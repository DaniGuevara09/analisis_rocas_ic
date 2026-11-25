"""Pruebas de los casos de uso de configuración de rangos (RF-14)."""

import pytest

from app.aplicacion.casos_de_uso.configurar_rangos import (
    GuardarConfiguracionRangos,
    ObtenerConfiguracionRangos,
    RestablecerConfiguracionRangos,
)
from app.aplicacion.casos_de_uso.crear_analisis import CrearAnalisis
from app.aplicacion.casos_de_uso.obtener_resultados import ObtenerResultados
from app.dominio.configuracion import CONFIGURACION_POR_DEFECTO, ModoRangos
from app.dominio.errores import DatosNoValidos
from app.dominio.modelo import OrigenFragmento, Poligono, Punto
from tests.unit.aplicacion.fakes import (
    CABECERA_JPG,
    AlmacenFalso,
    InspectorFalso,
    RepositorioConfiguracionFalso,
    RepositorioFalso,
)

COLORES_3 = ["#111111", "#222222", "#333333"]


def cuadrado(x: float, lado: float) -> Poligono:
    return Poligono((Punto(x, 0), Punto(x + lado, 0), Punto(x + lado, lado), Punto(x, lado)))


@pytest.fixture
def repo_config() -> RepositorioConfiguracionFalso:
    return RepositorioConfiguracionFalso()


def test_sin_configuracion_guardada_devuelve_la_de_por_defecto(
    repo_config: RepositorioConfiguracionFalso,
) -> None:
    assert ObtenerConfiguracionRangos(repo_config).ejecutar() == CONFIGURACION_POR_DEFECTO


def test_guardar_y_obtener(repo_config: RepositorioConfiguracionFalso) -> None:
    guardada = GuardarConfiguracionRangos(repo_config).ejecutar(
        ModoRangos.ABSOLUTO, [100, 500], ["A", "B", "C"], COLORES_3
    )
    assert ObtenerConfiguracionRangos(repo_config).ejecutar() == guardada


def test_guardar_configuracion_invalida_no_cambia_nada(
    repo_config: RepositorioConfiguracionFalso,
) -> None:
    with pytest.raises(DatosNoValidos):
        GuardarConfiguracionRangos(repo_config).ejecutar(
            ModoRangos.ABSOLUTO, [500, 100], ["A", "B", "C"], COLORES_3
        )
    assert repo_config.rangos is None


def test_restablecer_vuelve_a_la_de_por_defecto(
    repo_config: RepositorioConfiguracionFalso,
) -> None:
    GuardarConfiguracionRangos(repo_config).ejecutar(
        ModoRangos.ABSOLUTO, [100], ["A", "B"], COLORES_3[:2]
    )
    assert RestablecerConfiguracionRangos(repo_config).ejecutar() == CONFIGURACION_POR_DEFECTO
    assert repo_config.rangos is None


def test_resultados_usan_la_configuracion_guardada(
    repo_config: RepositorioConfiguracionFalso,
) -> None:
    repositorio = RepositorioFalso()
    analisis = CrearAnalisis(repositorio, AlmacenFalso(), InspectorFalso()).ejecutar(
        "pila", CABECERA_JPG + b"x"
    )
    analisis.calibrar(Punto(0, 0), Punto(10, 0), 10.0)
    analisis.registrar_fragmentos(
        [cuadrado(0, 10), cuadrado(20, 20), cuadrado(50, 40)], OrigenFragmento.MODELO
    )
    repositorio.guardar(analisis)
    GuardarConfiguracionRangos(repo_config).ejecutar(
        ModoRangos.ABSOLUTO, [1000], ["Todo", "Nada"], COLORES_3[:2]
    )
    reporte = ObtenerResultados(repositorio, repo_config).ejecutar(analisis.id)
    assert reporte.nombres_rangos == ("Todo", "Nada")
    assert {m.indice_rango for m in reporte.fragmentos} == {0}
