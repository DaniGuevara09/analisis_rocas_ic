"""Caso de uso: calcular los resultados granulométricos de un análisis (HU-07, HU-08)."""
from uuid import UUID

from app.aplicacion.puertos import RepositorioAnalisis
from app.dominio.errores import AnalisisNoEncontrado
from app.dominio.modelo import ReporteGranulometrico


class ObtenerResultados:
    """Devuelve D20-D90, n, curva, histograma y el rango de cada fragmento."""

    def __init__(self, repositorio: RepositorioAnalisis) -> None:
        self._repositorio = repositorio

    def ejecutar(self, id: UUID) -> ReporteGranulometrico:
        """Calcula el reporte con la calibración y los fragmentos vigentes."""
        analisis = self._repositorio.obtener(id)
        if analisis is None:
            raise AnalisisNoEncontrado(str(id))
        return analisis.generar_reporte()
