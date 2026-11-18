"""Caso de uso: obtener un análisis por id."""
from uuid import UUID

from app.aplicacion.puertos import RepositorioAnalisis
from app.dominio.errores import AnalisisNoEncontrado
from app.dominio.modelo import Analisis


class ObtenerAnalisis:
    """Busca un análisis o lanza `AnalisisNoEncontrado`."""

    def __init__(self, repositorio: RepositorioAnalisis) -> None:
        self._repositorio = repositorio

    def ejecutar(self, id: UUID) -> Analisis:
        """Devuelve el análisis con ese id."""
        analisis = self._repositorio.obtener(id)
        if analisis is None:
            raise AnalisisNoEncontrado(str(id))
        return analisis
