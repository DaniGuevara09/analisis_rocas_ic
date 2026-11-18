"""Segmentador que se usa cuando el modelo no se pudo cargar (por ejemplo, falta best.pt)."""
from app.aplicacion.errores import ModeloNoDisponible
from app.dominio.modelo import Poligono


class SegmentadorNoDisponible:
    """Implementa el puerto `Segmentador` lanzando siempre `ModeloNoDisponible`."""

    def __init__(self, motivo: str) -> None:
        self._motivo = motivo

    def segmentar(self, imagen: bytes) -> list[Poligono]:
        """Informa que la segmentación no está disponible."""
        raise ModeloNoDisponible(self._motivo)
