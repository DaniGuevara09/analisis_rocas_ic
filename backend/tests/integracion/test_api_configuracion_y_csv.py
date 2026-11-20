"""Pruebas de la API de configuración de rangos (RF-14) y del CSV de resultados (RF-09)."""

from collections.abc import Iterator
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.adaptadores.entrada.api.dependencias import (
    obtener_almacen,
    obtener_inspector,
    obtener_repositorio,
    obtener_repositorio_configuracion,
    obtener_segmentador,
)
from app.dominio.modelo import Poligono, Punto
from app.main import app
from tests.unit.aplicacion.fakes import (
    CABECERA_JPG,
    AlmacenFalso,
    InspectorFalso,
    RepositorioConfiguracionFalso,
    RepositorioFalso,
    SegmentadorFalso,
)

CALIBRACION = {"inicio": {"x": 0, "y": 0}, "fin": {"x": 300, "y": 400}, "longitud_real_mm": 250}
ABSOLUTA = {
    "modo": "ABSOLUTO",
    "cortes": [20, 40],
    "nombres": ["Chicos", "Medianos", "Grandes"],
    "colores": ["#AAAAAA", "#555555", "#000000"],
}


def cuadrado(x: float, lado: float) -> Poligono:
    return Poligono((Punto(x, 0), Punto(x + lado, 0), Punto(x + lado, lado), Punto(x, lado)))


@pytest.fixture
def cliente() -> Iterator[TestClient]:
    repositorio, almacen = RepositorioFalso(), AlmacenFalso()
    configuracion = RepositorioConfiguracionFalso()
    segmentador = SegmentadorFalso([cuadrado(0, 10), cuadrado(100, 40), cuadrado(300, 80)])
    app.dependency_overrides[obtener_repositorio] = lambda: repositorio
    app.dependency_overrides[obtener_almacen] = lambda: almacen
    app.dependency_overrides[obtener_inspector] = lambda: InspectorFalso(1600, 1200)
    app.dependency_overrides[obtener_segmentador] = lambda: segmentador
    app.dependency_overrides[obtener_repositorio_configuracion] = lambda: configuracion
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def id_segmentado(cliente: TestClient) -> str:
    creado = cliente.post(
        "/api/analisis",
        data={"nombre": "pila norte"},
        files={"imagen": ("f.jpg", CABECERA_JPG + b"x")},
    ).json()
    cliente.put(f"/api/analisis/{creado['id']}/calibracion", json=CALIBRACION)
    cliente.post(f"/api/analisis/{creado['id']}/segmentacion")
    return str(creado["id"])


# --- Configuración de rangos -------------------------------------------------
def test_configuracion_por_defecto(cliente: TestClient) -> None:
    datos = cliente.get("/api/configuracion/rangos").json()
    assert datos["modo"] == "RELATIVO"
    assert datos["cortes"] == [20, 50, 80, 90]
    assert len(datos["colores"]) == 5


def test_guardar_configuracion_y_se_aplica_a_resultados(
    cliente: TestClient, id_segmentado: str
) -> None:
    respuesta = cliente.put("/api/configuracion/rangos", json=ABSOLUTA)
    assert respuesta.status_code == 200
    assert respuesta.json()["colores"][0] == "#aaaaaa"

    rangos = cliente.get(f"/api/analisis/{id_segmentado}/resultados").json()["rangos"]
    assert [r["nombre"] for r in rangos] == ["Chicos", "Medianos", "Grandes"]
    assert rangos[1]["limite_inferior_mm"] == 20
    assert rangos[1]["color"] == "#555555"


def test_configuracion_invalida_devuelve_422(cliente: TestClient) -> None:
    respuesta = cliente.put("/api/configuracion/rangos", json={**ABSOLUTA, "cortes": [40, 20]})
    assert respuesta.status_code == 422
    assert respuesta.json()["codigo"] == "DATOS_NO_VALIDOS"


def test_restablecer_configuracion(cliente: TestClient) -> None:
    cliente.put("/api/configuracion/rangos", json=ABSOLUTA)
    respuesta = cliente.delete("/api/configuracion/rangos")
    assert respuesta.status_code == 200
    assert respuesta.json()["modo"] == "RELATIVO"
    assert cliente.get("/api/configuracion/rangos").json()["modo"] == "RELATIVO"


# --- CSV -----------------------------------------------------------------------
def test_csv_contiene_indicadores_supuestos_y_fragmentos(
    cliente: TestClient, id_segmentado: str
) -> None:
    respuesta = cliente.get(f"/api/analisis/{id_segmentado}/resultados.csv")
    assert respuesta.status_code == 200
    assert respuesta.headers["content-type"].startswith("text/csv")
    assert "attachment" in respuesta.headers["content-disposition"]
    texto = respuesta.content.decode("utf-8-sig")
    lineas = texto.splitlines()
    assert lineas[0] == "Informe granulometrico;pila norte"
    assert any(linea.startswith("D50 (mm);") for linea in lineas)
    assert any("esf" in linea for linea in lineas)  # supuesto de esfericidad (RNF-07)
    filas_fragmento = [linea for linea in lineas if linea.split(";")[0] in {"1", "2", "3"}]
    assert len(filas_fragmento) == 3
    assert "," in filas_fragmento[0].split(";")[5]  # coma decimal


def test_csv_sin_fragmentos_suficientes_devuelve_409(cliente: TestClient) -> None:
    creado = cliente.post(
        "/api/analisis", data={"nombre": "x"}, files={"imagen": ("f.jpg", CABECERA_JPG + b"x")}
    ).json()
    cliente.put(f"/api/analisis/{creado['id']}/calibracion", json=CALIBRACION)
    respuesta = cliente.get(f"/api/analisis/{creado['id']}/resultados.csv")
    assert respuesta.status_code == 409


def test_csv_de_analisis_inexistente_devuelve_404(cliente: TestClient) -> None:
    assert cliente.get(f"/api/analisis/{uuid4()}/resultados.csv").status_code == 404
