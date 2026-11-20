"""Almacén de imágenes en un bucket compatible con S3 (Cloudflare R2)."""

import re
from typing import Any
from uuid import uuid4

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

PATRON_CLAVE = re.compile(
    r"^imagenes/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\.(jpg|png)$"
)
TIPOS_CONTENIDO = {"jpg": "image/jpeg", "png": "image/png"}
CODIGOS_NO_EXISTE = {"NoSuchKey", "404", "NotFound"}


def crear_cliente_s3(
    endpoint_url: str, access_key_id: str, secret_access_key: str, region: str
) -> Any:
    """Crea el cliente boto3. Para R2: región "auto" y endpoint de la cuenta."""
    return boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        aws_access_key_id=access_key_id,
        aws_secret_access_key=secret_access_key,
        region_name=region,
        config=Config(signature_version="s3v4"),
    )


class AlmacenImagenesS3:
    """Implementa `AlmacenImagenes`: objetos `imagenes/<uuid>.<ext>` en un bucket privado."""

    def __init__(self, cliente: Any, bucket: str) -> None:
        self._cliente = cliente
        self._bucket = bucket

    def guardar(self, contenido: bytes, extension: str) -> str:
        """Sube el contenido y devuelve la clave del objeto."""
        extension = extension.lower()
        if extension not in TIPOS_CONTENIDO:
            raise ValueError(f"Extension no soportada: {extension}")
        clave = f"imagenes/{uuid4()}.{extension}"
        self._cliente.put_object(
            Bucket=self._bucket,
            Key=clave,
            Body=contenido,
            ContentType=TIPOS_CONTENIDO[extension],
        )
        return clave

    def leer(self, clave: str) -> bytes:
        """Descarga el objeto; si no existe lanza `FileNotFoundError`."""
        self._validar(clave)
        try:
            respuesta = self._cliente.get_object(Bucket=self._bucket, Key=clave)
        except ClientError as error:
            if error.response.get("Error", {}).get("Code") in CODIGOS_NO_EXISTE:
                raise FileNotFoundError(clave) from error
            raise
        return respuesta["Body"].read()

    def eliminar(self, clave: str) -> None:
        """Elimina el objeto; S3 no falla si ya no existe."""
        self._validar(clave)
        self._cliente.delete_object(Bucket=self._bucket, Key=clave)

    @staticmethod
    def _validar(clave: str) -> None:
        if not PATRON_CLAVE.fullmatch(clave):
            raise ValueError("Clave de imagen no valida")
