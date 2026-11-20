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


PASANTE_MINIMO_AJUSTE = 10.0
PASANTE_MAXIMO_AJUSTE = 90.0
PUNTOS_CURVA_TEORICA = 60


def _puntos_ajuste(
    curva: Sequence[PuntoCurva], minimo: float, maximo: float
) -> list[tuple[float, float]]:
    return [
        (math.log(p.diametro_mm), math.log(-math.log(1.0 - p.pasante_pct / 100.0)))
        for p in curva
        if minimo <= p.pasante_pct <= maximo and 0.0 < p.pasante_pct < 100.0
    ]


def ajuste_rosin_rammler(curva: Sequence[PuntoCurva]) -> tuple[float, float]:
    """Ajuste de Rosin-Rammler: devuelve (n, x_c en mm).

    Regresión lineal de ln(-ln(1-P)) contra ln(x) solo en el tramo central
    (10 % <= P <= 90 %), porque la cola de finos, ponderada por d³, crece como d³ y
    distorsiona la pendiente. Si ese tramo tiene menos de 2 puntos, usa todos los
    puntos con 0 < P < 100. x_c es el tamaño con 63,2 % pasante.
    """
    puntos = _puntos_ajuste(curva, PASANTE_MINIMO_AJUSTE, PASANTE_MAXIMO_AJUSTE)
    if len({x for x, _ in puntos}) < 2:
        puntos = _puntos_ajuste(curva, 0.0, 100.0)
    if len(puntos) < 2:
        raise DatosInsuficientes("Se necesitan al menos 2 puntos con 0 < P < 1")
    media_x = sum(x for x, _ in puntos) / len(puntos)
    media_y = sum(y for _, y in puntos) / len(puntos)
    varianza_x = sum((x - media_x) ** 2 for x, _ in puntos)
    if varianza_x == 0.0:
        raise DatosInsuficientes("Los diametros son iguales; no se puede ajustar")
    n = sum((x - media_x) * (y - media_y) for x, y in puntos) / varianza_x
    intercepto = media_y - n * media_x
    return n, math.exp(-intercepto / n)


def indice_uniformidad_n(curva: Sequence[PuntoCurva]) -> float:
    """Índice n de Rosin-Rammler (ver `ajuste_rosin_rammler`)."""
    return ajuste_rosin_rammler(curva)[0]


def pasante_rosin_rammler(diametro_mm: float, n: float, xc_mm: float) -> float:
    """% pasante del modelo de Rosin-Rammler para un tamaño."""
    return 100.0 * (1.0 - math.exp(-((diametro_mm / xc_mm) ** n)))


def curva_rosin_rammler(
    n: float, xc_mm: float, desde_mm: float, hasta_mm: float, cantidad: int = PUNTOS_CURVA_TEORICA
) -> list[PuntoCurva]:
    """Curva teórica P(x) = 1 - exp[-(x/x_c)^n] en puntos con espaciado logarítmico."""
    paso = math.log(hasta_mm / desde_mm) / (cantidad - 1)
    diametros = [desde_mm * math.exp(paso * i) for i in range(cantidad)]
    return [PuntoCurva(x, pasante_rosin_rammler(x, n, xc_mm)) for x in diametros]


def calcular(diametros_mm: Sequence[float]) -> ResultadoGranulometrico:
    """Calcula D20-D90, ajuste de Rosin-Rammler (n, x_c) y curvas a partir de los diámetros."""
    curva = curva_granulometrica(diametros_mm)
    n, xc = ajuste_rosin_rammler(curva)
    return ResultadoGranulometrico(
        d20=percentil_dx(curva, 20.0),
        d50=percentil_dx(curva, 50.0),
        d60=percentil_dx(curva, 60.0),
        d80=percentil_dx(curva, 80.0),
        d90=percentil_dx(curva, 90.0),
        indice_n=n,
        tamano_caracteristico_mm=xc,
        numero_fragmentos=len(diametros_mm),
        curva=tuple(curva),
        curva_teorica=tuple(
            curva_rosin_rammler(n, xc, curva[0].diametro_mm, curva[-1].diametro_mm)
        ),
    )


def rangos_por_defecto(resultado: ResultadoGranulometrico) -> tuple[RangoTamano, ...]:
    """Rangos relativos a la curva: <D20, D20-D50, D50-D80, D80-D90, >D90."""
    limites = [0.0, resultado.d20, resultado.d50, resultado.d80, resultado.d90]
    rangos = [RangoTamano(a, b) for a, b in zip(limites, limites[1:], strict=False)]
    return (*rangos, RangoTamano(resultado.d90, None))


def indice_rango(diametro_mm: float, rangos: Sequence[RangoTamano]) -> int:
    """Índice del rango que contiene el diámetro (el último si ninguno lo contiene)."""
    for indice, rango in enumerate(rangos):
        if rango.contiene(diametro_mm):
            return indice
    return len(rangos) - 1


def histograma(
    diametros_mm: Sequence[float], rangos: Sequence[RangoTamano]
) -> tuple[ClaseHistograma, ...]:
    """Una clase por rango de tamaño (los de la leyenda), con % retenido ponderado por d³."""
    if not diametros_mm:
        raise DatosInsuficientes("No hay diametros para el histograma")
    conteos = [0] * len(rangos)
    pesos = [0.0] * len(rangos)
    for diametro in diametros_mm:
        indice = indice_rango(diametro, rangos)
        conteos[indice] += 1
        pesos[indice] += ponderacion(diametro)
    total = sum(pesos)
    return tuple(
        ClaseHistograma(
            limite_inferior_mm=rango.limite_inferior_mm,
            limite_superior_mm=rango.limite_superior_mm,
            numero_fragmentos=conteos[i],
            porcentaje_retenido=100.0 * pesos[i] / total if total > 0 else 0.0,
        )
        for i, rango in enumerate(rangos)
    )
