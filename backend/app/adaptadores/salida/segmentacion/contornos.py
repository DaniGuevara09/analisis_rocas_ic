"""Conversión de contornos de máscaras (px) a polígonos del dominio. Funciones puras."""

import math
from collections.abc import Iterable, Sequence

from app.dominio.errores import PoligonoNoValido
from app.dominio.modelo import AREA_MINIMA_FRAGMENTO_PX2, Poligono, Punto

Par = tuple[float, float]

AREA_MINIMA_PX = AREA_MINIMA_FRAGMENTO_PX2
TOLERANCIA_PX = 1.0


def _distancia_a_segmento(p: Par, a: Par, b: Par) -> float:
    dx, dy = b[0] - a[0], b[1] - a[1]
    largo = math.hypot(dx, dy)
    if largo == 0:
        return math.hypot(p[0] - a[0], p[1] - a[1])
    return abs(dy * p[0] - dx * p[1] + b[0] * a[1] - b[1] * a[0]) / largo


def simplificar(puntos: Sequence[Par], tolerancia_px: float) -> list[Par]:
    """Douglas-Peucker sobre una polilínea abierta; conserva los extremos."""
    if len(puntos) < 3:
        return list(puntos)
    conservar = [False] * len(puntos)
    conservar[0] = conservar[-1] = True
    pendientes = [(0, len(puntos) - 1)]
    while pendientes:
        inicio, fin = pendientes.pop()
        lejano, maxima = -1, tolerancia_px
        for i in range(inicio + 1, fin):
            distancia = _distancia_a_segmento(puntos[i], puntos[inicio], puntos[fin])
            if distancia > maxima:
                lejano, maxima = i, distancia
        if lejano >= 0:
            conservar[lejano] = True
            pendientes += [(inicio, lejano), (lejano, fin)]
    return [p for p, mantener in zip(puntos, conservar, strict=True) if mantener]


def simplificar_anillo(puntos: Sequence[Par], tolerancia_px: float) -> list[Par]:
    """Douglas-Peucker sobre un contorno cerrado: lo parte en el punto más lejano al primero."""
    if len(puntos) < 4:
        return list(puntos)
    origen = puntos[0]
    corte = max(
        range(len(puntos)),
        key=lambda i: math.hypot(puntos[i][0] - origen[0], puntos[i][1] - origen[1]),
    )
    ida = simplificar(puntos[: corte + 1], tolerancia_px)
    vuelta = simplificar([*puntos[corte:], origen], tolerancia_px)
    return ida[:-1] + vuelta[:-1]


def _recortar(contorno: Iterable[Sequence[float]], ancho_px: float, alto_px: float) -> list[Par]:
    return [
        (min(max(float(p[0]), 0.0), ancho_px), min(max(float(p[1]), 0.0), alto_px))
        for p in contorno
    ]


def poligonos_desde_contornos(
    contornos: Iterable[Iterable[Sequence[float]]],
    ancho_px: float,
    alto_px: float,
    area_minima_px: float = AREA_MINIMA_PX,
    tolerancia_px: float = TOLERANCIA_PX,
) -> list[Poligono]:
    """Recorta a la imagen, simplifica y descarta contornos inválidos o diminutos."""
    poligonos: list[Poligono] = []
    for contorno in contornos:
        puntos = simplificar_anillo(_recortar(contorno, ancho_px, alto_px), tolerancia_px)
        if len(puntos) < 3:
            continue
        try:
            poligono = Poligono(tuple(Punto(x, y) for x, y in puntos))
        except PoligonoNoValido:
            continue
        if poligono.area() >= area_minima_px:
            poligonos.append(poligono)
    return poligonos
