"""Caso de uso: quitar la región excluida."""

from uuid import UUID

from app.aplicacion.puertos import RepositorioAnalisis
from app.dominio.errores import AnalisisNoEncontrado


class QuitarRegionExcluida:
    """Elimina la región excluida; es idempotente."""

    def __init__(self, repositorio: RepositorioAnalisis) -> None:
        self._repositorio = repositorio

    def ejecutar(self, id: UUID) -> None:
        """Quita la región (si no hay, no falla) y guarda el agregado."""
        analisis = self._repositorio.obtener(id)
        if analisis is None:
            raise AnalisisNoEncontrado(str(id))
        analisis.quitar_region_excluida()
        self._repositorio.guardar(analisis)
