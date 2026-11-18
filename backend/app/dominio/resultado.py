"""Objetos de valor del resultado granulométrico (se reexportan desde `modelo`)."""
from dataclasses import dataclass


@dataclass(frozen=True)
class PuntoCurva:
    """Punto de la curva granulométrica: diámetro en mm y porcentaje pasante acumulado."""

    diametro_mm: float
    pasante_pct: float


@dataclass(frozen=True)
class ResultadoGranulometrico:
    """Indicadores granulométricos de solo lectura."""

    d20: float
    d50: float
    d60: float
    d80: float
    d90: float
    indice_n: float
    numero_fragmentos: int
    curva: tuple[PuntoCurva, ...]
