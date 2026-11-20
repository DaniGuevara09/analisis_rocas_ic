"""Dependencias de FastAPI: puertos (tomados de `app.state`) y casos de uso."""

from typing import Annotated

from fastapi import Depends, Request

from app.aplicacion.casos_de_uso.calibrar_escala import CalibrarEscala
from app.aplicacion.casos_de_uso.configurar_rangos import (
    GuardarConfiguracionRangos,
    ObtenerConfiguracionRangos,
    RestablecerConfiguracionRangos,
)
from app.aplicacion.casos_de_uso.crear_analisis import CrearAnalisis
from app.aplicacion.casos_de_uso.editar_fragmentos import EditarFragmentos
from app.aplicacion.casos_de_uso.eliminar_analisis import EliminarAnalisis
from app.aplicacion.casos_de_uso.excluir_region import ExcluirRegion
from app.aplicacion.casos_de_uso.listar_analisis import ListarAnalisis
from app.aplicacion.casos_de_uso.obtener_analisis import ObtenerAnalisis
from app.aplicacion.casos_de_uso.obtener_imagen import ObtenerImagen
from app.aplicacion.casos_de_uso.obtener_resultados import ObtenerResultados
from app.aplicacion.casos_de_uso.quitar_region_excluida import QuitarRegionExcluida
from app.aplicacion.casos_de_uso.renombrar_analisis import RenombrarAnalisis
from app.aplicacion.casos_de_uso.segmentar_analisis import SegmentarAnalisis
from app.aplicacion.puertos import (
    AlmacenImagenes,
    InspectorImagenes,
    RepositorioAnalisis,
    RepositorioConfiguracion,
    Segmentador,
)


def obtener_repositorio(request: Request) -> RepositorioAnalisis:
    """Repositorio configurado en la composición (`main.py`)."""
    return request.app.state.repositorio  # type: ignore[no-any-return]


def obtener_almacen(request: Request) -> AlmacenImagenes:
    """Almacén de imágenes configurado en la composición."""
    return request.app.state.almacen  # type: ignore[no-any-return]


def obtener_inspector(request: Request) -> InspectorImagenes:
    """Inspector de imágenes configurado en la composición."""
    return request.app.state.inspector  # type: ignore[no-any-return]


def obtener_segmentador(request: Request) -> Segmentador:
    """Segmentador configurado en la composición (YOLO o no disponible)."""
    return request.app.state.segmentador  # type: ignore[no-any-return]


def obtener_repositorio_configuracion(request: Request) -> RepositorioConfiguracion:
    """Repositorio de configuración (rangos de tamaño y colores)."""
    return request.app.state.repositorio_configuracion  # type: ignore[no-any-return]


Repositorio = Annotated[RepositorioAnalisis, Depends(obtener_repositorio)]
Almacen = Annotated[AlmacenImagenes, Depends(obtener_almacen)]
Inspector = Annotated[InspectorImagenes, Depends(obtener_inspector)]
SegmentadorDep = Annotated[Segmentador, Depends(obtener_segmentador)]
RepoConfiguracion = Annotated[RepositorioConfiguracion, Depends(obtener_repositorio_configuracion)]


def caso_crear(repo: Repositorio, almacen: Almacen, inspector: Inspector) -> CrearAnalisis:
    """Caso de uso CrearAnalisis."""
    return CrearAnalisis(repo, almacen, inspector)


def caso_listar(repo: Repositorio) -> ListarAnalisis:
    """Caso de uso ListarAnalisis."""
    return ListarAnalisis(repo)


def caso_obtener(repo: Repositorio) -> ObtenerAnalisis:
    """Caso de uso ObtenerAnalisis."""
    return ObtenerAnalisis(repo)


def caso_renombrar(repo: Repositorio) -> RenombrarAnalisis:
    """Caso de uso RenombrarAnalisis."""
    return RenombrarAnalisis(repo)


def caso_eliminar(repo: Repositorio, almacen: Almacen) -> EliminarAnalisis:
    """Caso de uso EliminarAnalisis."""
    return EliminarAnalisis(repo, almacen)


def caso_imagen(repo: Repositorio, almacen: Almacen) -> ObtenerImagen:
    """Caso de uso ObtenerImagen."""
    return ObtenerImagen(repo, almacen)


def caso_calibrar(repo: Repositorio) -> CalibrarEscala:
    """Caso de uso CalibrarEscala."""
    return CalibrarEscala(repo)


def caso_excluir_region(repo: Repositorio) -> ExcluirRegion:
    """Caso de uso ExcluirRegion."""
    return ExcluirRegion(repo)


def caso_quitar_region(repo: Repositorio) -> QuitarRegionExcluida:
    """Caso de uso QuitarRegionExcluida."""
    return QuitarRegionExcluida(repo)


def caso_segmentar(
    repo: Repositorio, almacen: Almacen, segmentador: SegmentadorDep
) -> SegmentarAnalisis:
    """Caso de uso SegmentarAnalisis."""
    return SegmentarAnalisis(repo, almacen, segmentador)


def caso_editar_fragmentos(repo: Repositorio) -> EditarFragmentos:
    """Caso de uso EditarFragmentos."""
    return EditarFragmentos(repo)


def caso_resultados(repo: Repositorio, configuracion: RepoConfiguracion) -> ObtenerResultados:
    """Caso de uso ObtenerResultados."""
    return ObtenerResultados(repo, configuracion)


def caso_obtener_rangos(configuracion: RepoConfiguracion) -> ObtenerConfiguracionRangos:
    """Caso de uso ObtenerConfiguracionRangos."""
    return ObtenerConfiguracionRangos(configuracion)


def caso_guardar_rangos(configuracion: RepoConfiguracion) -> GuardarConfiguracionRangos:
    """Caso de uso GuardarConfiguracionRangos."""
    return GuardarConfiguracionRangos(configuracion)


def caso_restablecer_rangos(configuracion: RepoConfiguracion) -> RestablecerConfiguracionRangos:
    """Caso de uso RestablecerConfiguracionRangos."""
    return RestablecerConfiguracionRangos(configuracion)
