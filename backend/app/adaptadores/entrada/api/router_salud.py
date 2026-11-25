"""Ruta de salud: estado del servicio y disponibilidad del modelo de IA."""

from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.adaptadores.salida.segmentacion.no_disponible import SegmentadorNoDisponible

router = APIRouter()


class SaludEsquema(BaseModel):
    """Respuesta de GET /salud."""

    estado: str
    modelo_disponible: bool


@router.get("/salud")
def salud(request: Request) -> SaludEsquema:
    """Indica que el servicio está activo y si hay un modelo de segmentación cargado."""
    segmentador = getattr(request.app.state, "segmentador", None)
    disponible = segmentador is not None and not isinstance(segmentador, SegmentadorNoDisponible)
    return SaludEsquema(estado="ok", modelo_disponible=disponible)
