"""Almacén de imágenes en el sistema de archivos local."""
from pathlib import Path
from uuid import uuid4


class AlmacenArchivosLocal:
    """Implementa `AlmacenImagenes`: archivos `<uuid>.<ext>` bajo una carpeta base."""

    def __init__(self, carpeta_base: str) -> None:
        self._base = Path(carpeta_base)

    def guardar(self, contenido: bytes, extension: str) -> str:
        """Guarda el contenido y devuelve la ruta relativa a la carpeta base."""
        self._base.mkdir(parents=True, exist_ok=True)
        ruta = f"{uuid4()}.{extension.lower()}"
        (self._base / ruta).write_bytes(contenido)
        return ruta

    def leer(self, ruta: str) -> bytes:
        """Lee el archivo guardado en esa ruta relativa."""
        return self._resolver(ruta).read_bytes()

    def eliminar(self, ruta: str) -> None:
        """Elimina el archivo; si ya no existe, no hace nada."""
        self._resolver(ruta).unlink(missing_ok=True)

    def _resolver(self, ruta: str) -> Path:
        completa = (self._base / ruta).resolve()
        if not completa.is_relative_to(self._base.resolve()):
            raise ValueError("Ruta fuera de la carpeta de imagenes")
        return completa
