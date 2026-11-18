"""Pruebas del repositorio contra PostgreSQL real (requiere TEST_DATABASE_URL)."""
import os
from collections.abc import Iterator
from uuid import uuid4

import pytest
from sqlalchemy import Engine, create_engine, func, select

from app.adaptadores.salida.persistencia.repositorio import RepositorioPostgreSQL
from app.adaptadores.salida.persistencia.tablas import Base, TablaFragmento
from app.dominio.modelo import (
    Analisis,
    EstadoAnalisis,
    Imagen,
    OrigenFragmento,
    Poligono,
    Punto,
)

URL = os.environ.get("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not URL, reason="Defina TEST_DATABASE_URL para ejecutar las pruebas contra PostgreSQL"
)


@pytest.fixture
def motor() -> Iterator[Engine]:
    assert URL is not None
    motor = create_engine(URL)
    Base.metadata.drop_all(motor)
    Base.metadata.create_all(motor)
    yield motor
    Base.metadata.drop_all(motor)
    motor.dispose()


@pytest.fixture
def repositorio(motor: Engine) -> RepositorioPostgreSQL:
    return RepositorioPostgreSQL(motor)


def cuadrado(x: float, y: float, lado: float) -> Poligono:
    esquinas = [(x, y), (x + lado, y), (x + lado, y + lado), (x, y + lado)]
    return Poligono(tuple(Punto(a, b) for a, b in esquinas))


def analisis_nuevo(nombre: str = "pila") -> Analisis:
    return Analisis.crear(nombre, Imagen("a.jpg", 1920, 1080, "JPG"))


def analisis_completo() -> Analisis:
    analisis = analisis_nuevo()
    analisis.calibrar(Punto(0, 0), Punto(300, 400), 250.0)
    analisis.excluir_region(cuadrado(0, 0, 100))
    analisis.registrar_fragmentos(
        [cuadrado(200, 200, 10), cuadrado(300, 300, 20)], OrigenFragmento.MODELO
    )
    analisis.agregar_fragmento(cuadrado(500, 500, 30))
    return analisis


def test_guardar_y_recuperar_agregado_completo(repositorio: RepositorioPostgreSQL) -> None:
    analisis = analisis_completo()
    repositorio.guardar(analisis)
    recuperado = repositorio.obtener(analisis.id)
    assert recuperado is not None
    assert recuperado.id == analisis.id
    assert recuperado.nombre == analisis.nombre
    assert recuperado.estado is EstadoAnalisis.SEGMENTADO
    assert recuperado.fecha_creacion == analisis.fecha_creacion
    assert recuperado.imagen == analisis.imagen
    assert recuperado.calibracion == analisis.calibracion
    assert recuperado.region_excluida == analisis.region_excluida
    assert sorted(recuperado.fragmentos, key=lambda f: f.id) == sorted(
        analisis.fragmentos, key=lambda f: f.id
    )


def test_guardar_analisis_sin_calibracion_ni_region(repositorio: RepositorioPostgreSQL) -> None:
    analisis = analisis_nuevo()
    repositorio.guardar(analisis)
    recuperado = repositorio.obtener(analisis.id)
    assert recuperado is not None
    assert recuperado.calibracion is None
    assert recuperado.region_excluida is None
    assert recuperado.fragmentos == []


def test_obtener_inexistente_devuelve_none(repositorio: RepositorioPostgreSQL) -> None:
    assert repositorio.obtener(uuid4()) is None


def test_guardar_de_nuevo_reemplaza_calibracion_region_y_fragmentos(
    repositorio: RepositorioPostgreSQL,
) -> None:
    analisis = analisis_completo()
    repositorio.guardar(analisis)
    analisis.nombre = "renombrado"
    analisis.calibrar(Punto(0, 0), Punto(100, 0), 50.0)
    analisis.quitar_region_excluida()
    analisis.registrar_fragmentos([cuadrado(10, 10, 5)], OrigenFragmento.MODELO)
    repositorio.guardar(analisis)
    recuperado = repositorio.obtener(analisis.id)
    assert recuperado is not None
    assert recuperado.nombre == "renombrado"
    assert recuperado.calibracion == analisis.calibracion
    assert recuperado.region_excluida is None
    assert recuperado.fragmentos == analisis.fragmentos
    assert len(repositorio.listar()) == 1


def test_listar_devuelve_el_mas_reciente_primero(repositorio: RepositorioPostgreSQL) -> None:
    primero, segundo = analisis_nuevo("a"), analisis_nuevo("b")
    repositorio.guardar(primero)
    repositorio.guardar(segundo)
    assert [a.nombre for a in repositorio.listar()] == ["b", "a"]


def test_eliminar_borra_en_cascada(repositorio: RepositorioPostgreSQL, motor: Engine) -> None:
    analisis = analisis_completo()
    repositorio.guardar(analisis)
    repositorio.eliminar(analisis.id)
    assert repositorio.obtener(analisis.id) is None
    with motor.connect() as conexion:
        assert conexion.execute(select(func.count()).select_from(TablaFragmento)).scalar() == 0


def test_calibrar_y_excluir_region_se_guardan_y_recuperan(
    repositorio: RepositorioPostgreSQL,
) -> None:
    analisis = analisis_nuevo()
    repositorio.guardar(analisis)
    analisis.calibrar(Punto(0, 0), Punto(300, 400), 250.0)
    analisis.excluir_region(cuadrado(100, 100, 200))
    repositorio.guardar(analisis)
    recuperado = repositorio.obtener(analisis.id)
    assert recuperado is not None
    assert recuperado.estado is EstadoAnalisis.CALIBRADO
    assert recuperado.calibracion == analisis.calibracion
    assert recuperado.calibracion is not None
    assert recuperado.calibracion.factor_mm_por_px() == 0.5
    assert recuperado.region_excluida == analisis.region_excluida

    recuperado.quitar_region_excluida()
    repositorio.guardar(recuperado)
    sin_region = repositorio.obtener(analisis.id)
    assert sin_region is not None
    assert sin_region.region_excluida is None
    assert sin_region.calibracion == analisis.calibracion
