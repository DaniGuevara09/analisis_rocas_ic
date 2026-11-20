"""Casos de uso de la configuración de rangos de tamaño y colores (RF-14)."""

from collections.abc import Sequence

from app.aplicacion.puertos import RepositorioConfiguracion
from app.dominio.configuracion import (
    CONFIGURACION_POR_DEFECTO,
    ConfiguracionRangos,
    ModoRangos,
)


class ObtenerConfiguracionRangos:
    """Devuelve la configuración guardada o la de por defecto."""

    def __init__(self, repositorio: RepositorioConfiguracion) -> None:
        self._repositorio = repositorio

    def ejecutar(self) -> ConfiguracionRangos:
        """Configuración vigente."""
        return self._repositorio.obtener_rangos() or CONFIGURACION_POR_DEFECTO


class GuardarConfiguracionRangos:
    """Valida (en el dominio) y guarda una configuración nueva."""

    def __init__(self, repositorio: RepositorioConfiguracion) -> None:
        self._repositorio = repositorio

    def ejecutar(
        self,
        modo: ModoRangos,
        cortes: Sequence[float],
        nombres: Sequence[str],
        colores: Sequence[str],
    ) -> ConfiguracionRangos:
        """Construye la configuración y la persiste."""
        configuracion = ConfiguracionRangos(modo, tuple(cortes), tuple(nombres), tuple(colores))
        self._repositorio.guardar_rangos(configuracion)
        return configuracion


class RestablecerConfiguracionRangos:
    """Vuelve a los rangos y colores por defecto."""

    def __init__(self, repositorio: RepositorioConfiguracion) -> None:
        self._repositorio = repositorio

    def ejecutar(self) -> ConfiguracionRangos:
        """Borra la configuración guardada."""
        self._repositorio.guardar_rangos(None)
        return CONFIGURACION_POR_DEFECTO
