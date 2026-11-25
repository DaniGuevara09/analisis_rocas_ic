"""Modelo 3: HDBSCAN (agrupamiento no supervisado por color + posición)."""
import cv2
import numpy as np

from .base import BaseSegmenter, SegmentationOutput


def extract_pixel_features(image_bgr, spatial_weight=0.3, downsample_factor=4):
    h, w = image_bgr.shape[:2]
    small = cv2.resize(image_bgr, (w // downsample_factor, h // downsample_factor),
                       interpolation=cv2.INTER_AREA)
    sh, sw = small.shape[:2]
    Y, X = np.mgrid[0:sh, 0:sw]
    lab = cv2.cvtColor(small, cv2.COLOR_BGR2LAB).astype(np.float32)
    lab[..., 0] /= 100.0; lab[..., 1] = (lab[..., 1] + 128) / 255.0; lab[..., 2] = (lab[..., 2] + 128) / 255.0
    hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV).astype(np.float32)
    hsv[..., 0] /= 179.0; hsv[..., 1] /= 255.0; hsv[..., 2] /= 255.0
    feats = [(X / sw).ravel() * spatial_weight, (Y / sh).ravel() * spatial_weight]
    feats += [lab[..., c].ravel() for c in range(3)] + [hsv[..., c].ravel() for c in range(3)]
    return np.stack(feats, 1).astype(np.float32), (sh, sw)


class HDBSCANSegmenter(BaseSegmenter):
    name = "HDBSCAN"

    def __init__(self, min_cluster_size=150, min_samples=10, cluster_selection_epsilon=0.02,
                 downsample_factor=4, min_area_px=300):
        self.cfg = dict(min_cluster_size=min_cluster_size, min_samples=min_samples,
                        cluster_selection_epsilon=cluster_selection_epsilon)
        self.ds, self.min_area = downsample_factor, min_area_px

    def _predict(self, img_rgb):
        import hdbscan
        bgr = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2BGR)
        h, w = bgr.shape[:2]
        feats, (sh, sw) = extract_pixel_features(bgr, downsample_factor=self.ds)
        lab = hdbscan.HDBSCAN(core_dist_n_jobs=-1, algorithm="boruvka_kdtree",
                              prediction_data=False, **self.cfg).fit(feats)
        labels = lab.labels_.reshape(sh, sw)
        prob = lab.probabilities_.reshape(sh, sw)  # pertenencia al clúster (0..1)
        k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        masks, scores = [], []
        for l in np.unique(labels):
            if l < 0:
                continue
            sm = (labels == l).astype(np.uint8)
            full = cv2.resize(sm, (w, h), interpolation=cv2.INTER_NEAREST)
            full = cv2.morphologyEx(cv2.morphologyEx(full, cv2.MORPH_CLOSE, k), cv2.MORPH_OPEN, k)
            if full.sum() >= self.min_area:
                masks.append(full); scores.append(float(prob[sm.astype(bool)].mean()))
        return SegmentationOutput(masks, np.array(scores), None)
