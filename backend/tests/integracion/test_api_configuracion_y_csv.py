"""Pruebas de la API de configuración de rangos (RF-14) y del CSV de resultados (RF-09)."""

import csv
import io
import zipfile
from collections.abc import Iterator
from uuid import uuid4
from xml.etree import ElementTree

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
    assert datos["modo"] == "ABSOLUTO"
    assert datos["cortes"] == [50, 150, 400, 800]
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
    assert respuesta.json()["modo"] == "ABSOLUTO"
    assert cliente.get("/api/configuracion/rangos").json()["colores"] == respuesta.json()["colores"]


# --- CSV y Excel -----------------------------------------------------------------
def test_csv_es_una_tabla_estandar_con_coma_y_punto_decimal(
    cliente: TestClient, id_segmentado: str
) -> None:
    respuesta = cliente.get(f"/api/analisis/{id_segmentado}/resultados.csv")
    assert respuesta.status_code == 200
    assert respuesta.headers["content-type"].startswith("text/csv")
    assert "attachment" in respuesta.headers["content-disposition"]
    filas = list(csv.reader(io.StringIO(respuesta.content.decode("utf-8-sig"))))
    assert filas[0] == [
        "numero",
        "id",
        "origen",
        "area_px2",
        "area_mm2",
        "diametro_equivalente_mm",
        "rango",
    ]
    assert len(filas) == 4  # encabezado + 3 fragmentos, sin otras tablas
    assert all(len(fila) == 7 for fila in filas)
    float(filas[1][5])  # punto decimal: se convierte sin ajustes regionales


def _hojas_xlsx(contenido: bytes) -> dict[str, list[list[str]]]:
    espacio = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    with zipfile.ZipFile(io.BytesIO(contenido)) as libro:
        nombres = [
            h.get("name")
            for h in ElementTree.fromstring(libro.read("xl/workbook.xml")).iter(
                f"{{{espacio['m']}}}sheet"
            )
        ]
        hojas = {}
        for i, nombre in enumerate(nombres, start=1):
            raiz = ElementTree.fromstring(libro.read(f"xl/worksheets/sheet{i}.xml"))
            hojas[str(nombre)] = [
                ["".join(c.itertext()) for c in fila.findall("m:c", espacio)]
                for fila in raiz.iter(f"{{{espacio['m']}}}row")
            ]
    return hojas


def test_xlsx_tiene_resumen_curva_y_fragmentos(cliente: TestClient, id_segmentado: str) -> None:
    respuesta = cliente.get(f"/api/analisis/{id_segmentado}/resultados.xlsx")
    assert respuesta.status_code == 200
    assert "spreadsheetml" in respuesta.headers["content-type"]
    hojas = _hojas_xlsx(respuesta.content)
    assert list(hojas) == ["Resumen", "Curva", "Fragmentos"]

    resumen = {fila[0]: fila[1:] for fila in hojas["Resumen"] if fila}
    assert resumen["Informe granulométrico"] == ["pila norte"]
    assert (
        float(resumen["Longitud del objeto de referencia (mm)"][0])
        == CALIBRACION["longitud_real_mm"]
    )
    assert float(resumen["D50"][0]) > 0
    assert float(resumen["Tamaño característico x_c (Rosin-Rammler)"][0]) > 0
    assert any("esférica" in clave for clave in resumen)  # supuestos (RNF-07)

    assert hojas["Curva"][0] == ["Diámetro (mm)", "% pasante medido", "% pasante Rosin-Rammler"]
    assert len(hojas["Fragmentos"]) == 4


def test_csv_sin_fragmentos_suficientes_devuelve_409(cliente: TestClient) -> None:
    creado = cliente.post(
        "/api/analisis", data={"nombre": "x"}, files={"imagen": ("f.jpg", CABECERA_JPG + b"x")}
    ).json()
    cliente.put(f"/api/analisis/{creado['id']}/calibracion", json=CALIBRACION)
    respuesta = cliente.get(f"/api/analisis/{creado['id']}/resultados.csv")
    assert respuesta.status_code == 409


def test_csv_de_analisis_inexistente_devuelve_404(cliente: TestClient) -> None:
    assert cliente.get(f"/api/analisis/{uuid4()}/resultados.csv").status_code == 404
    assert cliente.get(f"/api/analisis/{uuid4()}/resultados.xlsx").status_code == 404
