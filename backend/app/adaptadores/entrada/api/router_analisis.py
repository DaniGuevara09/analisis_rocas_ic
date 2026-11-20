"""Rutas CRUD de análisis (docs/api.md)."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Form, Response, UploadFile

from app.adaptadores.entrada.api.dependencias import (
    caso_crear,
    caso_eliminar,
    caso_imagen,
    caso_listar,
    caso_obtener,
    caso_renombrar,
)
from app.adaptadores.entrada.api.errores import ArchivoDemasiadoGrande
from app.adaptadores.entrada.api.esquemas import (
    AnalisisDetalle,
    AnalisisResumen,
    RenombrarSolicitud,
    a_detalle,
    a_resumen,
)
from app.aplicacion.casos_de_uso.crear_analisis import CrearAnalisis
from app.aplicacion.casos_de_uso.eliminar_analisis import EliminarAnalisis
from app.aplicacion.casos_de_uso.listar_analisis import ListarAnalisis
from app.aplicacion.casos_de_uso.obtener_analisis import ObtenerAnalisis
from app.aplicacion.casos_de_uso.obtener_imagen import ObtenerImagen
from app.aplicacion.casos_de_uso.renombrar_analisis import RenombrarAnalisis

LIMITE_IMAGEN_BYTES = 20 * 1024 * 1024
TIPOS_MIME = {"JPG": "image/jpeg", "PNG": "image/png"}

router = APIRouter(prefix="/analisis")


@router.post("", status_code=201)
def crear_analisis(
    imagen: UploadFile,
    caso: Annotated[CrearAnalisis, Depends(caso_crear)],
    nombre: Annotated[str, Form()] = "",
) -> AnalisisResumen:
    """Crea un análisis a partir de una fotografía JPG o PNG."""
    contenido = imagen.file.read(LIMITE_IMAGEN_BYTES + 1)
    if len(contenido) > LIMITE_IMAGEN_BYTES:
        raise ArchivoDemasiadoGrande("La imagen supera los 20 MB")
    return a_resumen(caso.ejecutar(nombre, contenido))


@router.get("")
def listar_analisis(
    caso: Annotated[ListarAnalisis, Depends(caso_listar)],
) -> list[AnalisisResumen]:
    """Lista los análisis, el más reciente primero."""
    return [a_resumen(a) for a in caso.ejecutar()]


@router.get("/{id}")
def obtener_analisis(
    id: UUID, caso: Annotated[ObtenerAnalisis, Depends(caso_obtener)]
) -> AnalisisDetalle:
    """Devuelve el detalle de un análisis."""
    return a_detalle(caso.ejecutar(id))


@router.patch("/{id}")
def renombrar_analisis(
    id: UUID,
    cuerpo: RenombrarSolicitud,
    caso: Annotated[RenombrarAnalisis, Depends(caso_renombrar)],
) -> AnalisisResumen:
    """Cambia el nombre de un análisis."""
    return a_resumen(caso.ejecutar(id, cuerpo.nombre))


@router.delete("/{id}", status_code=204)
def eliminar_analisis(
    id: UUID, caso: Annotated[EliminarAnalisis, Depends(caso_eliminar)]
) -> Response:
    """Elimina el análisis y su imagen."""
    caso.ejecutar(id)
    return Response(status_code=204)


@router.get("/{id}/imagen")
def obtener_imagen(id: UUID, caso: Annotated[ObtenerImagen, Depends(caso_imagen)]) -> Response:
    """Devuelve el archivo de imagen del análisis."""
    contenido, formato = caso.ejecutar(id)
    return Response(content=contenido, media_type=TIPOS_MIME[formato])
