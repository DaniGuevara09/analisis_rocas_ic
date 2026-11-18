"""Cálculo granulométrico con funciones puras (CalculadoraGranulometrica)."""
import math
from collections.abc import Sequence

from app.dominio.errores import DatosInsuficientes
from app.dominio.resultado import PuntoCurva, ResultadoGranulometrico


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
