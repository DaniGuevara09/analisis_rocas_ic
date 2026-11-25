"""Pruebas de extremo a extremo con un dataset sintético de "rocas" (elipses
que se tocan). Ejecutar:  pytest -q tests/"""
import json
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ml import granulometry as G  # noqa: E402
from ml.data.coco_utils import coco_to_yolo_seg, load_coco  # noqa: E402
from ml.data.escalas import crear_plantilla, escribir_puntos, leer_escalas  # noqa: E402
from ml.data.manual_annotations import labelme_folder_to_coco, split_coco  # noqa: E402
from ml.evaluation import evaluate  # noqa: E402
from ml.metrics import PixelMetricAccumulator, boundary_iou, match  # noqa: E402
from ml.models.base import BaseSegmenter, SegmentationOutput  # noqa: E402


def make_scene(rng, h=256, w=320, n=14):
    img = np.full((h, w, 3), 90, np.uint8) + rng.integers(0, 25, (h, w, 3), dtype=np.uint8)
    polys, ref = [], None
    for _ in range(n):
        cx, cy = rng.integers(25, w - 25), rng.integers(25, h - 25)
        ax, ay = rng.integers(10, 26), rng.integers(8, 22)
        ang = rng.integers(0, 180)
        pts = cv2.ellipse2Poly((int(cx), int(cy)), (int(ax), int(ay)), int(ang), 0, 360, 12)
        polys.append(pts)
        col = tuple(int(c) for c in rng.integers(130, 230, 3))
        cv2.fillPoly(img, [pts], col)
        cv2.polylines(img, [pts], True, (40, 40, 40), 1)
    ref = np.array([[5, h - 20], [85, h - 20], [85, h - 12], [5, h - 12]])  # "regla" 80 px
    cv2.fillPoly(img, [ref], (250, 250, 250))
    return img, polys, ref


@pytest.fixture(scope="module")
def dataset(tmp_path_factory):
    root = tmp_path_factory.mktemp("ds")
    raw = root / "raw"; raw.mkdir()
    rng = np.random.default_rng(0)
    for i in range(10):
        img, polys, ref = make_scene(rng)
        name = f"img_{i:03d}.jpg"
        cv2.imwrite(str(raw / name), cv2.cvtColor(img, cv2.COLOR_RGB2BGR))
        shapes = [{"label": "roca", "points": p.tolist(), "shape_type": "polygon"} for p in polys]
        shapes.append({"label": "escala", "points": ref.tolist(), "shape_type": "polygon"})
        json.dump({"imagePath": name, "imageWidth": img.shape[1], "imageHeight": img.shape[0],
                   "shapes": shapes}, open(raw / f"img_{i:03d}.json", "w"))
    return root, raw


def test_labelme_split_yolo(dataset):
    root, raw = dataset
    info = labelme_folder_to_coco(raw, root / "all.json")
    assert info["imagenes"] == 10 and info["anotaciones"] == 150 and not info["omitidas"]
    s = split_coco(root / "all.json", raw, root / "dataset", (0.6, 0.2, 0.2))
    assert sum(v["imagenes"] for v in s.values()) == 10
    n = coco_to_yolo_seg(root / "dataset/annotations/train_coco.json", root / "dataset/labels/train")
    txt = next((root / "dataset/labels/train").glob("*.txt")).read_text().splitlines()
    assert n == 6 and len(txt) == 14 and txt[0].startswith("0 ")  # 'referencia' excluida


def test_excel_escalas(dataset, tmp_path):
    _, raw = dataset
    x = tmp_path / "escalas.xlsx"
    assert crear_plantilla(raw, x) == 10
    assert escribir_puntos(x, "img_000.jpg", 5, 240, 85, 240, 300, "Regla", "Bibian")
    esc = leer_escalas(x)
    assert list(esc) == ["img_000.jpg"]
    assert abs(esc["img_000.jpg"]["factor_mm_px"] - 300 / 80) < 1e-9


def test_pixel_metrics_against_sklearn():
    from sklearn.metrics import average_precision_score, roc_auc_score
    rng = np.random.default_rng(1)
    gt = rng.random((120, 120)) > 0.6
    score = np.clip(gt * 0.35 + rng.random((120, 120)) * 0.65, 0, 1)
    acc = PixelMetricAccumulator(n_bins=2000)
    acc.update(score, gt)
    assert abs(acc.roc_auc() - roc_auc_score(gt.ravel(), score.ravel())) < 2e-3
    assert abs(acc.pr_auc() - average_precision_score(gt.ravel(), score.ravel())) < 5e-3
    perfect = PixelMetricAccumulator(); perfect.update(gt.astype(float), gt)
    s = perfect.summary()
    assert s["pixel_IoU"] == 1.0 and abs(s["ROC_AUC"] - 1) < 1e-9


def test_matching_and_boundary():
    a = np.zeros((50, 50), np.uint8); a[10:30, 10:30] = 1
    b = np.zeros_like(a); b[12:32, 10:30] = 1
    r = match([a], [a, b])
    assert r["tp"] == 1 and r["fn"] == 1 and r["pairs"] == [(0, 0)]
    assert boundary_iou(a, a) == 1.0 and boundary_iou(a, b) < 0.9


def test_granulometry():
    rng = np.random.default_rng(3)
    d = rng.weibull(1.8, 2000) * 50
    rr = G.fit_rosin_rammler(d, weighting="count")
    assert 1.5 < rr["n"] < 2.1 and rr["R2"] > 0.98
    disk = np.zeros((101, 101), np.uint8); cv2.circle(disk, (50, 50), 20, 1, -1)
    assert abs(G.equivalent_diameters([disk], 2.0)[0] - 80) < 1.5
    assert abs(G.relative_error(110, 100) - 10) < 1e-9


class NoisyOracle(BaseSegmenter):
    """Segmentador falso: devuelve el GT erosionado/dilatado al azar."""
    name = "oraculo"

    def __init__(self, coco):
        self.coco = coco
        self.n2id = {v["file_name"]: k for k, v in coco.imgs.items()}
        self.current = None

    def _predict(self, img):
        from ml.data.coco_utils import gt_masks
        ms = gt_masks(self.coco, self.current, ["rock"])
        k = np.ones((3, 3), np.uint8)
        out = [cv2.dilate(m, k) if i % 2 else cv2.erode(m, k) for i, m in enumerate(ms)]
        return SegmentationOutput(out, np.linspace(1, 0.5, len(out)), None)


def test_evaluate_end_to_end(dataset, tmp_path):
    root, raw = dataset
    coco = load_coco(root / "dataset/annotations/train_coco.json")
    seg = NoisyOracle(coco)
    orig = seg.predict

    def predict(img, _names=iter(sorted(coco.imgs.values(), key=lambda v: v["file_name"]))):
        seg.current = next(_names)["id"]
        return orig(img)
    seg.predict = predict
    res = evaluate(seg, coco, root / "dataset/images/train", progress=False)
    s = res["summary"]
    assert s["ROC_AUC"] > 0.95 and s["pixel_IoU"] > 0.8 and s["mAP50"] > 0.5
    assert s["ER_D50_%"] < 20
    from ml.metrics.plots import plot_roc
    plot_roc({"oraculo": res["pixel_acc"]}, tmp_path / "roc.png")
    assert (tmp_path / "roc.png").stat().st_size > 5000


torch = pytest.importorskip("torch")


def test_unet_weight_map_and_training(dataset, tmp_path):
    from ml.models.unet_dual import UNetSegmenter, train_unet, unet_weight_map
    from ml.models.hybrid_yolo_unet import refine_contour, split_by_borders
    a = np.zeros((40, 60), np.uint8); a[10:30, 5:28] = 1
    b = np.zeros_like(a); b[10:30, 31:55] = 1
    w = unet_weight_map([a, b], a.shape, class_balance=False)
    assert w[20, 29] > 5 and w[2, 2] < 1.5   # hueco entre rocas pesa más que fondo lejano

    root, _ = dataset
    ds = root / "dataset"
    out, hist = train_unet(ds / "images/train", ds / "annotations/train_coco.json",
                           ds / "images/val", ds / "annotations/val_coco.json",
                           out_path=tmp_path / "u.pth", epochs=1, batch=2, img_size=128,
                           device="cpu", workers=0)
    assert Path(out).exists() and "val_IoU" in hist[0]
    seg = UNetSegmenter(out, img_size=128, mode="semantic", device="cpu")
    img = cv2.cvtColor(cv2.imread(str(next((ds / "images/test").glob("*.jpg")))), cv2.COLOR_BGR2RGB)
    o = seg.predict(img)
    assert o.score_map.shape == img.shape[:2] and o.latency_ms > 0

    merged = np.maximum(a, b); bd = np.zeros(a.shape, np.float32); bd[:, 28:31] = 1
    assert len(split_by_borders(merged, bd, min_area=50)) == 2
    assert refine_contour(a, a.astype(np.float32)).sum() == a.sum()
