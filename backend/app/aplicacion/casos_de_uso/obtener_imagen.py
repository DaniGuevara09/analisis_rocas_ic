"""Caso de uso: obtener el archivo de imagen de un análisis."""

from uuid import UUID

from app.aplicacion.puertos import AlmacenImagenes, RepositorioAnalisis
from app.dominio.errores import AnalisisNoEncontrado


class ObtenerImagen:
    """Devuelve el contenido y el formato de la imagen."""

    def __init__(self, repositorio: RepositorioAnalisis, almacen: AlmacenImagenes) -> None:
        self._repositorio = repositorio
        self._almacen = almacen

    def ejecutar(self, id: UUID) -> tuple[bytes, str]:
        """Devuelve (contenido, formato "JPG"|"PNG")."""
        analisis = self._repositorio.obtener(id)
        if analisis is None:
            raise AnalisisNoEncontrado(str(id))
        return self._almacen.leer(analisis.imagen.ruta), analisis.imagen.formato
