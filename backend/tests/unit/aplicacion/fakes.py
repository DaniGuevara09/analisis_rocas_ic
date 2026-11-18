"""Adaptadores falsos en memoria para probar los casos de uso."""
from uuid import UUID

from app.dominio.errores import FormatoImagenNoValido
from app.dominio.modelo import Analisis

CABECERA_JPG = b"\xff\xd8\xff"
CABECERA_PNG = b"\x89PNG"


class RepositorioFalso:
    """Repositorio en memoria; `fallar_al_guardar` simula un error de persistencia."""

    def __init__(self) -> None:
        self.datos: dict[UUID, Analisis] = {}
        self.fallar_al_guardar = False

    def guardar(self, analisis: Analisis) -> None:
        if self.fallar_al_guardar:
            raise RuntimeError("fallo de persistencia simulado")
        self.datos[analisis.id] = analisis

    def obtener(self, id: UUID) -> Analisis | None:
        return self.datos.get(id)

    def listar(self) -> list[Analisis]:
        return list(self.datos.values())

    def eliminar(self, id: UUID) -> None:
        self.datos.pop(id, None)


class AlmacenFalso:
    """Almacén en memoria con rutas secuenciales."""

    def __init__(self) -> None:
        self.archivos: dict[str, bytes] = {}
        self._contador = 0

    def guardar(self, contenido: bytes, extension: str) -> str:
        self._contador += 1
        ruta = f"{self._contador}.{extension}"
        self.archivos[ruta] = contenido
        return ruta

    def leer(self, ruta: str) -> bytes:
        return self.archivos[ruta]

    def eliminar(self, ruta: str) -> None:
        self.archivos.pop(ruta, None)


class InspectorFalso:
    """Reconoce JPG y PNG por su cabecera y devuelve dimensiones fijas (640x480 por defecto)."""

    def __init__(self, ancho_px: int = 640, alto_px: int = 480) -> None:
        self._ancho_px = ancho_px
        self._alto_px = alto_px

    def inspeccionar(self, contenido: bytes) -> tuple[str, int, int]:
        if contenido.startswith(CABECERA_JPG):
            return "JPG", self._ancho_px, self._alto_px
        if contenido.startswith(CABECERA_PNG):
            return "PNG", self._ancho_px, self._alto_px
        raise FormatoImagenNoValido("No es JPG ni PNG")
