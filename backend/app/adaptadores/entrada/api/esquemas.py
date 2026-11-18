"""Esquemas Pydantic de la API (ver docs/api.md)."""
from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.dominio.modelo import Analisis, Fragmento, Poligono

Coordenada = Annotated[float, Field(allow_inf_nan=False)]
LongitudMm = Annotated[float, Field(allow_inf_nan=False)]


class PuntoEsquema(BaseModel):
    """Punto en píxeles (coordenadas finitas)."""

    x: Coordenada
    y: Coordenada


class ImagenEsquema(BaseModel):
    """Datos de la imagen del análisis."""

    url: str
    ancho_px: int
    alto_px: int
    formato: Literal["JPG", "PNG"]


class CalibracionEsquema(BaseModel):
    """Calibración de la escala."""

    inicio: PuntoEsquema
    fin: PuntoEsquema
    longitud_real_mm: float
    factor_mm_por_px: float


class RegionExcluidaEsquema(BaseModel):
    """Región excluida del conteo."""

    poligono: list[PuntoEsquema]


class FragmentoEsquema(BaseModel):
    """Fragmento con su diámetro equivalente (null si no hay calibración)."""

    id: UUID
    poligono: list[PuntoEsquema]
    origen: Literal["MODELO", "MANUAL"]
    diametro_equivalente_mm: float | None


class AnalisisResumen(BaseModel):
    """Resumen de un análisis para listados."""

    id: UUID
    nombre: str
    fecha_creacion: datetime
    estado: str
    numero_fragmentos: int


class AnalisisDetalle(AnalisisResumen):
    """Análisis completo."""

    imagen: ImagenEsquema
    calibracion: CalibracionEsquema | None
    region_excluida: RegionExcluidaEsquema | None
    fragmentos: list[FragmentoEsquema]


class CalibracionSolicitud(BaseModel):
    """Cuerpo de PUT /analisis/{id}/calibracion."""

    inicio: PuntoEsquema
    fin: PuntoEsquema
    longitud_real_mm: LongitudMm


class CalibracionRespuesta(BaseModel):
    """Resultado de calibrar."""

    factor_mm_por_px: float
    estado: str


class RegionExcluidaSolicitud(BaseModel):
    """Cuerpo de PUT /analisis/{id}/region-excluida."""

    poligono: list[PuntoEsquema]


class RenombrarSolicitud(BaseModel):
    """Cuerpo de PATCH /analisis/{id}."""

    nombre: str


def _puntos(poligono: Poligono) -> list[PuntoEsquema]:
    return [PuntoEsquema(x=p.x, y=p.y) for p in poligono.puntos]


def a_resumen(analisis: Analisis) -> AnalisisResumen:
    """Convierte el agregado en su resumen."""
    return AnalisisResumen(
        id=analisis.id,
        nombre=analisis.nombre,
        fecha_creacion=analisis.fecha_creacion,
        estado=analisis.estado.value,
        numero_fragmentos=len(analisis.fragmentos),
    )


def a_detalle(analisis: Analisis) -> AnalisisDetalle:
    """Convierte el agregado en su detalle."""
    calibracion = analisis.calibracion
    factor = calibracion.factor_mm_por_px() if calibracion else None

    def fragmento(f: Fragmento) -> FragmentoEsquema:
        return FragmentoEsquema(
            id=f.id,
            poligono=_puntos(f.poligono),
            origen=f.origen.value,  # type: ignore[arg-type]
            diametro_equivalente_mm=None if factor is None else f.diametro_equivalente_mm(factor),
        )

    return AnalisisDetalle(
        **a_resumen(analisis).model_dump(),
        imagen=ImagenEsquema(
            url=f"/api/analisis/{analisis.id}/imagen",
            ancho_px=analisis.imagen.ancho_px,
            alto_px=analisis.imagen.alto_px,
            formato=analisis.imagen.formato,  # type: ignore[arg-type]
        ),
        calibracion=None
        if calibracion is None
        else CalibracionEsquema(
            inicio=PuntoEsquema(x=calibracion.inicio.x, y=calibracion.inicio.y),
            fin=PuntoEsquema(x=calibracion.fin.x, y=calibracion.fin.y),
            longitud_real_mm=calibracion.longitud_real_mm,
            factor_mm_por_px=calibracion.factor_mm_por_px(),
        ),
        region_excluida=None
        if analisis.region_excluida is None
        else RegionExcluidaEsquema(poligono=_puntos(analisis.region_excluida.poligono)),
        fragmentos=[fragmento(f) for f in analisis.fragmentos],
    )
