"""Rutas de configuración de rangos de tamaño y colores (RF-14)."""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.adaptadores.entrada.api.dependencias import (
    caso_guardar_rangos,
    caso_obtener_rangos,
    caso_restablecer_rangos,
)
from app.adaptadores.entrada.api.esquemas import ConfiguracionRangosEsquema, a_configuracion
from app.aplicacion.casos_de_uso.configurar_rangos import (
    GuardarConfiguracionRangos,
    ObtenerConfiguracionRangos,
    RestablecerConfiguracionRangos,
)
from app.dominio.configuracion import ModoRangos

router = APIRouter(prefix="/configuracion")


@router.get("/rangos")
def obtener_rangos(
    caso: Annotated[ObtenerConfiguracionRangos, Depends(caso_obtener_rangos)],
) -> ConfiguracionRangosEsquema:
    """Rangos vigentes (los guardados o los de por defecto)."""
    return a_configuracion(caso.ejecutar())


@router.put("/rangos")
def guardar_rangos(
    cuerpo: ConfiguracionRangosEsquema,
    caso: Annotated[GuardarConfiguracionRangos, Depends(caso_guardar_rangos)],
) -> ConfiguracionRangosEsquema:
    """Guarda cortes, nombres y colores; se aplican a todos los análisis."""
    guardada = caso.ejecutar(ModoRangos(cuerpo.modo), cuerpo.cortes, cuerpo.nombres, cuerpo.colores)
    return a_configuracion(guardada)


@router.delete("/rangos")
def restablecer_rangos(
    caso: Annotated[RestablecerConfiguracionRangos, Depends(caso_restablecer_rangos)],
) -> ConfiguracionRangosEsquema:
    """Vuelve a los rangos y colores por defecto y los devuelve."""
    return a_configuracion(caso.ejecutar())
