"""Composición: crea la app FastAPI, instancia los adaptadores y los conecta."""
from fastapi import APIRouter, FastAPI
from sqlalchemy import create_engine

from app.adaptadores.entrada.api import router_analisis, router_calibracion, router_salud
from app.adaptadores.entrada.api.errores import registrar_manejadores
from app.adaptadores.salida.almacenamiento.almacen_s3 import (
    AlmacenImagenesS3,
    crear_cliente_s3,
)
from app.adaptadores.salida.almacenamiento.archivos_local import AlmacenArchivosLocal
from app.adaptadores.salida.almacenamiento.inspector_pillow import InspectorImagenesPillow
from app.adaptadores.salida.persistencia.repositorio import RepositorioPostgreSQL
from app.aplicacion.puertos import AlmacenImagenes
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


def crear_app() -> FastAPI:
    """Construye la aplicación con los adaptadores reales."""
    app = FastAPI(
        title="Análisis Granulométrico de Roca",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )
    app.state.repositorio = RepositorioPostgreSQL(
        create_engine(configuracion.database_url, pool_pre_ping=True)
    )
    app.state.almacen = crear_almacen(configuracion)
    app.state.inspector = InspectorImagenesPillow()
    registrar_manejadores(app)
    api = APIRouter(prefix="/api")
    api.include_router(router_salud.router)
    api.include_router(router_analisis.router)
    api.include_router(router_calibracion.router)
    app.include_router(api)
    return app


app = crear_app()
