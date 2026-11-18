"""Prueba de la ruta de salud."""
from fastapi.testclient import TestClient

from app.main import app


def test_salud_devuelve_ok() -> None:
    respuesta = TestClient(app).get("/api/salud")
    assert respuesta.status_code == 200
    assert respuesta.json() == {"estado": "ok"}
