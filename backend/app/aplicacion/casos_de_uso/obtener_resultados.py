"""Caso de uso: calcular los resultados granulométricos de un análisis (HU-07 a HU-09)."""

from uuid import UUID

from app.aplicacion.puertos import RepositorioAnalisis, RepositorioConfiguracion
from app.dominio.configuracion import CONFIGURACION_POR_DEFECTO
from app.dominio.errores import AnalisisNoEncontrado
from app.dominio.modelo import Analisis, ReporteGranulometrico


class ObtenerResultados:
    """Devuelve D20-D90, n, curva, histograma y el rango de cada fragmento."""

    def __init__(
        self,
        repositorio: RepositorioAnalisis,
        configuracion: RepositorioConfiguracion,
    ) -> None:
        self._repositorio = repositorio
        self._configuracion = configuracion

    def ejecutar(self, id: UUID) -> ReporteGranulometrico:
        """Calcula el reporte con la calibración, los fragmentos y los rangos vigentes."""
        return self.ejecutar_con_analisis(id)[1]

    def ejecutar_con_analisis(self, id: UUID) -> tuple[Analisis, ReporteGranulometrico]:
        """Igual que `ejecutar`, pero devuelve también el análisis (para exportar el CSV)."""
        analisis = self._repositorio.obtener(id)
        if analisis is None:
            raise AnalisisNoEncontrado(str(id))
        rangos = self._configuracion.obtener_rangos() or CONFIGURACION_POR_DEFECTO
        return analisis, analisis.generar_reporte(rangos)
