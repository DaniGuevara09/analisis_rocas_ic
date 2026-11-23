"""Caso de uso: segmentar automáticamente la imagen de un análisis (HU-04)."""

from uuid import UUID

from app.aplicacion.puertos import AlmacenImagenes, RepositorioAnalisis, Segmentador
from app.dominio.errores import AnalisisNoEncontrado
from app.dominio.modelo import Analisis, Fragmento, OrigenFragmento


class SegmentarAnalisis:
    """Ejecuta el segmentador y registra los fragmentos con origen MODELO."""

    def __init__(
        self,
        repositorio: RepositorioAnalisis,
        almacen: AlmacenImagenes,
        segmentador: Segmentador,
    ) -> None:
        self._repositorio = repositorio
        self._almacen = almacen
        self._segmentador = segmentador

    def ejecutar(self, id: UUID) -> list[Fragmento]:
        """Segmenta, reemplaza los fragmentos y guarda. Exige calibración antes de inferir."""
        _, fragmentos = self.ejecutar_con_analisis(id)
        return fragmentos

    def ejecutar_con_analisis(self, id: UUID) -> tuple[Analisis, list[Fragmento]]:
        """Como `ejecutar`, devolviendo también el agregado ya cargado para evitar relecturas."""
        analisis = self._repositorio.obtener(id)
        if analisis is None:
            raise AnalisisNoEncontrado(str(id))
        analisis.factor_mm_por_px()
        imagen = self._almacen.leer(analisis.imagen.ruta)
        poligonos = self._segmentador.segmentar(imagen)
        fragmentos = analisis.registrar_fragmentos(poligonos, OrigenFragmento.MODELO)
        self._repositorio.guardar(analisis)
        return analisis, fragmentos
