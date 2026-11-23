"""Almacén de imágenes en un bucket compatible con S3 (Cloudflare R2)."""

import re
from pathlib import Path
from typing import Any
from uuid import uuid4

import boto3  # type: ignore[import-not-found]
from botocore.config import Config
from botocore.exceptions import ClientError

PATRON_CLAVE = re.compile(
    r"^imagenes/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\.(jpg|png)$"
)
TIPOS_CONTENIDO = {"jpg": "image/jpeg", "png": "image/png"}
CODIGOS_NO_EXISTE = {"NoSuchKey", "404", "NotFound"}
LIMITE_CACHE_ARCHIVOS = 40


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
    """Implementa `AlmacenImagenes`: objetos `imagenes/<uuid>.<ext>` con caché local opcional."""

    def __init__(
        self, cliente: Any, bucket: str, carpeta_cache: str | None = None
    ) -> None:
        self._cliente = cliente
        self._bucket = bucket
        self._cache = Path(carpeta_cache) if carpeta_cache else None

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
        self._guardar_en_cache(clave, contenido)
        return clave

    def leer(self, clave: str) -> bytes:
        """Devuelve el objeto desde caché local o lo descarga de S3/R2."""
        self._validar(clave)
        en_cache = self._leer_de_cache(clave)
        if en_cache is not None:
            return en_cache
        try:
            respuesta = self._cliente.get_object(Bucket=self._bucket, Key=clave)
        except ClientError as error:
            if error.response.get("Error", {}).get("Code") in CODIGOS_NO_EXISTE:
                raise FileNotFoundError(clave) from error
            raise
        datos: bytes = respuesta["Body"].read()
        self._guardar_en_cache(clave, datos)
        return datos

    def eliminar(self, clave: str) -> None:
        """Elimina el objeto en S3 y en caché local; S3 no falla si ya no existe."""
        self._validar(clave)
        self._cliente.delete_object(Bucket=self._bucket, Key=clave)
        ruta = self._ruta_cache(clave)
        if ruta is not None:
            try:
                ruta.unlink(missing_ok=True)
            except OSError:
                pass

    def _ruta_cache(self, clave: str) -> Path | None:
        if self._cache is None:
            return None
        return self._cache / Path(clave).name

    def _leer_de_cache(self, clave: str) -> bytes | None:
        ruta = self._ruta_cache(clave)
        if ruta is None or not ruta.is_file():
            return None
        try:
            return ruta.read_bytes()
        except OSError:
            return None

    def _guardar_en_cache(self, clave: str, contenido: bytes) -> None:
        ruta = self._ruta_cache(clave)
        if ruta is None or self._cache is None:
            return
        try:
            self._cache.mkdir(parents=True, exist_ok=True)
            ruta.write_bytes(contenido)
            archivos = sorted(
                (p for p in self._cache.iterdir() if p.is_file()),
                key=lambda p: p.stat().st_mtime,
            )
            for viejo in archivos[:-LIMITE_CACHE_ARCHIVOS]:
                viejo.unlink(missing_ok=True)
        except OSError:
            pass

    @staticmethod
    def _validar(clave: str) -> None:
        if not PATRON_CLAVE.fullmatch(clave):
            raise ValueError("Clave de imagen no valida")
