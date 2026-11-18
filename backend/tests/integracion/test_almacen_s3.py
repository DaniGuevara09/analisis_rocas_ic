"""Pruebas del almacén S3/R2 con moto (sin red)."""
import re
from collections.abc import Iterator
from typing import Any

import boto3
import pytest
from moto import mock_aws

from app.adaptadores.salida.almacenamiento.almacen_s3 import (
    AlmacenImagenesS3,
    crear_cliente_s3,
)

BUCKET = "rocas-prueba"
PATRON = re.compile(
    r"^imagenes/[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[0-9a-f]{4}-[0-9a-f]{12}\.(jpg|png)$"
)
CLAVE_VALIDA = "imagenes/3f2b8c1e-5d4a-4b7e-9c1d-0a1b2c3d4e5f.jpg"


@pytest.fixture
def cliente() -> Iterator[Any]:
    with mock_aws():
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket=BUCKET)
        yield s3


@pytest.fixture
def almacen(cliente: Any) -> AlmacenImagenesS3:
    return AlmacenImagenesS3(cliente, BUCKET)


def test_guardar_y_leer_ida_y_vuelta(almacen: AlmacenImagenesS3) -> None:
    clave = almacen.guardar(b"contenido", "jpg")
    assert almacen.leer(clave) == b"contenido"


def test_clave_cumple_el_patron_y_extension_en_minuscula(almacen: AlmacenImagenesS3) -> None:
    assert PATRON.match(almacen.guardar(b"x", "JPG"))
    assert PATRON.match(almacen.guardar(b"x", "png"))


def test_guardar_usa_content_type_segun_extension(almacen: AlmacenImagenesS3, cliente: Any) -> None:
    jpg = almacen.guardar(b"x", "JPG")
    png = almacen.guardar(b"x", "PNG")
    assert cliente.head_object(Bucket=BUCKET, Key=jpg)["ContentType"] == "image/jpeg"
    assert cliente.head_object(Bucket=BUCKET, Key=png)["ContentType"] == "image/png"


def test_guardar_rechaza_extension_no_soportada(almacen: AlmacenImagenesS3) -> None:
    with pytest.raises(ValueError):
        almacen.guardar(b"x", "gif")


def test_leer_inexistente_lanza_file_not_found(almacen: AlmacenImagenesS3) -> None:
    with pytest.raises(FileNotFoundError):
        almacen.leer(CLAVE_VALIDA)


def test_eliminar_borra_el_objeto(almacen: AlmacenImagenesS3) -> None:
    clave = almacen.guardar(b"x", "png")
    almacen.eliminar(clave)
    with pytest.raises(FileNotFoundError):
        almacen.leer(clave)


def test_eliminar_inexistente_no_falla(almacen: AlmacenImagenesS3) -> None:
    almacen.eliminar(CLAVE_VALIDA)


@pytest.mark.parametrize(
    "clave",
    [
        "../secreto.txt",
        "imagenes/../x.jpg",
        "x.jpg",
        "imagenes/no-es-uuid.jpg",
        "imagenes/3f2b8c1e-5d4a-4b7e-9c1d-0a1b2c3d4e5f.gif",
        "imagenes/3f2b8c1e-5d4a-4b7e-9c1d-0a1b2c3d4e5f.jpg/extra",
        "otra/3f2b8c1e-5d4a-4b7e-9c1d-0a1b2c3d4e5f.jpg",
        "",
    ],
)
def test_claves_invalidas_lanzan_value_error(almacen: AlmacenImagenesS3, clave: str) -> None:
    for operacion in (almacen.leer, almacen.eliminar):
        with pytest.raises(ValueError):
            operacion(clave)


def test_otro_error_de_s3_se_propaga(cliente: Any) -> None:
    from botocore.exceptions import ClientError

    almacen = AlmacenImagenesS3(cliente, "bucket-que-no-existe")
    with pytest.raises(ClientError):
        almacen.leer(CLAVE_VALIDA)


def test_crear_cliente_s3_configura_endpoint_y_region() -> None:
    cliente = crear_cliente_s3(
        "https://cuenta.r2.cloudflarestorage.com", "id", "secreto", "auto"
    )
    assert cliente.meta.endpoint_url == "https://cuenta.r2.cloudflarestorage.com"
    assert cliente.meta.region_name == "auto"
