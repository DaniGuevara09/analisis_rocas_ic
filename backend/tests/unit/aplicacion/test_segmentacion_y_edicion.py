"""Pruebas de SegmentarAnalisis, EditarFragmentos y ObtenerResultados (adaptadores falsos)."""

from uuid import uuid4

import pytest

from app.aplicacion.casos_de_uso.crear_analisis import CrearAnalisis
from app.aplicacion.casos_de_uso.editar_fragmentos import EditarFragmentos, FragmentoEditado
from app.aplicacion.casos_de_uso.obtener_resultados import ObtenerResultados
from app.aplicacion.casos_de_uso.segmentar_analisis import SegmentarAnalisis
from app.dominio.errores import (
    AnalisisNoEncontrado,
    DatosInsuficientes,
    EscalaNoCalibrada,
    FragmentoEnRegionExcluida,
)
from app.dominio.modelo import Analisis, EstadoAnalisis, OrigenFragmento, Poligono, Punto
from tests.unit.aplicacion.fakes import (
    CABECERA_JPG,
    AlmacenFalso,
    InspectorFalso,
    RepositorioConfiguracionFalso,
    RepositorioFalso,
    SegmentadorFalso,
)


def cuadrado(x: float, y: float, lado: float) -> Poligono:
    return Poligono(
        (Punto(x, y), Punto(x + lado, y), Punto(x + lado, y + lado), Punto(x, y + lado))
    )


def puntos(poligono: Poligono) -> list[Punto]:
    return list(poligono.puntos)


@pytest.fixture
def repositorio() -> RepositorioFalso:
    return RepositorioFalso()


@pytest.fixture
def almacen() -> AlmacenFalso:
    return AlmacenFalso()


@pytest.fixture
def analisis(repositorio: RepositorioFalso, almacen: AlmacenFalso) -> Analisis:
    crear = CrearAnalisis(repositorio, almacen, InspectorFalso(1600, 1200))
    return crear.ejecutar("pila", CABECERA_JPG + b"foto")


@pytest.fixture
def calibrado(analisis: Analisis, repositorio: RepositorioFalso) -> Analisis:
    analisis.calibrar(Punto(0, 0), Punto(300, 400), 250.0)
    repositorio.guardar(analisis)
    return analisis


# --- SegmentarAnalisis -----------------------------------------------------
def test_segmentar_registra_fragmentos_del_modelo(
    calibrado: Analisis, repositorio: RepositorioFalso, almacen: AlmacenFalso
) -> None:
    segmentador = SegmentadorFalso([cuadrado(0, 0, 10), cuadrado(50, 50, 20)])
    fragmentos = SegmentarAnalisis(repositorio, almacen, segmentador).ejecutar(calibrado.id)

    guardado = repositorio.obtener(calibrado.id)
    assert guardado is not None
    assert len(fragmentos) == 2
    assert all(f.origen is OrigenFragmento.MODELO for f in guardado.fragmentos)
    assert guardado.estado is EstadoAnalisis.SEGMENTADO
    assert segmentador.ultima_imagen == CABECERA_JPG + b"foto"


def test_segmentar_sin_calibracion_no_llama_al_segmentador(
    analisis: Analisis, repositorio: RepositorioFalso, almacen: AlmacenFalso
) -> None:
    segmentador = SegmentadorFalso([cuadrado(0, 0, 10)])
    with pytest.raises(EscalaNoCalibrada):
        SegmentarAnalisis(repositorio, almacen, segmentador).ejecutar(analisis.id)
    assert segmentador.llamadas == 0


def test_segmentar_omite_poligonos_en_region_excluida(
    calibrado: Analisis, repositorio: RepositorioFalso, almacen: AlmacenFalso
) -> None:
    calibrado.excluir_region(cuadrado(100, 100, 100))
    repositorio.guardar(calibrado)
    segmentador = SegmentadorFalso([cuadrado(0, 0, 10), cuadrado(140, 140, 10)])
    fragmentos = SegmentarAnalisis(repositorio, almacen, segmentador).ejecutar(calibrado.id)
    assert len(fragmentos) == 1


def test_segmentar_id_inexistente_lanza_no_encontrado(
    repositorio: RepositorioFalso, almacen: AlmacenFalso
) -> None:
    with pytest.raises(AnalisisNoEncontrado):
        SegmentarAnalisis(repositorio, almacen, SegmentadorFalso()).ejecutar(uuid4())


def test_volver_a_segmentar_reemplaza_los_fragmentos(
    calibrado: Analisis, repositorio: RepositorioFalso, almacen: AlmacenFalso
) -> None:
    calibrado.agregar_fragmento(cuadrado(500, 500, 30))
    repositorio.guardar(calibrado)
    segmentador = SegmentadorFalso([cuadrado(0, 0, 10)])
    analisis_out, fragmentos = SegmentarAnalisis(
        repositorio, almacen, segmentador
    ).ejecutar_con_analisis(calibrado.id)
    assert analisis_out.id == calibrado.id
    assert len(fragmentos) == 1
    guardado = repositorio.obtener(calibrado.id)
    assert guardado is not None
    assert len(guardado.fragmentos) == 1
    assert guardado.fragmentos[0].origen is OrigenFragmento.MODELO


# --- EditarFragmentos -------------------------------------------------------
def test_editar_conserva_ids_existentes_y_crea_nuevos(
    calibrado: Analisis, repositorio: RepositorioFalso
) -> None:
    existente = calibrado.registrar_fragmentos([cuadrado(0, 0, 10)], OrigenFragmento.MODELO)[0]
    repositorio.guardar(calibrado)

    resultado = EditarFragmentos(repositorio).ejecutar(
        calibrado.id,
        [
            FragmentoEditado(existente.id, puntos(cuadrado(0, 0, 12)), OrigenFragmento.MODELO),
            FragmentoEditado(None, puntos(cuadrado(40, 40, 10)), OrigenFragmento.MANUAL),
        ],
    )

    guardado = repositorio.obtener(calibrado.id)
    assert guardado is not None
    assert guardado.fragmentos == resultado
    assert resultado[0].id == existente.id
    assert resultado[0].poligono.area() == pytest.approx(144.0)
    assert resultado[1].id != existente.id
    assert resultado[1].origen is OrigenFragmento.MANUAL


def test_editar_en_region_excluida_no_guarda(
    calibrado: Analisis, repositorio: RepositorioFalso
) -> None:
    calibrado.excluir_region(cuadrado(100, 100, 100))
    repositorio.guardar(calibrado)
    with pytest.raises(FragmentoEnRegionExcluida):
        EditarFragmentos(repositorio).ejecutar(
            calibrado.id,
            [FragmentoEditado(None, puntos(cuadrado(140, 140, 10)), OrigenFragmento.MANUAL)],
        )
    guardado = repositorio.obtener(calibrado.id)
    assert guardado is not None
    assert guardado.fragmentos == []


def test_editar_id_inexistente_lanza_no_encontrado(repositorio: RepositorioFalso) -> None:
    with pytest.raises(AnalisisNoEncontrado):
        EditarFragmentos(repositorio).ejecutar(uuid4(), [])


# --- ObtenerResultados ------------------------------------------------------
def test_obtener_resultados_devuelve_reporte(
    calibrado: Analisis, repositorio: RepositorioFalso
) -> None:
    calibrado.registrar_fragmentos(
        [cuadrado(0, 0, 10), cuadrado(20, 0, 20), cuadrado(50, 0, 40)], OrigenFragmento.MODELO
    )
    repositorio.guardar(calibrado)
    reporte = ObtenerResultados(repositorio, RepositorioConfiguracionFalso()).ejecutar(calibrado.id)
    assert reporte.resultado.numero_fragmentos == 3
    assert len(reporte.fragmentos) == 3


def test_obtener_resultados_con_pocos_fragmentos_lanza_datos_insuficientes(
    calibrado: Analisis, repositorio: RepositorioFalso
) -> None:
    with pytest.raises(DatosInsuficientes):
        ObtenerResultados(repositorio, RepositorioConfiguracionFalso()).ejecutar(calibrado.id)


def test_obtener_resultados_id_inexistente_lanza_no_encontrado(
    repositorio: RepositorioFalso,
) -> None:
    with pytest.raises(AnalisisNoEncontrado):
        ObtenerResultados(repositorio, RepositorioConfiguracionFalso()).ejecutar(uuid4())
