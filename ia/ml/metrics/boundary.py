"""Métricas de calidad de BORDE (para evaluar si U-Net mejora los contornos).

- Boundary IoU (Cheng et al., CVPR 2021): IoU calculado solo sobre la franja
  de ancho d alrededor del contorno. Es mucho más sensible a errores de borde
  que el IoU de máscara, porque en rocas grandes el interior domina el IoU.
- Boundary F1 (BF-score, Csurka et al. 2013): precisión/recall de píxeles de
  contorno con tolerancia d.
"""
import cv2
import numpy as np


def _band(mask, d):
    m = mask.astype(np.uint8)
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * d + 1, 2 * d + 1))
    return (m - cv2.erode(m, k)).astype(bool)


def _contour(mask):
    m = mask.astype(np.uint8)
    return (m - cv2.erode(m, np.ones((3, 3), np.uint8))).astype(bool)


def default_d(shape, ratio=0.01):
    return max(1, int(round(ratio * np.hypot(*shape[:2]))))


def boundary_iou(pred, gt, d=None):
    d = d or default_d(gt.shape)
    pb = _band(pred, d) & pred.astype(bool)
    gb = _band(gt, d) & gt.astype(bool)
    union = np.logical_or(pb, gb).sum()
    return float(np.logical_and(pb, gb).sum() / union) if union else 1.0


def boundary_f1(pred, gt, d=2):
    pc, gc = _contour(pred), _contour(gt)
    if not pc.any() and not gc.any():
        return 1.0
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * d + 1, 2 * d + 1))
    gd = cv2.dilate(gc.astype(np.uint8), k).astype(bool)
    pd = cv2.dilate(pc.astype(np.uint8), k).astype(bool)
    prec = (pc & gd).sum() / max(pc.sum(), 1)
    rec = (gc & pd).sum() / max(gc.sum(), 1)
    return float(2 * prec * rec / (prec + rec)) if prec + rec else 0.0


def boundary_scores_matched(pred_masks, gt_masks, match_result, d=None):
    """Boundary IoU / BF promedio sobre los pares emparejados (TP)."""
    if not match_result["tp"]:
        return {"boundary_IoU": 0.0, "boundary_F1": 0.0}
    bi, bf = [], []
    for i, j in match_result["pairs"]:
        bi.append(boundary_iou(pred_masks[i], gt_masks[j], d))
        bf.append(boundary_f1(pred_masks[i], gt_masks[j]))
    return {"boundary_IoU": float(np.mean(bi)), "boundary_F1": float(np.mean(bf))}
