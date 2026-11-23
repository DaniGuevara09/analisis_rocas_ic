"""Segmentación localizada para el pincel mágico (multi-escala YOLO + Watershed suavizado)."""

import math
from collections.abc import Sequence
from typing import Any

from PIL import Image

from app.adaptadores.salida.segmentacion.contornos import poligonos_desde_contornos
from app.dominio.errores import PoligonoNoValido
from app.dominio.modelo import Poligono, Punto


def _area_lazo(trazo: Sequence[Punto]) -> float:
    area = 0.0
    for i in range(len(trazo)):
        a = trazo[i]
        b = trazo[(i + 1) % len(trazo)]
        area += a.x * b.y - b.x * a.y
    return abs(area) / 2.0


def es_trazo_envolvente(trazo: Sequence[Punto], radio_px: float) -> bool:
    """Indica si el trazo rodea el contorno de una roca en lugar de ser una línea abierta."""
    if len(trazo) < 5:
        return False
    xs = [p.x for p in trazo]
    ys = [p.y for p in trazo]
    diag = math.hypot(max(xs) - min(xs), max(ys) - min(ys))
    if diag < 12.0:
        return False
    dist_cierre = math.hypot(trazo[-1].x - trazo[0].x, trazo[-1].y - trazo[0].y)
    if dist_cierre > max(radio_px * 3.5, diag * 0.5):
        return False
    area = _area_lazo(trazo)
    perimetro = sum(
        math.hypot(trazo[i + 1].x - trazo[i].x, trazo[i + 1].y - trazo[i].y)
        for i in range(len(trazo) - 1)
    )
    return area > max(120.0, perimetro * radio_px * 0.4)


def cajas_para_trazo(
    ancho: int, alto: int, trazo: Sequence[Punto], radio_px: float
) -> list[tuple[int, int, int, int]]:
    """Devuelve las ventanas de contexto (x0, y0, x1, y1) adecuadas al gesto del usuario."""
    if not trazo:
        return []
    xs = [p.x for p in trazo]
    ys = [p.y for p in trazo]
    x_min, x_max = min(xs) - radio_px, max(xs) + radio_px
    y_min, y_max = min(ys) - radio_px, max(ys) + radio_px

    if len(trazo) == 1:
        lado_img = min(ancho, alto)
        radios = [
            max(120.0, lado_img * 0.14),
            max(260.0, lado_img * 0.28),
            max(460.0, lado_img * 0.48),
        ]
        cajas: list[tuple[int, int, int, int]] = []
        vistos: set[tuple[int, int, int, int]] = set()
        for r in radios:
            x0 = max(0, int(math.floor(x_min - r)))
            y0 = max(0, int(math.floor(y_min - r)))
            x1 = min(ancho, int(math.ceil(x_max + r)))
            y1 = min(alto, int(math.ceil(y_max + r)))
            caja = (x0, y0, max(x0 + 8, x1), max(y0 + 8, y1))
            if caja not in vistos:
                vistos.add(caja)
                cajas.append(caja)
        if (0, 0, ancho, alto) not in vistos:
            cajas.append((0, 0, ancho, alto))
        return cajas

    margen = max(28.0, min(x_max - x_min, y_max - y_min) * 0.45, radio_px * 1.8)
    x0 = max(0, int(math.floor(x_min - margen)))
    y0 = max(0, int(math.floor(y_min - margen)))
    x1 = min(ancho, int(math.ceil(x_max + margen)))
    y1 = min(alto, int(math.ceil(y_max + margen)))
    return [(x0, y0, max(x0 + 8, x1), max(y0 + 8, y1))]


def recorte_para_trazo(
    ancho: int, alto: int, trazo: Sequence[Punto], radio_px: float
) -> tuple[int, int, int, int]:
    """Ventana principal de contexto para el pincel."""
    cajas = cajas_para_trazo(ancho, alto, trazo, radio_px)
    if not cajas:
        return (0, 0, ancho, alto)
    return cajas[min(1, len(cajas) - 1)] if len(trazo) == 1 else cajas[0]


def toca_borde_recorte(
    poligono: Poligono,
    caja: tuple[int, int, int, int],
    ancho_img: int,
    alto_img: int,
    margen_px: float = 3.0,
) -> bool:
    """Detecta si el polígono fue cortado artificialmente por un borde interno del recorte."""
    x0, y0, x1, y1 = caja
    pts = poligono.puntos
    lados_cortados = 0
    if x0 > 0 and sum(1 for p in pts if p.x <= x0 + margen_px) >= 2:
        lados_cortados += 1
    if x1 < ancho_img and sum(1 for p in pts if p.x >= x1 - margen_px) >= 2:
        lados_cortados += 1
    if y0 > 0 and sum(1 for p in pts if p.y <= y0 + margen_px) >= 2:
        lados_cortados += 1
    if y1 < alto_img and sum(1 for p in pts if p.y >= y1 - margen_px) >= 2:
        lados_cortados += 1
    return lados_cortados >= 2


def mascaras_a_poligonos_limpios(
    mascaras_tensor: Any,
    caja: tuple[int, int, int, int],
    ancho_img: int,
    alto_img: int,
    tam_inferencia: tuple[int, int] | None = None,
) -> list[Poligono]:
    """Convierte máscaras binarias a polígonos simples sin reescalar matrices gigantes."""
    import cv2  # type: ignore[import-not-found]
    import numpy as np

    x0, y0, x1, y1 = caja
    w_rec, h_rec = x1 - x0, y1 - y0
    w_ref, h_ref = tam_inferencia if tam_inferencia is not None else (w_rec, h_rec)
    escala_x = w_rec / max(1, w_ref)
    escala_y = h_rec / max(1, h_ref)
    contornos: list[list[tuple[float, float]]] = []

    for m in mascaras_tensor:
        arr = m.astype(np.uint8)
        if arr.shape != (h_ref, w_ref):
            arr = (
                cv2.resize(m.astype(np.float32), (w_ref, h_ref), interpolation=cv2.INTER_CUBIC)
                > 0.5
            ).astype(np.uint8)
        binaria = (arr > 0).astype(np.uint8)
        c_cv, _ = cv2.findContours(binaria, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not c_cv:
            continue
        mayor = max(c_cv, key=cv2.contourArea)
        if len(mayor) < 3:
            continue
        contornos.append(
            [(float(pt[0][0]) * escala_x + x0, float(pt[0][1]) * escala_y + y0) for pt in mayor]
        )

    return poligonos_desde_contornos(contornos, ancho_img, alto_img)


def _area_estimada_trazo(trazo: Sequence[Punto], radio_px: float) -> float:
    """Área aproximada barrida por un trazo abierto del pincel."""
    largo = sum(
        math.hypot(trazo[i + 1].x - trazo[i].x, trazo[i + 1].y - trazo[i].y)
        for i in range(len(trazo) - 1)
    )
    return largo * (radio_px * 2.0) + math.pi * (radio_px**2)


def _elegir_para_lazo(
    candidatos: Sequence[Poligono], trazo: Sequence[Punto]
) -> Poligono | None:
    """Elige la máscara de YOLO que mejor corresponde a una roca enmarcada por el borde."""
    try:
        lazo = Poligono(tuple(trazo))
    except PoligonoNoValido:
        return None
    area_lazo = _area_lazo(trazo)
    if area_lazo <= 0:
        return None
    centro_lazo = lazo.centroide()
    area_min = area_lazo * 0.30
    area_max = area_lazo * 2.10

    mejor: Poligono | None = None
    mejor_puntaje = 0.0
    for pol in candidatos:
        area = pol.area()
        if area < area_min or area > area_max:
            continue
        if not (lazo.contiene(pol.centroide()) or pol.contiene(centro_lazo)):
            continue
        cerca_centro = 2.0 if pol.contiene(centro_lazo) else 0.0
        similitud_area = 1.0 - min(1.0, abs(area - area_lazo) / area_lazo)
        puntaje = 5.0 * similitud_area + cerca_centro
        if puntaje > mejor_puntaje:
            mejor_puntaje = puntaje
            mejor = pol
    return mejor


def mejor_poligono_para_trazo(
    poligonos: Sequence[Poligono],
    trazo: Sequence[Punto],
    radio_px: float,
    caja: tuple[int, int, int, int] | None = None,
    ancho_img: int = 0,
    alto_img: int = 0,
) -> Poligono | None:
    """Elige el polígono detectado que mejor coincide con un toque, lazo o trazo pintado."""
    if not poligonos or not trazo:
        return None

    filtrados = list(poligonos)
    if caja is not None and ancho_img > 0 and alto_img > 0:
        sin_corte = [p for p in filtrados if not toca_borde_recorte(p, caja, ancho_img, alto_img)]
        if sin_corte:
            filtrados = sin_corte
        elif len(trazo) == 1:
            return None

    if len(trazo) == 1:
        punto = trazo[0]
        contienen = [p for p in filtrados if p.contiene(punto)]
        if not contienen:
            return None
        if caja is not None:
            area_caja = max(1.0, float((caja[2] - caja[0]) * (caja[3] - caja[1])))
            razonables = [p for p in contienen if p.area() <= area_caja * 0.7]
            if not razonables:
                return None
            contienen = razonables
        return min(contienen, key=lambda p: p.area())

    if es_trazo_envolvente(trazo, radio_px):
        return _elegir_para_lazo(filtrados, trazo)

    area_pintada = _area_estimada_trazo(trazo, radio_px)
    area_max = area_pintada * 1.85
    area_min = area_pintada * 0.25
    minimo_dentro = max(1, int(math.ceil(len(trazo) * 0.65)))

    mejor: Poligono | None = None
    mejor_puntaje = 0.0

    for poligono in filtrados:
        area = poligono.area()
        if area > area_max or area < area_min:
            continue
        dentro = sum(1 for p in trazo if poligono.contiene(p))
        if dentro < minimo_dentro:
            continue
        proporcion_dentro = dentro / len(trazo)
        diferencia_tamano = abs(area - area_pintada) / area_pintada
        puntaje = proporcion_dentro * 10.0 - diferencia_tamano * 3.0
        if puntaje > mejor_puntaje:
            mejor_puntaje = puntaje
            mejor = poligono

    return mejor


def segmentar_recorte_grabcut(
    foto: Image.Image, trazo: Sequence[Punto], radio_px: float
) -> Poligono | None:
    """Ajusta el toque, lazo o trazo a las grietas oscuras de la roca mediante Watershed."""
    if not trazo:
        return None
    try:
        import cv2  # type: ignore[import-not-found]
        import numpy as np
    except ImportError:
        return None

    ancho, alto = foto.size
    x0, y0, x1, y1 = recorte_para_trazo(ancho, alto, trazo, radio_px)
    recorte = foto.crop((x0, y0, x1, y1))
    w_rec, h_rec = recorte.size
    if w_rec < 8 or h_rec < 8:
        return None

    img_rgb = np.array(recorte, dtype=np.uint8)
    suave_color = cv2.bilateralFilter(img_rgb, d=7, sigmaColor=35, sigmaSpace=35)
    gris = cv2.cvtColor(suave_color, cv2.COLOR_RGB2GRAY)

    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    gradiente = cv2.morphologyEx(gris, cv2.MORPH_GRADIENT, kernel)
    gradiente_3c = cv2.cvtColor(gradiente, cv2.COLOR_GRAY2BGR)

    pts_locales = np.array(
        [[int(round(p.x - x0)), int(round(p.y - y0))] for p in trazo], dtype=np.int32
    )
    es_toque = len(pts_locales) == 1
    es_lazo = es_trazo_envolvente(trazo, radio_px)

    if es_toque:
        pt = (int(pts_locales[0][0]), int(pts_locales[0][1]))
        radio_nucleo = max(3, int(round(radio_px * 0.55)))
        radio_max = max(radio_nucleo + 10, int(round(min(w_rec, h_rec) * 0.42)))
        marcadores = np.full((h_rec, w_rec), 2, dtype=np.int32)
        mascara_max = np.zeros((h_rec, w_rec), dtype=np.uint8)
        cv2.circle(marcadores, pt, radio_max, (0,), -1)
        cv2.circle(marcadores, pt, radio_nucleo, (1,), -1)
        cv2.circle(mascara_max, pt, radio_max, (255,), -1)
    elif es_lazo:
        # El usuario enmarcó el borde: rellena el interior como roca (1), deja la franja del
        # borde como zona de ajuste (0) y todo el exterior como fondo definitivo (2).
        relleno = np.zeros((h_rec, w_rec), dtype=np.uint8)
        cv2.fillPoly(relleno, [pts_locales], (255,))
        k_banda = max(3, int(round(radio_px))) | 1
        elem = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k_banda, k_banda))
        exterior = cv2.dilate(relleno, elem)
        interior = cv2.erode(relleno, elem)
        if not np.any(interior > 0):
            interior = relleno

        marcadores = np.full((h_rec, w_rec), 2, dtype=np.int32)
        marcadores[exterior > 0] = 0
        marcadores[interior > 0] = 1
        mascara_max = exterior
    else:
        radio_max = max(3, int(round(radio_px * 1.22)))
        radio_nucleo = max(2, int(round(radio_px * 0.65)))
        marcadores = np.full((h_rec, w_rec), 2, dtype=np.int32)
        mascara_max = np.zeros((h_rec, w_rec), dtype=np.uint8)
        cv2.polylines(marcadores, [pts_locales], False, (0,), thickness=radio_max * 2)
        cv2.polylines(marcadores, [pts_locales], False, (1,), thickness=radio_nucleo * 2)
        cv2.polylines(mascara_max, [pts_locales], False, (255,), thickness=radio_max * 2)

    if not np.any(marcadores == 1) or not np.any(marcadores == 2):
        return None

    try:
        cv2.watershed(gradiente_3c, marcadores)
    except Exception:  # noqa: BLE001
        return None

    binaria = np.where((marcadores == 1) & (mascara_max > 0), 255, 0).astype(np.uint8)
    binaria = cv2.morphologyEx(binaria, cv2.MORPH_CLOSE, kernel)

    contornos_cv, _ = cv2.findContours(binaria, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contornos_cv:
        return None

    mayor = max(contornos_cv, key=cv2.contourArea)
    if len(mayor) < 3:
        return None
    contorno_img = [[(float(pt[0][0]) + x0, float(pt[0][1]) + y0) for pt in mayor]]
    poligonos = poligonos_desde_contornos(contorno_img, ancho, alto)
    return poligonos[0] if poligonos else None
