"""Objetos de valor del resultado granulométrico (se reexportan desde `modelo`)."""

from dataclasses import dataclass
from uuid import UUID


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
    tamano_caracteristico_mm: float  # x_c de Rosin-Rammler (63,2 % pasante)
    numero_fragmentos: int
    curva: tuple[PuntoCurva, ...]
    curva_teorica: tuple[PuntoCurva, ...]  # Rosin-Rammler ajustada, para superponer


@dataclass(frozen=True)
class RangoTamano:
    """Rango de tamaño [inferior, superior) en mm; sin límite superior si es None (RF-06)."""

    limite_inferior_mm: float
    limite_superior_mm: float | None

    def contiene(self, diametro_mm: float) -> bool:
        """Indica si el diámetro cae en el rango (incluye el inferior, excluye el superior)."""
        if diametro_mm < self.limite_inferior_mm:
            return False
        return self.limite_superior_mm is None or diametro_mm < self.limite_superior_mm


@dataclass(frozen=True)
class ClaseHistograma:
    """Clase del histograma (un rango de tamaño): intervalo en mm, fragmentos y % en masa."""

    limite_inferior_mm: float
    limite_superior_mm: float | None
    numero_fragmentos: int
    porcentaje_retenido: float


@dataclass(frozen=True)
class FragmentoMedido:
    """Diámetro equivalente de un fragmento y el índice de su rango de tamaño."""

    id: UUID
    diametro_equivalente_mm: float
    indice_rango: int


@dataclass(frozen=True)
class ReporteGranulometrico:
    """Resultado completo para la pantalla de resultados y el informe."""

    resultado: ResultadoGranulometrico
    rangos: tuple[RangoTamano, ...]
    nombres_rangos: tuple[str, ...]
    colores_rangos: tuple[str, ...]
    histograma: tuple[ClaseHistograma, ...]
    fragmentos: tuple[FragmentoMedido, ...]
