"""Composición: crea la app FastAPI, instancia los adaptadores y los conecta."""

import logging
from pathlib import Path

from fastapi import APIRouter, FastAPI
from sqlalchemy import create_engine

from app.adaptadores.entrada.api import (
    router_analisis,
    router_calibracion,
    router_configuracion,
    router_fragmentos,
    router_salud,
)
from app.adaptadores.entrada.api.errores import registrar_manejadores
from app.adaptadores.salida.almacenamiento.almacen_s3 import (
    AlmacenImagenesS3,
    crear_cliente_s3,
)
from app.adaptadores.salida.almacenamiento.archivos_local import AlmacenArchivosLocal
from app.adaptadores.salida.almacenamiento.inspector_pillow import InspectorImagenesPillow
from app.adaptadores.salida.persistencia.repositorio import RepositorioPostgreSQL
from app.adaptadores.salida.persistencia.repositorio_configuracion import (
    RepositorioConfiguracionPostgreSQL,
)
from app.adaptadores.salida.segmentacion.no_disponible import SegmentadorNoDisponible
from app.aplicacion.puertos import AlmacenImagenes, Segmentador
from app.config import Configuracion, configuracion


def crear_almacen(config: Configuracion) -> AlmacenImagenes:
    """Elige el almacén de imágenes (local o S3/R2) según la configuración."""
    if config.almacen_imagenes == "s3":
        cliente = crear_cliente_s3(
            config.s3_endpoint_url,
            config.s3_access_key_id,
            config.s3_secret_access_key,
            config.s3_region,
        )
        return AlmacenImagenesS3(cliente, config.s3_bucket)
    return AlmacenArchivosLocal(config.ruta_imagenes)


registro = logging.getLogger(__name__)


def crear_segmentador(config: Configuracion) -> Segmentador:
    """YOLO si existe el archivo del modelo; si no, un segmentador que responde 503."""
    if not Path(config.ruta_modelo).is_file():
        registro.warning("No se encontro el modelo en %s", config.ruta_modelo)
        return SegmentadorNoDisponible(f"no existe {config.ruta_modelo}")
    try:
        from app.adaptadores.salida.segmentacion.segmentador_yolo import SegmentadorYOLO

        return SegmentadorYOLO(
            config.ruta_modelo,
            confianza=config.segmentacion_confianza,
            imgsz=config.segmentacion_imgsz,
            max_det=config.segmentacion_max_det,
        )
    except Exception as error:  # noqa: BLE001 - la app debe arrancar aunque falle el modelo
        registro.exception("No se pudo cargar el modelo")
        return SegmentadorNoDisponible(f"error al cargar el modelo: {type(error).__name__}")


def crear_app() -> FastAPI:
    """Construye la aplicación con los adaptadores reales."""
    app = FastAPI(
        title="Análisis Granulométrico de Roca",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )
    motor = create_engine(configuracion.database_url, pool_pre_ping=True)
    app.state.repositorio = RepositorioPostgreSQL(motor)
    app.state.repositorio_configuracion = RepositorioConfiguracionPostgreSQL(motor)
    app.state.almacen = crear_almacen(configuracion)
    app.state.inspector = InspectorImagenesPillow()
    app.state.segmentador = crear_segmentador(configuracion)
    registrar_manejadores(app)
    api = APIRouter(prefix="/api")
    api.include_router(router_salud.router)
    api.include_router(router_analisis.router)
    api.include_router(router_calibracion.router)
    api.include_router(router_fragmentos.router)
    api.include_router(router_configuracion.router)
    app.include_router(api)
    return app


app = crear_app()
