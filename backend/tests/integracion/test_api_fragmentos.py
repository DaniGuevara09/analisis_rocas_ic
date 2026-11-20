"""Pruebas de la API de segmentación, edición de fragmentos y resultados (segmentador falso)."""

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
from app.adaptadores.salida.segmentacion.no_disponible import SegmentadorNoDisponible
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


def cuadrado(x: float, y: float, lado: float) -> list[dict[str, float]]:
    return [
        {"x": x, "y": y},
        {"x": x + lado, "y": y},
        {"x": x + lado, "y": y + lado},
        {"x": x, "y": y + lado},
    ]


def poligono(x: float, y: float, lado: float) -> Poligono:
    return Poligono(tuple(Punto(p["x"], p["y"]) for p in cuadrado(x, y, lado)))


@pytest.fixture
def segmentador() -> SegmentadorFalso:
    return SegmentadorFalso([poligono(0, 0, 10), poligono(100, 100, 40), poligono(300, 300, 80)])


@pytest.fixture
def cliente(segmentador: SegmentadorFalso) -> Iterator[TestClient]:
    repositorio, almacen = RepositorioFalso(), AlmacenFalso()
    app.dependency_overrides[obtener_repositorio] = lambda: repositorio
    app.dependency_overrides[obtener_almacen] = lambda: almacen
    app.dependency_overrides[obtener_inspector] = lambda: InspectorFalso(1600, 1200)
    app.dependency_overrides[obtener_segmentador] = lambda: segmentador
    configuracion = RepositorioConfiguracionFalso()
    app.dependency_overrides[obtener_repositorio_configuracion] = lambda: configuracion
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def id_analisis(cliente: TestClient) -> str:
    respuesta = cliente.post(
        "/api/analisis", data={"nombre": "pila"}, files={"imagen": ("f.jpg", CABECERA_JPG + b"x")}
    )
    return str(respuesta.json()["id"])


@pytest.fixture
def id_calibrado(cliente: TestClient, id_analisis: str) -> str:
    cliente.put(f"/api/analisis/{id_analisis}/calibracion", json=CALIBRACION)
    return id_analisis


# --- POST /segmentacion -----------------------------------------------------
def test_segmentar_devuelve_fragmentos_del_modelo(cliente: TestClient, id_calibrado: str) -> None:
    respuesta = cliente.post(f"/api/analisis/{id_calibrado}/segmentacion")
    assert respuesta.status_code == 200
    fragmentos = respuesta.json()
    assert len(fragmentos) == 3
    assert {f["origen"] for f in fragmentos} == {"MODELO"}
    assert all(f["diametro_equivalente_mm"] > 0 for f in fragmentos)
    detalle = cliente.get(f"/api/analisis/{id_calibrado}").json()
    assert detalle["estado"] == "SEGMENTADO"


def test_segmentar_sin_calibracion_devuelve_409(
    cliente: TestClient, id_analisis: str, segmentador: SegmentadorFalso
) -> None:
    respuesta = cliente.post(f"/api/analisis/{id_analisis}/segmentacion")
    assert respuesta.status_code == 409
    assert respuesta.json()["codigo"] == "ESCALA_NO_CALIBRADA"
    assert segmentador.llamadas == 0


def test_segmentar_id_inexistente_devuelve_404(cliente: TestClient) -> None:
    respuesta = cliente.post(f"/api/analisis/{uuid4()}/segmentacion")
    assert respuesta.status_code == 404


def test_segmentar_sin_modelo_devuelve_503(cliente: TestClient, id_calibrado: str) -> None:
    app.dependency_overrides[obtener_segmentador] = lambda: SegmentadorNoDisponible("falta")
    respuesta = cliente.post(f"/api/analisis/{id_calibrado}/segmentacion")
    assert respuesta.status_code == 503
    assert respuesta.json()["codigo"] == "MODELO_NO_DISPONIBLE"


# --- PUT /fragmentos ----------------------------------------------------------
def test_editar_fragmentos_reemplaza_la_lista(cliente: TestClient, id_calibrado: str) -> None:
    modelo = cliente.post(f"/api/analisis/{id_calibrado}/segmentacion").json()
    cuerpo = {
        "fragmentos": [
            {"id": modelo[0]["id"], "poligono": modelo[0]["poligono"], "origen": "MODELO"},
            {"poligono": cuadrado(500, 500, 30)},
        ]
    }
    respuesta = cliente.put(f"/api/analisis/{id_calibrado}/fragmentos", json=cuerpo)
    assert respuesta.status_code == 200
    fragmentos = respuesta.json()
    assert len(fragmentos) == 2
    assert fragmentos[0]["id"] == modelo[0]["id"]
    assert fragmentos[1]["origen"] == "MANUAL"
    detalle = cliente.get(f"/api/analisis/{id_calibrado}").json()
    assert detalle["numero_fragmentos"] == 2


def test_editar_fragmentos_sin_calibracion_devuelve_409(
    cliente: TestClient, id_analisis: str
) -> None:
    cuerpo = {"fragmentos": [{"poligono": cuadrado(0, 0, 10)}]}
    respuesta = cliente.put(f"/api/analisis/{id_analisis}/fragmentos", json=cuerpo)
    assert respuesta.status_code == 409


def test_editar_fragmento_con_poligono_invalido_devuelve_422(
    cliente: TestClient, id_calibrado: str
) -> None:
    cuerpo = {"fragmentos": [{"poligono": [{"x": 0, "y": 0}, {"x": 1, "y": 1}]}]}
    respuesta = cliente.put(f"/api/analisis/{id_calibrado}/fragmentos", json=cuerpo)
    assert respuesta.status_code == 422
    assert respuesta.json()["codigo"] == "DATOS_NO_VALIDOS"


def test_editar_fragmento_en_region_excluida_devuelve_422(
    cliente: TestClient, id_calibrado: str
) -> None:
    cliente.put(
        f"/api/analisis/{id_calibrado}/region-excluida", json={"poligono": cuadrado(0, 0, 200)}
    )
    cuerpo = {"fragmentos": [{"poligono": cuadrado(50, 50, 10)}]}
    respuesta = cliente.put(f"/api/analisis/{id_calibrado}/fragmentos", json=cuerpo)
    assert respuesta.status_code == 422


# --- GET /resultados ----------------------------------------------------------
def test_resultados_devuelve_indicadores_rangos_e_histograma(
    cliente: TestClient, id_calibrado: str
) -> None:
    cliente.post(f"/api/analisis/{id_calibrado}/segmentacion")
    respuesta = cliente.get(f"/api/analisis/{id_calibrado}/resultados")
    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert datos["numero_fragmentos"] == 3
    assert datos["d20"] <= datos["d50"] <= datos["d60"] <= datos["d80"] <= datos["d90"]
    assert len(datos["curva"]) == 3
    assert [r["indice"] for r in datos["rangos"]] == [0, 1, 2, 3, 4]
    assert datos["rangos"][-1]["limite_superior_mm"] is None
    assert sum(c["numero_fragmentos"] for c in datos["histograma"]) == 3
    assert len(datos["fragmentos"]) == 3
    assert any("esf" in s for s in datos["supuestos"])


def test_resultados_con_pocos_fragmentos_devuelve_409(
    cliente: TestClient, id_calibrado: str
) -> None:
    respuesta = cliente.get(f"/api/analisis/{id_calibrado}/resultados")
    assert respuesta.status_code == 409
    assert respuesta.json()["codigo"] == "DATOS_INSUFICIENTES"


def test_resultados_sin_calibracion_devuelve_409(cliente: TestClient, id_analisis: str) -> None:
    respuesta = cliente.get(f"/api/analisis/{id_analisis}/resultados")
    assert respuesta.json()["codigo"] == "ESCALA_NO_CALIBRADA"
