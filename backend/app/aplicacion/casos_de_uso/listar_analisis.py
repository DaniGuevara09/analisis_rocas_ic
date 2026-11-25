"""Caso de uso: listar los análisis."""

from app.aplicacion.puertos import RepositorioAnalisis
from app.dominio.modelo import Analisis


class ListarAnalisis:
    """Devuelve los análisis, el más reciente primero."""

    def __init__(self, repositorio: RepositorioAnalisis) -> None:
        self._repositorio = repositorio

    def ejecutar(self) -> list[Analisis]:
        """Lista ordenada por fecha de creación descendente."""
        return sorted(self._repositorio.listar(), key=lambda a: a.fecha_creacion, reverse=True)
