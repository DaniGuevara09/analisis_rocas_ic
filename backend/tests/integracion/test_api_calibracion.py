"""Pruebas de la API de calibración y región excluida (imagen de 1600x1200)."""

from collections.abc import Iterator
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.adaptadores.entrada.api.dependencias import (
    obtener_almacen,
    obtener_inspector,
    obtener_repositorio,
)
from app.main import app
from tests.unit.aplicacion.fakes import (
    CABECERA_JPG,
    AlmacenFalso,
    InspectorFalso,
    RepositorioFalso,
)

CUADRADO = [{"x": 100, "y": 100}, {"x": 300, "y": 100}, {"x": 300, "y": 300}, {"x": 100, "y": 300}]
CALIBRACION = {"inicio": {"x": 0, "y": 0}, "fin": {"x": 300, "y": 400}, "longitud_real_mm": 250}


@pytest.fixture
def cliente() -> Iterator[TestClient]:
    repositorio, almacen = RepositorioFalso(), AlmacenFalso()
    app.dependency_overrides[obtener_repositorio] = lambda: repositorio
    app.dependency_overrides[obtener_almacen] = lambda: almacen
    app.dependency_overrides[obtener_inspector] = lambda: InspectorFalso(1600, 1200)
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def id_analisis(cliente: TestClient) -> str:
    respuesta = cliente.post(
        "/api/analisis", data={"nombre": "pila"}, files={"imagen": ("f.jpg", CABECERA_JPG + b"x")}
    )
    return str(respuesta.json()["id"])


def test_calibrar_devuelve_factor_y_estado(cliente: TestClient, id_analisis: str) -> None:
    respuesta = cliente.put(f"/api/analisis/{id_analisis}/calibracion", json=CALIBRACION)
    assert respuesta.status_code == 200
    assert respuesta.json() == {"factor_mm_por_px": 0.5, "estado": "CALIBRADO"}


def test_detalle_muestra_la_calibracion(cliente: TestClient, id_analisis: str) -> None:
    cliente.put(f"/api/analisis/{id_analisis}/calibracion", json=CALIBRACION)
    detalle = cliente.get(f"/api/analisis/{id_analisis}").json()
    assert detalle["estado"] == "CALIBRADO"
    assert detalle["calibracion"] == {
        "inicio": {"x": 0, "y": 0},
        "fin": {"x": 300, "y": 400},
        "longitud_real_mm": 250,
        "factor_mm_por_px": 0.5,
    }


@pytest.mark.parametrize("longitud", [0, -5])
def test_calibrar_con_longitud_no_positiva_devuelve_422(
    cliente: TestClient, id_analisis: str, longitud: float
) -> None:
    cuerpo = {**CALIBRACION, "longitud_real_mm": longitud}
    respuesta = cliente.put(f"/api/analisis/{id_analisis}/calibracion", json=cuerpo)
    assert respuesta.status_code == 422
    assert respuesta.json()["codigo"] == "DATOS_NO_VALIDOS"


def test_calibrar_con_punto_fuera_de_la_imagen_devuelve_422(
    cliente: TestClient, id_analisis: str
) -> None:
    cuerpo = {**CALIBRACION, "fin": {"x": 2000, "y": 0}}
    respuesta = cliente.put(f"/api/analisis/{id_analisis}/calibracion", json=cuerpo)
    assert respuesta.status_code == 422
    assert respuesta.json()["codigo"] == "DATOS_NO_VALIDOS"


def test_calibrar_con_puntos_coincidentes_devuelve_422(
    cliente: TestClient, id_analisis: str
) -> None:
    cuerpo = {**CALIBRACION, "fin": {"x": 0, "y": 0}}
    assert cliente.put(f"/api/analisis/{id_analisis}/calibracion", json=cuerpo).status_code == 422


@pytest.mark.parametrize("valor", ["NaN", "Infinity", "-Infinity"])
def test_calibrar_con_coordenada_no_finita_devuelve_422(
    cliente: TestClient, id_analisis: str, valor: str
) -> None:
    contenido = f'{{"inicio":{{"x":0,"y":0}},"fin":{{"x":{valor},"y":10}},"longitud_real_mm":250}}'
    respuesta = cliente.put(
        f"/api/analisis/{id_analisis}/calibracion",
        content=contenido,
        headers={"Content-Type": "application/json"},
    )
    assert respuesta.status_code == 422
    assert respuesta.json()["codigo"] == "DATOS_NO_VALIDOS"


def test_calibrar_sin_cuerpo_valido_devuelve_422(cliente: TestClient, id_analisis: str) -> None:
    assert cliente.put(f"/api/analisis/{id_analisis}/calibracion", json={}).status_code == 422


def test_region_valida_aparece_en_el_detalle(cliente: TestClient, id_analisis: str) -> None:
    respuesta = cliente.put(
        f"/api/analisis/{id_analisis}/region-excluida", json={"poligono": CUADRADO}
    )
    assert respuesta.status_code == 200
    assert respuesta.json()["region_excluida"] == {"poligono": CUADRADO}
    detalle = cliente.get(f"/api/analisis/{id_analisis}").json()
    assert detalle["region_excluida"] == {"poligono": CUADRADO}


def test_region_con_menos_de_tres_puntos_devuelve_422(
    cliente: TestClient, id_analisis: str
) -> None:
    respuesta = cliente.put(
        f"/api/analisis/{id_analisis}/region-excluida", json={"poligono": CUADRADO[:2]}
    )
    assert respuesta.status_code == 422
    assert respuesta.json()["codigo"] == "DATOS_NO_VALIDOS"


def test_region_fuera_de_la_imagen_devuelve_422(cliente: TestClient, id_analisis: str) -> None:
    fuera = [{"x": 1500, "y": 1000}, {"x": 1700, "y": 1000}, {"x": 1700, "y": 1100}]
    ruta = f"/api/analisis/{id_analisis}/region-excluida"
    assert cliente.put(ruta, json={"poligono": fuera}).status_code == 422


def test_quitar_region_devuelve_204_y_desaparece(cliente: TestClient, id_analisis: str) -> None:
    cliente.put(f"/api/analisis/{id_analisis}/region-excluida", json={"poligono": CUADRADO})
    assert cliente.delete(f"/api/analisis/{id_analisis}/region-excluida").status_code == 204
    assert cliente.get(f"/api/analisis/{id_analisis}").json()["region_excluida"] is None


def test_quitar_region_dos_veces_devuelve_204(cliente: TestClient, id_analisis: str) -> None:
    ruta = f"/api/analisis/{id_analisis}/region-excluida"
    assert cliente.delete(ruta).status_code == 204
    assert cliente.delete(ruta).status_code == 204


@pytest.mark.parametrize(
    "metodo, sufijo, cuerpo",
    [
        ("put", "calibracion", CALIBRACION),
        ("put", "region-excluida", {"poligono": CUADRADO}),
        ("delete", "region-excluida", None),
    ],
)
def test_id_inexistente_devuelve_404(
    cliente: TestClient, metodo: str, sufijo: str, cuerpo: dict | None
) -> None:
    ruta = f"/api/analisis/{uuid4()}/{sufijo}"
    respuesta = cliente.request(metodo.upper(), ruta, json=cuerpo)
    assert respuesta.status_code == 404
    assert respuesta.json()["codigo"] == "NO_ENCONTRADO"
