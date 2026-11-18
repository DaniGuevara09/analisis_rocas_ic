"""Rutas de calibración y región excluida (docs/api.md)."""
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response

from app.adaptadores.entrada.api.dependencias import (
    caso_calibrar,
    caso_excluir_region,
    caso_quitar_region,
)
from app.adaptadores.entrada.api.esquemas import (
    AnalisisDetalle,
    CalibracionRespuesta,
    CalibracionSolicitud,
    RegionExcluidaSolicitud,
    a_detalle,
)
from app.aplicacion.casos_de_uso.calibrar_escala import CalibrarEscala
from app.aplicacion.casos_de_uso.excluir_region import ExcluirRegion
from app.aplicacion.casos_de_uso.quitar_region_excluida import QuitarRegionExcluida
from app.dominio.modelo import Punto

router = APIRouter(prefix="/analisis/{id}")


@router.put("/calibracion")
def calibrar(
    id: UUID,
    cuerpo: CalibracionSolicitud,
    caso: Annotated[CalibrarEscala, Depends(caso_calibrar)],
) -> CalibracionRespuesta:
    """Calibra la escala con una línea sobre el objeto de referencia."""
    analisis = caso.ejecutar(
        id,
        Punto(cuerpo.inicio.x, cuerpo.inicio.y),
        Punto(cuerpo.fin.x, cuerpo.fin.y),
        cuerpo.longitud_real_mm,
    )
    return CalibracionRespuesta(
        factor_mm_por_px=analisis.factor_mm_por_px(), estado=analisis.estado.value
    )


@router.put("/region-excluida")
def excluir_region(
    id: UUID,
    cuerpo: RegionExcluidaSolicitud,
    caso: Annotated[ExcluirRegion, Depends(caso_excluir_region)],
) -> AnalisisDetalle:
    """Marca la región del objeto de escala que no se cuenta."""
    puntos = [Punto(p.x, p.y) for p in cuerpo.poligono]
    return a_detalle(caso.ejecutar(id, puntos))


@router.delete("/region-excluida", status_code=204)
def quitar_region(
    id: UUID, caso: Annotated[QuitarRegionExcluida, Depends(caso_quitar_region)]
) -> Response:
    """Quita la región excluida (idempotente)."""
    caso.ejecutar(id)
    return Response(status_code=204)
