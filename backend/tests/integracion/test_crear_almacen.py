"""Pruebas de la composición del almacén según la configuración."""

import pytest
from pydantic import ValidationError

from app.adaptadores.salida.almacenamiento.almacen_s3 import AlmacenImagenesS3
from app.adaptadores.salida.almacenamiento.archivos_local import AlmacenArchivosLocal
from app.config import Configuracion
from app.main import crear_almacen

S3 = {
    "almacen_imagenes": "s3",
    "s3_endpoint_url": "https://cuenta.r2.cloudflarestorage.com",
    "s3_bucket": "rocas",
    "s3_access_key_id": "id-de-acceso",
    "s3_secret_access_key": "SECRETO-MUY-SECRETO",
}


def _config(**valores: str) -> Configuracion:
    return Configuracion(_env_file=None, **valores)  # type: ignore[arg-type]


def test_por_defecto_es_local() -> None:
    config = _config(ruta_imagenes="/tmp/imagenes")
    assert config.almacen_imagenes == "local"
    assert isinstance(crear_almacen(config), AlmacenArchivosLocal)


def test_s3_con_todos_los_valores() -> None:
    config = _config(**S3)
    assert config.s3_region == "auto"
    assert isinstance(crear_almacen(config), AlmacenImagenesS3)


@pytest.mark.parametrize(
    "faltante", ["s3_endpoint_url", "s3_bucket", "s3_access_key_id", "s3_secret_access_key"]
)
def test_s3_incompleto_falla_nombrando_la_variable(faltante: str) -> None:
    valores = {**S3, faltante: ""}
    with pytest.raises(ValidationError) as error:
        _config(**valores)
    assert faltante.upper() in str(error.value)


def test_el_error_no_imprime_secretos() -> None:
    with pytest.raises(ValidationError) as error:
        _config(**{**S3, "s3_bucket": ""})
    texto = str(error.value)
    assert "SECRETO-MUY-SECRETO" not in texto
    assert "id-de-acceso" not in texto


def test_local_no_exige_valores_s3() -> None:
    assert _config(almacen_imagenes="local").s3_bucket == ""
