"""Pruebas de los casos de uso de calibración y región excluida."""

from uuid import uuid4

import pytest

from app.aplicacion.casos_de_uso.calibrar_escala import CalibrarEscala
from app.aplicacion.casos_de_uso.crear_analisis import CrearAnalisis
from app.aplicacion.casos_de_uso.excluir_region import ExcluirRegion
from app.aplicacion.casos_de_uso.quitar_region_excluida import QuitarRegionExcluida
from app.dominio.errores import AnalisisNoEncontrado, CalibracionNoValida, PoligonoNoValido
from app.dominio.modelo import Analisis, EstadoAnalisis, Punto
from tests.unit.aplicacion.fakes import (
    CABECERA_JPG,
    AlmacenFalso,
    InspectorFalso,
    RepositorioFalso,
)

CUADRADO = [Punto(0, 0), Punto(100, 0), Punto(100, 100), Punto(0, 100)]


@pytest.fixture
def repositorio() -> RepositorioFalso:
    return RepositorioFalso()


@pytest.fixture
def analisis(repositorio: RepositorioFalso) -> Analisis:
    crear = CrearAnalisis(repositorio, AlmacenFalso(), InspectorFalso(1600, 1200))
    return crear.ejecutar("pila", CABECERA_JPG + b"x")


# --- CalibrarEscala ---------------------------------------------------------
def test_calibrar_fija_la_calibracion_y_guarda(
    analisis: Analisis, repositorio: RepositorioFalso
) -> None:
    resultado = CalibrarEscala(repositorio).ejecutar(analisis.id, Punto(0, 0), Punto(300, 400), 250)
    assert resultado.estado is EstadoAnalisis.CALIBRADO
    assert resultado.calibracion is not None
    assert resultado.calibracion.factor_mm_por_px() == pytest.approx(0.5)
    assert repositorio.datos[analisis.id].calibracion == resultado.calibracion


def test_calibrar_con_punto_fuera_de_la_imagen_lanza_error(
    analisis: Analisis, repositorio: RepositorioFalso
) -> None:
    with pytest.raises(CalibracionNoValida):
        CalibrarEscala(repositorio).ejecutar(analisis.id, Punto(0, 0), Punto(2000, 0), 250)
    assert repositorio.datos[analisis.id].calibracion is None


def test_calibrar_inexistente_lanza_no_encontrado(repositorio: RepositorioFalso) -> None:
    with pytest.raises(AnalisisNoEncontrado):
        CalibrarEscala(repositorio).ejecutar(uuid4(), Punto(0, 0), Punto(1, 1), 10)


# --- ExcluirRegion ----------------------------------------------------------
def test_excluir_region_fija_la_region_y_guarda(
    analisis: Analisis, repositorio: RepositorioFalso
) -> None:
    resultado = ExcluirRegion(repositorio).ejecutar(analisis.id, CUADRADO)
    assert resultado.region_excluida is not None
    assert resultado.region_excluida.poligono.puntos == tuple(CUADRADO)
    assert repositorio.datos[analisis.id].region_excluida == resultado.region_excluida


def test_excluir_region_con_menos_de_tres_puntos_lanza_error(
    analisis: Analisis, repositorio: RepositorioFalso
) -> None:
    with pytest.raises(PoligonoNoValido):
        ExcluirRegion(repositorio).ejecutar(analisis.id, CUADRADO[:2])


def test_excluir_region_fuera_de_la_imagen_lanza_error(
    analisis: Analisis, repositorio: RepositorioFalso
) -> None:
    fuera = [Punto(1500, 1100), Punto(1700, 1100), Punto(1700, 1150)]
    with pytest.raises(PoligonoNoValido):
        ExcluirRegion(repositorio).ejecutar(analisis.id, fuera)


def test_excluir_region_inexistente_lanza_no_encontrado(repositorio: RepositorioFalso) -> None:
    with pytest.raises(AnalisisNoEncontrado):
        ExcluirRegion(repositorio).ejecutar(uuid4(), CUADRADO)


# --- QuitarRegionExcluida ---------------------------------------------------
def test_quitar_region_la_elimina_y_guarda(
    analisis: Analisis, repositorio: RepositorioFalso
) -> None:
    ExcluirRegion(repositorio).ejecutar(analisis.id, CUADRADO)
    QuitarRegionExcluida(repositorio).ejecutar(analisis.id)
    assert repositorio.datos[analisis.id].region_excluida is None


def test_quitar_region_es_idempotente(analisis: Analisis, repositorio: RepositorioFalso) -> None:
    caso = QuitarRegionExcluida(repositorio)
    caso.ejecutar(analisis.id)
    caso.ejecutar(analisis.id)
    assert repositorio.datos[analisis.id].region_excluida is None


def test_quitar_region_inexistente_lanza_no_encontrado(repositorio: RepositorioFalso) -> None:
    with pytest.raises(AnalisisNoEncontrado):
        QuitarRegionExcluida(repositorio).ejecutar(uuid4())
