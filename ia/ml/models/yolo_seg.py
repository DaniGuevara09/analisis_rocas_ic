"""Modelo 1: YOLOv11m-seg (segmentación de instancias de una etapa)."""
import os

import cv2
import numpy as np

from .. import config
from .base import BaseSegmenter, SegmentationOutput


def write_data_yaml(dataset_root=config.DATASET_ROOT, out=config.DATA_YAML, val_split="val"):
    import yaml
    val = f"images/{val_split}" if (dataset_root / "images" / val_split).exists() else "images/test"
    cfg = {"path": str(dataset_root), "train": "images/train", "val": val,
           "test": "images/test", "nc": len(config.CLASS_NAMES), "names": config.CLASS_NAMES}
    with open(out, "w") as f:
        yaml.safe_dump(cfg, f)
    return out


def train_yolo(data_yaml=config.DATA_YAML, base="yolo11m-seg.pt", epochs=100, batch=4,
               imgsz=640, project=None, name="yolo11m_seg_rocks", device=None, **overrides):
    """Mismos hiperparámetros del notebook (sección III-B del documento)."""
    from ultralytics import YOLO
    model = YOLO(base)
    params = dict(data=str(data_yaml), epochs=epochs, batch=batch, imgsz=imgsz, patience=20,
                  device=device or config.device(), project=str(project or config.RESULTS_DIR / "yolo"),
                  name=name, save=True, val=True, plots=True, workers=2, amp=True, max_det=300,
                  degrees=10.0, fliplr=0.5, flipud=0.3, mosaic=0.8, scale=0.5,
                  hsv_h=0.015, hsv_s=0.5, hsv_v=0.4, exist_ok=True)
    params.update(overrides)
    model.train(**params)
    return os.path.join(params["project"], name, "weights", "best.pt")


class YoloSegmenter(BaseSegmenter):
    name = "YOLOv11m-seg"

    def __init__(self, weights=config.YOLO_WEIGHTS, imgsz=640, conf=0.25, iou=0.5,
                 max_det=1000, device=None, retina_masks=True):
        from ultralytics import YOLO
        self.weights = str(weights)
        self.model = YOLO(self.weights)
        self.imgsz, self.conf, self.iou, self.max_det = imgsz, conf, iou, max_det
        self.device = device or config.device()
        self.retina_masks = retina_masks  # máscaras a resolución original (mejor borde)

    def _predict(self, img_rgb):
        bgr = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2BGR)
        r = self.model.predict(bgr, imgsz=self.imgsz, conf=self.conf, iou=self.iou,
                               max_det=self.max_det, device=self.device, verbose=False,
                               retina_masks=self.retina_masks)[0]
        h, w = img_rgb.shape[:2]
        if r.masks is None:
            return SegmentationOutput([], np.zeros(0), np.zeros((h, w), np.float32))
        masks = []
        for m in r.masks.data.cpu().numpy():
            if m.shape != (h, w):
                m = cv2.resize(m, (w, h), interpolation=cv2.INTER_NEAREST)
            masks.append((m > 0.5).astype(np.uint8))
        scores = r.boxes.conf.cpu().numpy()
        return SegmentationOutput(masks, scores, None)

    @property
    def weights_size_mb(self):
        return os.path.getsize(self.weights) / 1e6
