"""Rutas de segmentación, edición de fragmentos y resultados (docs/api.md)."""

from typing import Annotated
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Depends, Response

from app.adaptadores.entrada.api.dependencias import (
    caso_editar_fragmentos,
    caso_obtener,
    caso_pincel_magico,
    caso_resultados,
    caso_segmentar,
)
from app.adaptadores.entrada.api.esquemas import (
    FragmentoEsquema,
    FragmentosSolicitud,
    PincelMagicoRespuesta,
    PincelMagicoSolicitud,
    PuntoEsquema,
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
from app.aplicacion.casos_de_uso.segmentar_zona_pincel import SegmentarZonaPincel
from app.dominio.modelo import OrigenFragmento, Punto

BOM_UTF8 = "\ufeff"  # marca de orden de bytes: Excel detecta UTF-8 por ella

router = APIRouter(prefix="/analisis/{id}")


# `def` (no `async def`): FastAPI la ejecuta en el threadpool y la inferencia no bloquea.
@router.post("/segmentacion")
def segmentar(
    id: UUID,
    caso: Annotated[SegmentarAnalisis, Depends(caso_segmentar)],
) -> list[FragmentoEsquema]:
    """Segmenta la imagen con el modelo y reemplaza los fragmentos."""
    analisis, fragmentos = caso.ejecutar_con_analisis(id)
    return a_fragmentos(analisis, fragmentos)


@router.post("/pincel-magico")
def pincel_magico(
    id: UUID,
    cuerpo: PincelMagicoSolicitud,
    caso: Annotated[SegmentarZonaPincel, Depends(caso_pincel_magico)],
) -> PincelMagicoRespuesta:
    """Segmenta con IA la zona pintada con el pincel mágico."""
    puntos = [Punto(p.x, p.y) for p in cuerpo.trazo]
    poligono = caso.ejecutar(id, puntos, cuerpo.radio_px)
    return PincelMagicoRespuesta(
        poligono=None
        if poligono is None
        else [PuntoEsquema(x=p.x, y=p.y) for p in poligono.puntos]
    )


@router.put("/fragmentos")
def editar_fragmentos(
    id: UUID,
    cuerpo: FragmentosSolicitud,
    caso: Annotated[EditarFragmentos, Depends(caso_editar_fragmentos)],
    obtener: Annotated[ObtenerAnalisis, Depends(caso_obtener)],
) -> list[FragmentoEsquema]:
    """Reemplaza la lista completa de fragmentos editada por el operador."""
    analisis_actual = obtener.ejecutar(id)
    ancho_max = float(analisis_actual.imagen.ancho_px)
    alto_max = float(analisis_actual.imagen.alto_px)
    editados = [
        FragmentoEditado(
            id=f.id,
            puntos=[
                Punto(
                    min(max(float(p.x), 0.0), ancho_max),
                    min(max(float(p.y), 0.0), alto_max),
                )
                for p in f.poligono
            ],
            origen=OrigenFragmento(f.origen),
        )
        for f in cuerpo.fragmentos
        if len(f.poligono) >= 3
    ]
    analisis, fragmentos = caso.ejecutar_con_analisis(id, editados)
    return a_fragmentos(analisis, fragmentos)


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
