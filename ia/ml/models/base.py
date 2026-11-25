"""Interfaz común para los cuatro métodos de segmentación.

Todos devuelven un `SegmentationOutput` con:
  masks      lista de máscaras binarias (H, W) en resolución ORIGINAL
  scores     confianza por instancia (para mAP / curva PR por instancia)
  score_map  mapa (H, W) en [0,1] de "probabilidad de roca" por píxel
             (para ROC / AUC / IoU semántico)
  extra      salidas intermedias (p. ej. mapas fg/borde de U-Net)
  latency_ms tiempo de inferencia + post-procesamiento
"""
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import numpy as np

from ..metrics.pixel import score_map_from_instances


@dataclass
class SegmentationOutput:
    masks: list
    scores: np.ndarray
    score_map: np.ndarray
    extra: dict = field(default_factory=dict)
    latency_ms: float = 0.0


class BaseSegmenter(ABC):
    name = "base"

    @abstractmethod
    def _predict(self, img_rgb) -> SegmentationOutput: ...

    def predict(self, img_rgb) -> SegmentationOutput:
        t0 = time.perf_counter()
        out = self._predict(img_rgb)
        self._sync()
        out.latency_ms = (time.perf_counter() - t0) * 1000
        if out.score_map is None:
            out.score_map = score_map_from_instances(out.masks, out.scores, img_rgb.shape[:2])
        return out

    def _sync(self):
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.synchronize()
        except ImportError:
            pass

    @property
    def weights_size_mb(self):
        return None
