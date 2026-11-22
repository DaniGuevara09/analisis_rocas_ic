"""Caso de uso: segmentar una zona pintada con el pincel mágico."""

from uuid import UUID

from app.aplicacion.puertos import AlmacenImagenes, RepositorioAnalisis, Segmentador
from app.dominio.errores import AnalisisNoEncontrado, DatosNoValidos
from app.dominio.modelo import Poligono, Punto


class SegmentarZonaPincel:
    """Segmenta con IA el fragmento bajo el trazo del pincel mágico."""

    def __init__(
        self,
        repositorio: RepositorioAnalisis,
        almacen: AlmacenImagenes,
        segmentador: Segmentador,
    ) -> None:
        self._repositorio = repositorio
        self._almacen = almacen
        self._segmentador = segmentador

    def ejecutar(self, id: UUID, trazo: list[Punto], radio_px: float) -> Poligono | None:
        """Ejecuta la segmentación localizada en la región pintada."""
        if not trazo:
            raise DatosNoValidos("El trazo del pincel no puede estar vacio")
        analisis = self._repositorio.obtener(id)
        if analisis is None:
            raise AnalisisNoEncontrado(str(id))
        analisis.factor_mm_por_px()
        imagen = self._almacen.leer(analisis.imagen.ruta)
        return self._segmentador.segmentar_zona(imagen, trazo, max(2.0, radio_px))
