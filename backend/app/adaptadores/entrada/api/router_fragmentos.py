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
from app.adaptadores.entrada.api.exportacion_xlsx import generar_xlsx
from app.aplicacion.casos_de_uso.editar_fragmentos import EditarFragmentos, FragmentoEditado
from app.aplicacion.casos_de_uso.obtener_analisis import ObtenerAnalisis
from app.aplicacion.casos_de_uso.obtener_resultados import ObtenerResultados
from app.aplicacion.casos_de_uso.segmentar_analisis import SegmentarAnalisis
from app.dominio.modelo import OrigenFragmento, Punto

BOM_UTF8 = "\ufeff"  # marca de orden de bytes: Excel detecta UTF-8 por ella

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


def _descarga(contenido: bytes, tipo: str, nombre_archivo: str) -> Response:
    archivo = quote(nombre_archivo)
    return Response(
        content=contenido,
        media_type=tipo,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{archivo}"},
    )


@router.get("/resultados.csv")
def resultados_csv(
    id: UUID, caso: Annotated[ObtenerResultados, Depends(caso_resultados)]
) -> Response:
    """CSV estándar ("," y punto decimal) con una fila por fragmento."""
    analisis, reporte = caso.ejecutar_con_analisis(id)
    contenido = (BOM_UTF8 + generar_csv(analisis, reporte)).encode("utf-8")
    return _descarga(contenido, "text/csv; charset=utf-8", f"granulometria_{analisis.nombre}.csv")


@router.get("/resultados.xlsx")
def resultados_xlsx(
    id: UUID, caso: Annotated[ObtenerResultados, Depends(caso_resultados)]
) -> Response:
    """Informe Excel: hojas Resumen (indicadores y supuestos), Curva y Fragmentos."""
    analisis, reporte = caso.ejecutar_con_analisis(id)
    return _descarga(
        generar_xlsx(analisis, reporte),
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        f"granulometria_{analisis.nombre}.xlsx",
    )
