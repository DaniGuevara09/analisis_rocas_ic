"""Modelo 4: MobileSAM zero-shot (Segment Everything + filtro de rocas)."""
import os
import urllib.request

import numpy as np

from .. import config
from .base import BaseSegmenter, SegmentationOutput

URL = "https://github.com/ChaoningZhang/MobileSAM/raw/master/weights/mobile_sam.pt"


class MobileSAMSegmenter(BaseSegmenter):
    name = "MobileSAM"

    def __init__(self, weights=config.MOBILESAM_WEIGHTS, points_per_side=32, pred_iou_thresh=0.88,
                 stability_score_thresh=0.95, min_area=300, max_area_ratio=0.5,
                 min_iou_quality=0.85, device=None):
        from mobile_sam import SamAutomaticMaskGenerator, sam_model_registry
        self.weights = str(weights)
        if not os.path.exists(self.weights):
            os.makedirs(os.path.dirname(self.weights), exist_ok=True)
            urllib.request.urlretrieve(URL, self.weights)
        dev = device or config.device()
        sam = sam_model_registry["vit_t"](checkpoint=self.weights).to(dev).eval()
        self.gen = SamAutomaticMaskGenerator(
            model=sam, points_per_side=points_per_side, pred_iou_thresh=pred_iou_thresh,
            stability_score_thresh=stability_score_thresh, crop_n_layers=1,
            crop_n_points_downscale_factor=2, min_mask_region_area=200, output_mode="binary_mask")
        self.min_area, self.max_ratio, self.min_q = min_area, max_area_ratio, min_iou_quality

    def _predict(self, img_rgb):
        import torch
        with torch.no_grad():
            raw = self.gen.generate(img_rgb)
        max_area = img_rgb.shape[0] * img_rgb.shape[1] * self.max_ratio
        # Se corrige un detalle del notebook: allí los scores se tomaban de las
        # primeras N máscaras brutas, que no siempre coincidían con las filtradas.
        keep = [a for a in sorted(raw, key=lambda a: -a["predicted_iou"])
                if self.min_area <= a["area"] <= max_area and a["predicted_iou"] >= self.min_q]
        masks = [a["segmentation"].astype(np.uint8) for a in keep]
        scores = np.array([float(a["predicted_iou"]) for a in keep])
        return SegmentationOutput(masks, scores, None, {"n_raw": len(raw)})

    @property
    def weights_size_mb(self):
        return os.path.getsize(self.weights) / 1e6
