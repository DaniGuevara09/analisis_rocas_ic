"""Repositorio de configuración contra PostgreSQL real (requiere TEST_DATABASE_URL)."""

import os
from collections.abc import Iterator

import pytest
from sqlalchemy import Engine, create_engine

from app.adaptadores.salida.persistencia.repositorio_configuracion import (
    RepositorioConfiguracionPostgreSQL,
    rangos_a_json,
    rangos_desde_json,
)
from app.adaptadores.salida.persistencia.tablas import Base
from app.dominio.configuracion import CONFIGURACION_POR_DEFECTO, ConfiguracionRangos, ModoRangos

URL = os.environ.get("TEST_DATABASE_URL")
OTRA = ConfiguracionRangos(ModoRangos.ABSOLUTO, (100.0,), ("A", "B"), ("#111111", "#222222"))


def test_json_ida_y_vuelta() -> None:
    assert rangos_desde_json(rangos_a_json(CONFIGURACION_POR_DEFECTO)) == CONFIGURACION_POR_DEFECTO


@pytest.fixture
def repositorio() -> Iterator[RepositorioConfiguracionPostgreSQL]:
    if not URL:
        pytest.skip("Defina TEST_DATABASE_URL para ejecutar las pruebas contra PostgreSQL")
    motor: Engine = create_engine(URL)
    Base.metadata.drop_all(motor)
    Base.metadata.create_all(motor)
    yield RepositorioConfiguracionPostgreSQL(motor)
    Base.metadata.drop_all(motor)
    motor.dispose()


def test_sin_configuracion_devuelve_none(repositorio: RepositorioConfiguracionPostgreSQL) -> None:
    assert repositorio.obtener_rangos() is None


def test_guardar_reemplazar_y_borrar(repositorio: RepositorioConfiguracionPostgreSQL) -> None:
    repositorio.guardar_rangos(CONFIGURACION_POR_DEFECTO)
    repositorio.guardar_rangos(OTRA)
    assert repositorio.obtener_rangos() == OTRA
    repositorio.guardar_rangos(None)
    assert repositorio.obtener_rangos() is None
