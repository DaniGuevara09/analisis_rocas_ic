"""Rutas de segmentación, edición de fragmentos y resultados (docs/api.md)."""

from typing import Annotated
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Depends, Response

from app.adaptadores.entrada.api.dependencias import (
    caso_editar_fragmentos,
    caso_obtener,
    caso_resultados,
    caso_segmentar,
)
from app.adaptadores.entrada.api.esquemas import (
    FragmentoEsquema,
    FragmentosSolicitud,
    ResultadosEsquema,
    a_fragmentos,
    a_resultados,
)
from app.adaptadores.entrada.api.exportacion_csv import generar_csv
from app.aplicacion.casos_de_uso.editar_fragmentos import EditarFragmentos, FragmentoEditado
from app.aplicacion.casos_de_uso.obtener_analisis import ObtenerAnalisis
from app.aplicacion.casos_de_uso.obtener_resultados import ObtenerResultados
from app.aplicacion.casos_de_uso.segmentar_analisis import SegmentarAnalisis
from app.dominio.modelo import OrigenFragmento, Punto

router = APIRouter(prefix="/analisis/{id}")


# `def` (no `async def`): FastAPI la ejecuta en el threadpool y la inferencia no bloquea.
@router.post("/segmentacion")
def segmentar(
    id: UUID,
    caso: Annotated[SegmentarAnalisis, Depends(caso_segmentar)],
    obtener: Annotated[ObtenerAnalisis, Depends(caso_obtener)],
) -> list[FragmentoEsquema]:
    """Segmenta la imagen con el modelo y reemplaza los fragmentos."""
    fragmentos = caso.ejecutar(id)
    return a_fragmentos(obtener.ejecutar(id), fragmentos)


@router.put("/fragmentos")
def editar_fragmentos(
    id: UUID,
    cuerpo: FragmentosSolicitud,
    caso: Annotated[EditarFragmentos, Depends(caso_editar_fragmentos)],
    obtener: Annotated[ObtenerAnalisis, Depends(caso_obtener)],
) -> list[FragmentoEsquema]:
    """Reemplaza la lista completa de fragmentos editada por el operador."""
    editados = [
        FragmentoEditado(
            id=f.id,
            puntos=[Punto(p.x, p.y) for p in f.poligono],
            origen=OrigenFragmento(f.origen),
        )
        for f in cuerpo.fragmentos
    ]
    fragmentos = caso.ejecutar(id, editados)
    return a_fragmentos(obtener.ejecutar(id), fragmentos)


@router.get("/resultados")
def resultados(
    id: UUID, caso: Annotated[ObtenerResultados, Depends(caso_resultados)]
) -> ResultadosEsquema:
    """D20-D90, índice n, curva, histograma y rango de cada fragmento."""
    return a_resultados(caso.ejecutar(id))


@router.get("/resultados.csv")
def resultados_csv(
    id: UUID, caso: Annotated[ObtenerResultados, Depends(caso_resultados)]
) -> Response:
    """Descarga el CSV con indicadores, supuestos, rangos y el tamaño de cada fragmento."""
    analisis, reporte = caso.ejecutar_con_analisis(id)
    contenido = "\ufeff" + generar_csv(analisis, reporte)
    archivo = quote(f"granulometria_{analisis.nombre}.csv")
    return Response(
        content=contenido.encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{archivo}"},
    )
