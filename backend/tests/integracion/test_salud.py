"""Prueba de la ruta de salud."""
from fastapi.testclient import TestClient

from app.adaptadores.salida.segmentacion.no_disponible import SegmentadorNoDisponible
from app.main import app
from tests.unit.aplicacion.fakes import SegmentadorFalso


def test_salud_devuelve_ok_y_modelo_no_disponible() -> None:
    app.state.segmentador = SegmentadorNoDisponible("sin modelo")
    respuesta = TestClient(app).get("/api/salud")
    assert respuesta.status_code == 200
    assert respuesta.json() == {"estado": "ok", "modelo_disponible": False}


def test_salud_informa_modelo_disponible() -> None:
    anterior = app.state.segmentador
    app.state.segmentador = SegmentadorFalso()
    try:
        assert TestClient(app).get("/api/salud").json()["modelo_disponible"] is True
    finally:
        app.state.segmentador = anterior
