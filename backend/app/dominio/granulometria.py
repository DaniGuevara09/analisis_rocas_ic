"""Cálculo granulométrico con funciones puras (CalculadoraGranulometrica)."""
import math
from collections.abc import Sequence

from app.dominio.errores import DatosInsuficientes
from app.dominio.resultado import (
    ClaseHistograma,
    PuntoCurva,
    RangoTamano,
    ResultadoGranulometrico,
)

MAXIMO_CLASES_HISTOGRAMA = 12


def factor_mm_por_px(longitud_real_mm: float, distancia_px: float) -> float:
    """Factor de escala: mm reales por cada píxel."""
    return longitud_real_mm / distancia_px


def area_mm2(area_px: float, factor_mm_por_px: float) -> float:
    """Área real a partir del área en píxeles."""
    return area_px * factor_mm_por_px**2


def diametro_equivalente_mm(area_mm2: float) -> float:
    """Diámetro del círculo con la misma área (supuesto de esfericidad)."""
    return math.sqrt(4.0 * area_mm2 / math.pi)


def ponderacion(diametro_mm: float) -> float:
    """Peso relativo de un fragmento. Provisional: volumen de esfera, proporcional a d³."""
    return diametro_mm**3


def curva_granulometrica(diametros_mm: Sequence[float]) -> list[PuntoCurva]:
    """Porcentaje pasante acumulado, con diámetros ordenados de menor a mayor."""
    if not diametros_mm:
        raise DatosInsuficientes("No hay diametros para construir la curva")
    ordenados = sorted(diametros_mm)
    pesos = [ponderacion(d) for d in ordenados]
    total = sum(pesos)
    curva: list[PuntoCurva] = []
    acumulado = 0.0
    for diametro, peso in zip(ordenados, pesos, strict=True):
        acumulado += peso
        curva.append(PuntoCurva(diametro, 100.0 * acumulado / total))
    return curva


def percentil_dx(curva: Sequence[PuntoCurva], x_pct: float) -> float:
    """Tamaño (mm) para el cual P = x %, por interpolación lineal entre puntos."""
    if not curva:
        raise DatosInsuficientes("La curva esta vacia")
    if x_pct <= curva[0].pasante_pct:
        return curva[0].diametro_mm
    for anterior, siguiente in zip(curva, curva[1:], strict=False):
        if x_pct <= siguiente.pasante_pct:
            fraccion = (x_pct - anterior.pasante_pct) / (
                siguiente.pasante_pct - anterior.pasante_pct
            )
            return anterior.diametro_mm + fraccion * (siguiente.diametro_mm - anterior.diametro_mm)
    return curva[-1].diametro_mm


def indice_uniformidad_n(curva: Sequence[PuntoCurva]) -> float:
    """Índice n de Rosin-Rammler: pendiente del ajuste lineal de ln(-ln(1-P)) contra ln(x)."""
    puntos = [
        (math.log(p.diametro_mm), math.log(-math.log(1.0 - p.pasante_pct / 100.0)))
        for p in curva
        if 0.0 < p.pasante_pct < 100.0
    ]
    if len(puntos) < 2:
        raise DatosInsuficientes("Se necesitan al menos 2 puntos con 0 < P < 1")
    media_x = sum(x for x, _ in puntos) / len(puntos)
    media_y = sum(y for _, y in puntos) / len(puntos)
    varianza_x = sum((x - media_x) ** 2 for x, _ in puntos)
    if varianza_x == 0.0:
        raise DatosInsuficientes("Los diametros son iguales; no se puede ajustar")
    covarianza = sum((x - media_x) * (y - media_y) for x, y in puntos)
    return covarianza / varianza_x


def calcular(diametros_mm: Sequence[float]) -> ResultadoGranulometrico:
    """Calcula D20-D90, índice n y curva a partir de los diámetros equivalentes."""
    curva = curva_granulometrica(diametros_mm)
    return ResultadoGranulometrico(
        d20=percentil_dx(curva, 20.0),
        d50=percentil_dx(curva, 50.0),
        d60=percentil_dx(curva, 60.0),
        d80=percentil_dx(curva, 80.0),
        d90=percentil_dx(curva, 90.0),
        indice_n=indice_uniformidad_n(curva),
        numero_fragmentos=len(diametros_mm),
        curva=tuple(curva),
    )


def rangos_por_defecto(resultado: ResultadoGranulometrico) -> tuple[RangoTamano, ...]:
    """Rangos de color por defecto, relativos a la curva: <D20, D20-D50, D50-D80, D80-D90, >D90."""
    limites = [0.0, resultado.d20, resultado.d50, resultado.d80, resultado.d90]
    rangos = [RangoTamano(a, b) for a, b in zip(limites, limites[1:], strict=False)]
    return (*rangos, RangoTamano(resultado.d90, None))


def indice_rango(diametro_mm: float, rangos: Sequence[RangoTamano]) -> int:
    """Índice del rango que contiene el diámetro (el último si ninguno lo contiene)."""
    for indice, rango in enumerate(rangos):
        if rango.contiene(diametro_mm):
            return indice
    return len(rangos) - 1


def _numero_clases(cantidad: int) -> int:
    """Regla de Sturges, acotada a MAXIMO_CLASES_HISTOGRAMA."""
    return min(MAXIMO_CLASES_HISTOGRAMA, math.ceil(math.log2(cantidad)) + 1)


def histograma(
    diametros_mm: Sequence[float], numero_clases: int | None = None
) -> tuple[ClaseHistograma, ...]:
    """Clases de igual ancho entre el menor y el mayor diámetro, con % retenido ponderado."""
    if not diametros_mm:
        raise DatosInsuficientes("No hay diametros para el histograma")
    minimo, maximo = min(diametros_mm), max(diametros_mm)
    clases = 1 if maximo == minimo else numero_clases or _numero_clases(len(diametros_mm))
    ancho = (maximo - minimo) / clases
    conteos = [0] * clases
    pesos = [0.0] * clases
    for diametro in diametros_mm:
        indice = 0 if ancho == 0 else min(int((diametro - minimo) / ancho), clases - 1)
        conteos[indice] += 1
        pesos[indice] += ponderacion(diametro)
    total = sum(pesos)
    return tuple(
        ClaseHistograma(
            limite_inferior_mm=minimo + i * ancho,
            limite_superior_mm=maximo if i == clases - 1 else minimo + (i + 1) * ancho,
            numero_fragmentos=conteos[i],
            porcentaje_retenido=100.0 * pesos[i] / total if total > 0 else 0.0,
        )
        for i in range(clases)
    )
