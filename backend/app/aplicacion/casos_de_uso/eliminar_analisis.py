"""Caso de uso: eliminar un análisis y su imagen."""
from uuid import UUID

from app.aplicacion.puertos import AlmacenImagenes, RepositorioAnalisis
from app.dominio.errores import AnalisisNoEncontrado


class EliminarAnalisis:
    """Borra el análisis de la base de datos y su imagen del almacén."""

    def __init__(self, repositorio: RepositorioAnalisis, almacen: AlmacenImagenes) -> None:
        self._repositorio = repositorio
        self._almacen = almacen

    def ejecutar(self, id: UUID) -> None:
        """Elimina el registro y luego el archivo de imagen."""
        analisis = self._repositorio.obtener(id)
        if analisis is None:
            raise AnalisisNoEncontrado(str(id))
        self._repositorio.eliminar(id)
        self._almacen.eliminar(analisis.imagen.ruta)
