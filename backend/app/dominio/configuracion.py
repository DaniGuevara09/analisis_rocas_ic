"""Configuración de los rangos de tamaño y sus colores (RF-06, RF-14)."""

import re
from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum

from app.dominio import granulometria
from app.dominio.errores import DatosNoValidos
from app.dominio.resultado import PuntoCurva, RangoTamano

MAXIMO_CORTES = 7
LONGITUD_MAXIMA_NOMBRE = 40
_COLOR_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")


class ModoRangos(Enum):
    """Cómo se interpretan los cortes entre rangos."""

    RELATIVO = "RELATIVO"  # % pasante de la curva (20 -> D20)
    ABSOLUTO = "ABSOLUTO"  # tamaño fijo en mm


@dataclass(frozen=True)
class ConfiguracionRangos:
    """Cortes, nombres y colores de los rangos. N cortes definen N + 1 rangos."""

    modo: ModoRangos
    cortes: tuple[float, ...]
    nombres: tuple[str, ...]
    colores: tuple[str, ...]

    def __post_init__(self) -> None:
        cortes = tuple(float(c) for c in self.cortes)
        _validar_cortes(self.modo, cortes)
        cantidad = len(cortes) + 1
        if len(self.nombres) != cantidad or len(self.colores) != cantidad:
            raise DatosNoValidos(f"Se esperan {cantidad} nombres y {cantidad} colores")
        object.__setattr__(self, "cortes", cortes)
        object.__setattr__(self, "nombres", tuple(_validar_nombre(n) for n in self.nombres))
        object.__setattr__(self, "colores", tuple(_validar_color(c) for c in self.colores))

    def rangos(self, curva: Sequence[PuntoCurva]) -> tuple[RangoTamano, ...]:
        """Límites en mm de cada rango para una curva granulométrica."""
        if self.modo is ModoRangos.RELATIVO:
            limites = [granulometria.percentil_dx(curva, c) for c in self.cortes]
        else:
            limites = list(self.cortes)
        inferiores = [0.0, *limites]
        superiores: list[float | None] = [*limites, None]
        return tuple(RangoTamano(a, b) for a, b in zip(inferiores, superiores, strict=True))


def _validar_cortes(modo: ModoRangos, cortes: tuple[float, ...]) -> None:
    if not 1 <= len(cortes) <= MAXIMO_CORTES:
        raise DatosNoValidos(f"Debe haber entre 2 y {MAXIMO_CORTES + 1} rangos")
    if any(b <= a for a, b in zip(cortes, cortes[1:], strict=False)):
        raise DatosNoValidos("Los cortes deben ser estrictamente crecientes")
    if cortes[0] <= 0:
        raise DatosNoValidos("Los cortes deben ser mayores que cero")
    if modo is ModoRangos.RELATIVO and cortes[-1] >= 100:
        raise DatosNoValidos("En modo relativo los cortes deben estar entre 0 y 100 %")


def _validar_nombre(nombre: str) -> str:
    limpio = nombre.strip()
    if not limpio or len(limpio) > LONGITUD_MAXIMA_NOMBRE:
        raise DatosNoValidos(
            f"Cada rango necesita un nombre de 1 a {LONGITUD_MAXIMA_NOMBRE} caracteres"
        )
    return limpio


def _validar_color(color: str) -> str:
    if not _COLOR_HEX.match(color):
        raise DatosNoValidos(f"Color no valido: {color} (use #rrggbb)")
    return color.lower()


# Rampa ordinal azul validada (claro = fino, oscuro = grueso): un solo tono, luminosidad
# monótona y el extremo claro con contraste >= 2:1 sobre fondo blanco.
CONFIGURACION_POR_DEFECTO = ConfiguracionRangos(
    modo=ModoRangos.RELATIVO,
    cortes=(20.0, 50.0, 80.0, 90.0),
    nombres=("Finos", "Pequeños", "Medianos", "Gruesos", "Sobretamaño"),
    colores=("#86b6ef", "#5598e7", "#2a78d6", "#1c5cab", "#104281"),
)
