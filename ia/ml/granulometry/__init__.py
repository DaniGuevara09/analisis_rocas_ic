"""Cálculo granulométrico para INVESTIGACIÓN (benchmark de modelos).

La fuente de verdad de la aplicación es backend/app/dominio/granulometria.py.
Aquí se replica su ponderación por defecto (volumen de esfera, d³) para que el
error de D50/D80 medido en el benchmark sea comparable con lo que muestra la app.
Se puede cambiar con weighting="volumen" o "count" para el análisis de sensibilidad
que piden docs/dominio.md (ponderación provisional).
"""
import math

import cv2
import numpy as np
from scipy.optimize import curve_fit


def factor_mm_px(x1, y1, x2, y2, longitud_real_mm):
    """Ecuación (1)."""
    d = math.hypot(x2 - x1, y2 - y1)
    if d <= 0:
        raise ValueError("Los puntos de calibración coinciden")
    return longitud_real_mm / d


def shoelace_area(contour):
    pts = contour.reshape(-1, 2).astype(float)
    x, y = pts[:, 0], pts[:, 1]
    return 0.5 * abs(np.dot(x, np.roll(y, 1)) - np.dot(y, np.roll(x, 1)))


def mask_area_px(mask, method="pixels"):
    """Área en px². 'pixels' cuenta píxeles; 'shoelace' usa el contorno externo
    (fórmula de Gauss, como en el documento)."""
    if method == "pixels":
        return float(mask.astype(bool).sum())
    cnts, _ = cv2.findContours(mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    return float(sum(shoelace_area(c) for c in cnts))


def exclude_reference(masks, ref_polygon_or_mask):
    """Descarta fragmentos cuyo centroide cae dentro de la región de exclusión."""
    if ref_polygon_or_mask is None:
        return masks
    keep = []
    for m in masks:
        M = cv2.moments(m.astype(np.uint8))
        if M["m00"] == 0:
            continue
        cx, cy = M["m10"] / M["m00"], M["m01"] / M["m00"]
        if isinstance(ref_polygon_or_mask, np.ndarray) and ref_polygon_or_mask.ndim == 2 \
                and ref_polygon_or_mask.shape == m.shape:
            inside = ref_polygon_or_mask[int(cy), int(cx)] > 0
        else:
            poly = np.asarray(ref_polygon_or_mask, np.float32).reshape(-1, 1, 2)
            inside = cv2.pointPolygonTest(poly, (float(cx), float(cy)), False) >= 0
        if not inside:
            keep.append(m)
    return keep


def equivalent_diameters(masks, factor=1.0, method="pixels"):
    """Ecuaciones (2) y (3): d_i = 2*sqrt(A_px * f^2 / pi)."""
    areas_mm2 = np.array([mask_area_px(m, method) for m in masks]) * factor ** 2
    return 2.0 * np.sqrt(areas_mm2 / np.pi)


def passing_curve(diameters, weighting="volumen"):
    """Curva acumulada pasante (%).
    weighting: 'volumen' (d³, igual que el dominio de la app), 'area' (d²) o 'count'."""
    d = np.sort(np.asarray(diameters, float))
    w = {"volumen": d ** 3, "area": d ** 2}.get(weighting, np.ones_like(d))
    return d, 100.0 * np.cumsum(w) / w.sum()


def percentiles(diameters, ps=(20, 50, 60, 80, 90), weighting="volumen"):
    if len(diameters) == 0:
        return {f"D{p}": float("nan") for p in ps}
    d, P = passing_curve(diameters, weighting)
    return {f"D{p}": float(np.interp(p, P, d)) for p in ps}


def rosin_rammler(x, xc, n):
    """Ecuación (4)."""
    return 100.0 * (1.0 - np.exp(-(x / xc) ** n))


def fit_rosin_rammler(diameters, weighting="volumen"):
    d, P = passing_curve(diameters, weighting)
    if len(d) < 3:
        return {"xc": float("nan"), "n": float("nan"), "R2": float("nan")}
    (xc, n), _ = curve_fit(rosin_rammler, d, P, p0=[np.median(d), 1.5],
                           bounds=([1e-6, 0.1], [np.inf, 10]), maxfev=20000)
    pred = rosin_rammler(d, xc, n)
    r2 = 1 - np.sum((P - pred) ** 2) / np.sum((P - P.mean()) ** 2)
    return {"xc": float(xc), "n": float(n), "R2": float(r2)}


def rr_percentile(p, xc, n):
    """Inverso de Rosin-Rammler: tamaño para el p % pasante."""
    return xc * (-math.log(1 - p / 100.0)) ** (1.0 / n)


def relative_error(sistema, referencia):
    """Ecuación (5), en %."""
    return abs(sistema - referencia) / referencia * 100.0 if referencia else float("nan")


def analizar(masks, factor=1.0, ref_region=None, weighting="volumen"):
    masks = exclude_reference(masks, ref_region)
    d = equivalent_diameters(masks, factor)
    out = {"n_fragmentos": int(len(d)), **percentiles(d, weighting=weighting)}
    out.update({f"RR_{k}": v for k, v in fit_rosin_rammler(d, weighting).items()})
    return out, d
