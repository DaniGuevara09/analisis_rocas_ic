"""Segmentador que se usa cuando el modelo no se pudo cargar (por ejemplo, falta best.pt)."""

import io

from PIL import Image

from app.adaptadores.salida.segmentacion.pincel import segmentar_recorte_grabcut
from app.aplicacion.errores import ModeloNoDisponible
from app.dominio.modelo import Poligono, Punto


class SegmentadorNoDisponible:
    """Implementa el puerto `Segmentador` lanzando `ModeloNoDisponible` en segmentación completa."""

    def __init__(self, motivo: str) -> None:
        self._motivo = motivo

    def segmentar(self, imagen: bytes) -> list[Poligono]:
        """Informa que la segmentación completa no está disponible."""
        raise ModeloNoDisponible(self._motivo)

    def segmentar_zona(
        self, imagen: bytes, trazo: list[Punto], radio_px: float
    ) -> Poligono | None:
        """Usa segmentación asistida por bordes (GrabCut) sobre la zona pintada."""
        foto = Image.open(io.BytesIO(imagen)).convert("RGB")
        return segmentar_recorte_grabcut(foto, trazo, radio_px)
