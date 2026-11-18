"""Métricas por instancia (fragmento): emparejamiento por IoU, precisión,
recall, F1, IoU medio, mAP COCO y curva PR por instancia.

Nota sobre ROC por instancia: en detección/segmentación de instancias NO
existen verdaderos negativos (cualquier región de fondo podría serlo), así
que la ROC clásica no está definida. Lo estándar es la curva
Precisión-Recall y su área (AP = mAP). Por eso la ROC/AUC se reporta a
nivel de píxel (ver pixel.py) y la PR/AP a nivel de instancia.
"""
import numpy as np


def _bbox(m):
    ys, xs = np.nonzero(m)
    if len(ys) == 0:
        return None
    return ys.min(), ys.max() + 1, xs.min(), xs.max() + 1


def iou_matrix(pred_masks, gt_masks):
    """IoU par a par usando solo la intersección de bounding boxes.

    Evita apilar máscaras completas (300 máscaras Full HD = varios GB)."""
    M = np.zeros((len(pred_masks), len(gt_masks)))
    if not pred_masks or not gt_masks:
        return M
    pb = [_bbox(m) for m in pred_masks]
    gb = [_bbox(m) for m in gt_masks]
    pa = [int(m.astype(bool).sum()) for m in pred_masks]
    ga = [int(m.astype(bool).sum()) for m in gt_masks]
    for i, bi in enumerate(pb):
        if bi is None:
            continue
        for j, bj in enumerate(gb):
            if bj is None:
                continue
            y0, y1 = max(bi[0], bj[0]), min(bi[1], bj[1])
            x0, x1 = max(bi[2], bj[2]), min(bi[3], bj[3])
            if y0 >= y1 or x0 >= x1:
                continue
            inter = np.logical_and(pred_masks[i][y0:y1, x0:x1].astype(bool),
                                   gt_masks[j][y0:y1, x0:x1].astype(bool)).sum()
            if inter:
                M[i, j] = inter / (pa[i] + ga[j] - inter)
    return M


def match(pred_masks, gt_masks, iou_thr=0.5, scores=None):
    """Emparejamiento voraz (mayor IoU primero, o mayor score primero si se da)."""
    M = iou_matrix(pred_masks, gt_masks)
    n_p, n_g = M.shape
    matched_p, matched_g, ious, tp_flags = set(), set(), [], np.zeros(n_p, bool)
    pairs = []
    if n_p and n_g:
        if scores is not None:
            avail = np.ones(n_g, bool)
            for i in np.argsort(-np.asarray(scores)):
                row = np.where(avail, M[i], -1)
                j = int(np.argmax(row))
                if row[j] >= iou_thr:
                    avail[j] = False
                    matched_p.add(int(i)); matched_g.add(j); ious.append(M[i, j]); tp_flags[i] = True
                    pairs.append((int(i), j))
        else:
            for idx in np.argsort(-M.ravel()):
                i, j = divmod(int(idx), n_g)
                if M[i, j] < iou_thr:
                    break
                if i not in matched_p and j not in matched_g:
                    matched_p.add(i); matched_g.add(j); ious.append(M[i, j]); tp_flags[i] = True
                    pairs.append((i, j))
    tp = len(ious)
    return {"tp": tp, "fp": n_p - tp, "fn": n_g - tp,
            "mean_iou": float(np.mean(ious)) if ious else 0.0,
            "matched_ious": ious, "tp_flags": tp_flags,
            "matched_gt": sorted(matched_g), "matched_pred": sorted(matched_p), "pairs": pairs}


class InstanceAccumulator:
    def __init__(self, iou_thr=0.5):
        self.iou_thr = iou_thr
        self.tp = self.fp = self.fn = 0
        self.ious, self.scores, self.flags = [], [], []
        self.n_gt_total = 0
        self.count_err = []

    def update(self, pred_masks, gt_masks, scores=None):
        scores = np.ones(len(pred_masks)) if scores is None else np.asarray(scores)
        r = match(pred_masks, gt_masks, self.iou_thr, scores)
        self.tp += r["tp"]; self.fp += r["fp"]; self.fn += r["fn"]
        self.ious += r["matched_ious"]
        self.scores += list(scores); self.flags += list(r["tp_flags"])
        self.n_gt_total += len(gt_masks)
        if gt_masks:
            self.count_err.append(abs(len(pred_masks) - len(gt_masks)) / len(gt_masks))
        return r

    def pr_curve(self):
        if not self.scores:
            return np.array([0.0]), np.array([1.0])
        order = np.argsort(-np.asarray(self.scores))
        f = np.asarray(self.flags)[order]
        tp, fp = np.cumsum(f), np.cumsum(~f)
        return tp / max(self.n_gt_total, 1), tp / np.maximum(tp + fp, 1)

    def ap(self):
        r, p = self.pr_curve()
        # interpolación de 101 puntos (estilo COCO) con el umbral de IoU fijo
        p_interp = np.maximum.accumulate(p[::-1])[::-1]
        grid = np.linspace(0, 1, 101)
        idx = np.searchsorted(r, grid, side="left")
        return float(np.mean([p_interp[i] if i < len(p_interp) else 0 for i in idx]))

    def summary(self):
        P = self.tp / max(self.tp + self.fp, 1)
        R = self.tp / max(self.tp + self.fn, 1)
        return {"inst_precision": P, "inst_recall": R,
                "inst_F1": 2 * P * R / max(P + R, 1e-9),
                "inst_mean_IoU": float(np.mean(self.ious)) if self.ious else 0.0,
                f"inst_AP@{self.iou_thr:.2f}": self.ap(),
                "error_conteo_medio": float(np.mean(self.count_err)) if self.count_err else 0.0}


def coco_mask_map(coco_gt, coco_dt_list, img_ids=None, cat_names=("rock",)):
    """mAP COCO (segm). Devuelve mAP50-95, mAP50 y mAP75."""
    if not coco_dt_list:
        return {"mAP50_95": 0.0, "mAP50": 0.0, "mAP75": 0.0}
    from pycocotools.cocoeval import COCOeval
    dt = coco_gt.loadRes(coco_dt_list)
    ev = COCOeval(coco_gt, dt, iouType="segm")
    ev.params.maxDets = [100, 300, 1000]  # las imágenes tienen cientos de rocas
    if img_ids is not None:
        ev.params.imgIds = list(img_ids)
    if cat_names:  # excluye la clase 'referencia' (si no, su AP=0 baja el promedio)
        ev.params.catIds = coco_gt.getCatIds(catNms=list(cat_names))
    ev.evaluate(); ev.accumulate(); ev.summarize()
    return {"mAP50_95": float(ev.stats[0]), "mAP50": float(ev.stats[1]), "mAP75": float(ev.stats[2])}
