"""Repositorio de la configuración global sobre PostgreSQL."""

from typing import Any

from sqlalchemy import Engine, delete
from sqlalchemy.orm import sessionmaker

from app.adaptadores.salida.persistencia.tablas import TablaConfiguracion
from app.dominio.configuracion import ConfiguracionRangos, ModoRangos

CLAVE_RANGOS = "rangos"


def rangos_a_json(configuracion: ConfiguracionRangos) -> dict[str, Any]:
    """Serializa la configuración de rangos."""
    return {
        "modo": configuracion.modo.value,
        "cortes": list(configuracion.cortes),
        "nombres": list(configuracion.nombres),
        "colores": list(configuracion.colores),
    }


def rangos_desde_json(datos: dict[str, Any]) -> ConfiguracionRangos:
    """Reconstruye la configuración (vuelve a validarse en el dominio)."""
    return ConfiguracionRangos(
        modo=ModoRangos(datos["modo"]),
        cortes=tuple(float(c) for c in datos["cortes"]),
        nombres=tuple(datos["nombres"]),
        colores=tuple(datos["colores"]),
    )


class RepositorioConfiguracionPostgreSQL:
    """Implementa `RepositorioConfiguracion` en la tabla `configuracion`."""

    def __init__(self, motor: Engine) -> None:
        self._sesiones = sessionmaker(motor, expire_on_commit=False)

    def obtener_rangos(self) -> ConfiguracionRangos | None:
        """Configuración guardada o None."""
        with self._sesiones() as sesion:
            fila = sesion.get(TablaConfiguracion, CLAVE_RANGOS)
            return None if fila is None else rangos_desde_json(fila.valor)

    def guardar_rangos(self, configuracion: ConfiguracionRangos | None) -> None:
        """Guarda o borra (None) la configuración de rangos."""
        with self._sesiones.begin() as sesion:
            if configuracion is None:
                sesion.execute(
                    delete(TablaConfiguracion).where(TablaConfiguracion.clave == CLAVE_RANGOS)
                )
            else:
                sesion.merge(
                    TablaConfiguracion(clave=CLAVE_RANGOS, valor=rangos_a_json(configuracion))
                )
