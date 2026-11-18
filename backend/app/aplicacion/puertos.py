"""Puertos: Segmentador, RepositorioAnalisis, AlmacenImagenes e InspectorImagenes."""
from typing import Protocol
from uuid import UUID

from app.dominio.modelo import Analisis, Poligono


class Segmentador(Protocol):
    """Segmenta una imagen en polígonos de fragmentos (en píxeles). Solo se declara."""

    def segmentar(self, imagen: bytes) -> list[Poligono]: ...


class RepositorioAnalisis(Protocol):
    """Persistencia del agregado `Analisis`."""

    def guardar(self, analisis: Analisis) -> None: ...

    def obtener(self, id: UUID) -> Analisis | None: ...

    def listar(self) -> list[Analisis]: ...

    def eliminar(self, id: UUID) -> None: ...


class AlmacenImagenes(Protocol):
    """Almacenamiento de los archivos de imagen."""

    def guardar(self, contenido: bytes, extension: str) -> str:
        """Guarda el contenido y devuelve la ruta relativa."""
        ...

    def leer(self, ruta: str) -> bytes: ...

    def eliminar(self, ruta: str) -> None: ...


class InspectorImagenes(Protocol):
    """Detecta formato y dimensiones por el contenido del archivo."""

    def inspeccionar(self, contenido: bytes) -> tuple[str, int, int]:
        """Devuelve (formato "JPG"|"PNG", ancho_px, alto_px).

        Lanza `FormatoImagenNoValido` si el contenido no es una imagen JPG o PNG.
        """
        ...
