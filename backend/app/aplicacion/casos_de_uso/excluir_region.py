"""Caso de uso: marcar la región del objeto de escala que se excluye."""

from collections.abc import Sequence
from uuid import UUID

from app.aplicacion.puertos import RepositorioAnalisis
from app.dominio.errores import AnalisisNoEncontrado
from app.dominio.modelo import Analisis, Poligono, Punto


class ExcluirRegion:
    """Fija la región excluida a partir de los vértices del polígono."""

    def __init__(self, repositorio: RepositorioAnalisis) -> None:
        self._repositorio = repositorio

    def ejecutar(self, id: UUID, puntos: Sequence[Punto]) -> Analisis:
        """Excluye la región y guarda el agregado."""
        analisis = self._repositorio.obtener(id)
        if analisis is None:
            raise AnalisisNoEncontrado(str(id))
        analisis.excluir_region(Poligono(tuple(puntos)))
        self._repositorio.guardar(analisis)
        return analisis
