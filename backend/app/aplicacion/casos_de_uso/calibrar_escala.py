"""Caso de uso: calibrar la escala de un análisis."""

from uuid import UUID

from app.aplicacion.puertos import RepositorioAnalisis
from app.dominio.errores import AnalisisNoEncontrado
from app.dominio.modelo import Analisis, Punto


class CalibrarEscala:
    """Fija la línea de calibración y su longitud real."""

    def __init__(self, repositorio: RepositorioAnalisis) -> None:
        self._repositorio = repositorio

    def ejecutar(self, id: UUID, inicio: Punto, fin: Punto, longitud_mm: float) -> Analisis:
        """Calibra el agregado y lo guarda."""
        analisis = self._repositorio.obtener(id)
        if analisis is None:
            raise AnalisisNoEncontrado(str(id))
        analisis.calibrar(inicio, fin, longitud_mm)
        self._repositorio.guardar(analisis)
        return analisis
