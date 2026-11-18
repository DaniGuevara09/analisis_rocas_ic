"""Pruebas de la API de análisis con adaptadores falsos inyectados."""
from collections.abc import Iterator
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from httpx import Response

from app.adaptadores.entrada.api import router_analisis
from app.adaptadores.entrada.api.dependencias import (
    obtener_almacen,
    obtener_inspector,
    obtener_repositorio,
)
from app.main import app
from tests.unit.aplicacion.fakes import (
    CABECERA_JPG,
    CABECERA_PNG,
    AlmacenFalso,
    InspectorFalso,
    RepositorioFalso,
)

JPG = CABECERA_JPG + b"datos"
PNG = CABECERA_PNG + b"datos"


@pytest.fixture
def almacen() -> AlmacenFalso:
    return AlmacenFalso()


@pytest.fixture
def repositorio() -> RepositorioFalso:
    return RepositorioFalso()


@pytest.fixture
def cliente(repositorio: RepositorioFalso, almacen: AlmacenFalso) -> Iterator[TestClient]:
    app.dependency_overrides[obtener_repositorio] = lambda: repositorio
    app.dependency_overrides[obtener_almacen] = lambda: almacen
    app.dependency_overrides[obtener_inspector] = lambda: InspectorFalso()
    yield TestClient(app)
    app.dependency_overrides.clear()


def crear(cliente: TestClient, nombre: str = "pila 1", contenido: bytes = JPG) -> Response:
    return cliente.post(
        "/api/analisis", data={"nombre": nombre}, files={"imagen": ("foto.jpg", contenido)}
    )


def test_crear_devuelve_201_con_resumen(cliente: TestClient, almacen: AlmacenFalso) -> None:
    respuesta = crear(cliente)
    assert respuesta.status_code == 201
    cuerpo = respuesta.json()
    assert cuerpo["nombre"] == "pila 1"
    assert cuerpo["estado"] == "IMAGEN_CARGADA"
    assert cuerpo["numero_fragmentos"] == 0
    assert len(almacen.archivos) == 1


def test_listar_devuelve_los_analisis(cliente: TestClient) -> None:
    crear(cliente, "a")
    crear(cliente, "b")
    respuesta = cliente.get("/api/analisis")
    assert respuesta.status_code == 200
    assert {a["nombre"] for a in respuesta.json()} == {"a", "b"}


def test_listar_vacio(cliente: TestClient) -> None:
    assert cliente.get("/api/analisis").json() == []


def test_obtener_devuelve_detalle(cliente: TestClient) -> None:
    id_ = crear(cliente).json()["id"]
    respuesta = cliente.get(f"/api/analisis/{id_}")
    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["imagen"] == {
        "url": f"/api/analisis/{id_}/imagen",
        "ancho_px": 640,
        "alto_px": 480,
        "formato": "JPG",
    }
    assert cuerpo["calibracion"] is None
    assert cuerpo["region_excluida"] is None
    assert cuerpo["fragmentos"] == []


def test_renombrar(cliente: TestClient) -> None:
    id_ = crear(cliente).json()["id"]
    respuesta = cliente.patch(f"/api/analisis/{id_}", json={"nombre": "nuevo"})
    assert respuesta.status_code == 200
    assert respuesta.json()["nombre"] == "nuevo"
    assert cliente.get(f"/api/analisis/{id_}").json()["nombre"] == "nuevo"


def test_eliminar_devuelve_204_y_borra_la_imagen(
    cliente: TestClient, almacen: AlmacenFalso
) -> None:
    id_ = crear(cliente).json()["id"]
    respuesta = cliente.delete(f"/api/analisis/{id_}")
    assert respuesta.status_code == 204
    assert almacen.archivos == {}
    assert cliente.get(f"/api/analisis/{id_}").status_code == 404


@pytest.mark.parametrize(
    "contenido, tipo", [(JPG, "image/jpeg"), (PNG, "image/png")]
)
def test_obtener_imagen(cliente: TestClient, contenido: bytes, tipo: str) -> None:
    id_ = crear(cliente, contenido=contenido).json()["id"]
    respuesta = cliente.get(f"/api/analisis/{id_}/imagen")
    assert respuesta.status_code == 200
    assert respuesta.headers["content-type"] == tipo
    assert respuesta.content == contenido


def test_formato_no_valido_devuelve_415(cliente: TestClient) -> None:
    respuesta = crear(cliente, contenido=b"hola")
    assert respuesta.status_code == 415
    assert respuesta.json()["codigo"] == "FORMATO_NO_VALIDO"


@pytest.mark.parametrize("peticion", ["obtener", "renombrar", "eliminar", "imagen"])
def test_id_inexistente_devuelve_404(cliente: TestClient, peticion: str) -> None:
    ruta = f"/api/analisis/{uuid4()}"
    respuesta = {
        "obtener": lambda: cliente.get(ruta),
        "renombrar": lambda: cliente.patch(ruta, json={"nombre": "x"}),
        "eliminar": lambda: cliente.delete(ruta),
        "imagen": lambda: cliente.get(ruta + "/imagen"),
    }[peticion]()
    assert respuesta.status_code == 404
    assert respuesta.json()["codigo"] == "NO_ENCONTRADO"


@pytest.mark.parametrize("nombre", ["", "   ", "x" * 151])
def test_nombre_no_valido_devuelve_422(cliente: TestClient, nombre: str) -> None:
    respuesta = crear(cliente, nombre)
    assert respuesta.status_code == 422
    assert respuesta.json()["codigo"] == "DATOS_NO_VALIDOS"


def test_renombrar_con_nombre_vacio_devuelve_422(cliente: TestClient) -> None:
    id_ = crear(cliente).json()["id"]
    respuesta = cliente.patch(f"/api/analisis/{id_}", json={"nombre": ""})
    assert respuesta.status_code == 422
    assert respuesta.json()["codigo"] == "DATOS_NO_VALIDOS"


def test_falta_la_imagen_devuelve_422_con_formato_de_error(cliente: TestClient) -> None:
    respuesta = cliente.post("/api/analisis", data={"nombre": "x"})
    assert respuesta.status_code == 422
    assert respuesta.json()["codigo"] == "DATOS_NO_VALIDOS"


def test_id_con_formato_invalido_devuelve_422(cliente: TestClient) -> None:
    assert cliente.get("/api/analisis/no-es-uuid").status_code == 422


def test_imagen_de_mas_de_20_mb_devuelve_413(
    cliente: TestClient, monkeypatch: pytest.MonkeyPatch, almacen: AlmacenFalso
) -> None:
    monkeypatch.setattr(router_analisis, "LIMITE_IMAGEN_BYTES", 10)
    respuesta = crear(cliente, contenido=JPG + b"x" * 20)
    assert respuesta.status_code == 413
    assert respuesta.json()["codigo"] == "ARCHIVO_DEMASIADO_GRANDE"
    assert almacen.archivos == {}
