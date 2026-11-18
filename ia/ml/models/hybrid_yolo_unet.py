"""Experimento: YOLO para instancias + U-Net para BORDES.

Responde a la corrección "mirar cómo U-Net puede funcionar para determinar
los bordes". En lugar de reemplazar a YOLO (que ya ganó en mAP y latencia),
U-Net se usa como módulo de refinamiento:

  1. Ajuste de contorno: cada máscara de YOLO (que viene de prototipos a
     baja resolución, 160x160 para imgsz=640) se recorta/expande con el mapa
     de foreground de U-Net dentro de una franja estrecha alrededor del borde.
  2. División de sub-segmentaciones: si dentro de una máscara YOLO el mapa de
     bordes de U-Net muestra una frontera que la parte en >=2 regiones
     grandes, se divide con Watershed (rocas en contacto fusionadas).

Si el Boundary IoU / BF-score y el error de D50/D80 mejoran respecto a YOLO
solo, se justifica incluir U-Net en el sistema; si no, se documenta que no
aporta y se descarta (decisión de la fase de Evaluación de CRISP-DM).
"""
import cv2
import numpy as np
from scipy import ndimage as ndi

from .base import BaseSegmenter, SegmentationOutput


def refine_contour(mask, fg_prob, band=3, thr=0.5):
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * band + 1, 2 * band + 1))
    m = mask.astype(np.uint8)
    inner = cv2.erode(m, k)
    outer = cv2.dilate(m, k)
    ring = (outer - inner).astype(bool)
    out = inner.astype(bool) | (ring & (fg_prob > thr))
    # conservar solo la componente principal
    lab, n = ndi.label(out)
    if n > 1:
        sizes = ndi.sum(out, lab, range(1, n + 1))
        out = lab == (1 + int(np.argmax(sizes)))
    return out.astype(np.uint8)


def split_by_borders(mask, bd_prob, bd_thr=0.5, min_part_ratio=0.15, min_area=200):
    from skimage.segmentation import watershed
    m = mask.astype(bool)
    seeds = m & (bd_prob < bd_thr)
    seeds = ndi.binary_opening(seeds, iterations=2)
    lab, n = ndi.label(seeds)
    if n < 2:
        return [mask]
    sizes = ndi.sum(seeds, lab, range(1, n + 1))
    big = [i + 1 for i, s in enumerate(sizes) if s >= max(min_part_ratio * m.sum(), min_area)]
    if len(big) < 2:
        return [mask]
    markers = np.zeros(lab.shape, np.int32)
    for k, i in enumerate(big, start=1):
        markers[lab == i] = k
    ws = watershed(bd_prob, markers, mask=m)
    return [(ws == k).astype(np.uint8) for k in range(1, len(big) + 1) if (ws == k).sum() >= min_area]


class YoloUNetBorderSegmenter(BaseSegmenter):
    name = "YOLO+U-Net bordes"

    def __init__(self, yolo, unet, refine=True, split=True, band=3):
        self.yolo, self.unet = yolo, unet
        self.refine, self.split, self.band = refine, split, band

    def _predict(self, img_rgb):
        y = self.yolo._predict(img_rgb)
        fg, bd = self.unet.prob_maps(img_rgb)
        masks, scores = [], []
        for m, s in zip(y.masks, y.scores):
            parts = split_by_borders(m, bd) if self.split else [m]
            for p in parts:
                masks.append(refine_contour(p, fg, self.band) if self.refine else p)
                scores.append(s)
        return SegmentationOutput(masks, np.array(scores), None,
                                  {"fg_prob": fg, "bd_prob": bd, "n_yolo": len(y.masks)})

    @property
    def weights_size_mb(self):
        return (self.yolo.weights_size_mb or 0) + (self.unet.weights_size_mb or 0)
