"""Métricas a nivel de píxel: IoU (Jaccard), Dice/F1, precisión, recall,
curva ROC, AUC-ROC, curva PR y AUC-PR.

Se calculan de forma ACUMULADA sobre todo el conjunto de test usando
histogramas de puntajes (n_bins umbrales). Así no hay que guardar millones de
píxeles en memoria y la curva ROC es exacta hasta la resolución del bin.

Qué es el "puntaje" de cada píxel según el modelo:
  - U-Net:      probabilidad sigmoide de la cabeza de foreground (continua).
  - YOLO-seg:   max_i( conf_i * máscara_i(píxel) )  -> continua por niveles.
  - MobileSAM:  max_i( predicted_iou_i * máscara_i(píxel) ).
  - HDBSCAN:    máscara binaria (0/1) -> la ROC tiene un único punto y el AUC
                equivale a (TPR + TNR)/2 (balanced accuracy). Hay que
                aclararlo en el documento.
"""
from dataclasses import dataclass, field

import numpy as np


def iou_binary(pred, gt):
    pred, gt = pred.astype(bool), gt.astype(bool)
    union = np.logical_or(pred, gt).sum()
    return float(np.logical_and(pred, gt).sum() / union) if union else 1.0


def dice_binary(pred, gt):
    pred, gt = pred.astype(bool), gt.astype(bool)
    s = pred.sum() + gt.sum()
    return float(2 * np.logical_and(pred, gt).sum() / s) if s else 1.0


def score_map_from_instances(masks, scores, shape):
    """Construye un mapa de puntaje por píxel a partir de instancias."""
    out = np.zeros(shape, np.float32)
    for m, s in zip(masks, scores):
        np.maximum(out, m.astype(np.float32) * float(s), out=out)
    return out


@dataclass
class PixelMetricAccumulator:
    n_bins: int = 1000
    threshold: float = 0.5
    pos_hist: np.ndarray = field(default=None)
    neg_hist: np.ndarray = field(default=None)
    per_image_iou: list = field(default_factory=list)
    per_image_dice: list = field(default_factory=list)

    def __post_init__(self):
        self.pos_hist = np.zeros(self.n_bins, np.int64)
        self.neg_hist = np.zeros(self.n_bins, np.int64)

    def update(self, score_map, gt_fg, ignore=None):
        """score_map en [0,1] (H,W); gt_fg binaria (H,W); ignore opcional
        (p. ej. la región del objeto de referencia o el relleno negro)."""
        s = np.clip(score_map.astype(np.float32), 0, 1)
        g = gt_fg.astype(bool)
        valid = np.ones_like(g) if ignore is None else ~ignore.astype(bool)
        bins = np.minimum((s * self.n_bins).astype(np.int64), self.n_bins - 1)
        self.pos_hist += np.bincount(bins[g & valid], minlength=self.n_bins)
        self.neg_hist += np.bincount(bins[~g & valid], minlength=self.n_bins)
        pred = (s >= self.threshold) & valid
        self.per_image_iou.append(iou_binary(pred, g & valid))
        self.per_image_dice.append(dice_binary(pred, g & valid))

    # ---------------- curvas ----------------
    def _cum(self):
        # umbral t_k = k/n_bins; predicho positivo si score >= t_k
        tp = np.cumsum(self.pos_hist[::-1])[::-1]
        fp = np.cumsum(self.neg_hist[::-1])[::-1]
        P, N = self.pos_hist.sum(), self.neg_hist.sum()
        return tp, fp, P, N

    def roc_curve(self):
        tp, fp, P, N = self._cum()
        tpr = np.concatenate([[0.0], (tp / max(P, 1))[::-1]])
        fpr = np.concatenate([[0.0], (fp / max(N, 1))[::-1]])
        thr = np.concatenate([[1.0], (np.arange(self.n_bins) / self.n_bins)[::-1]])
        # aseguramos el punto (1,1)
        if fpr[-1] < 1 or tpr[-1] < 1:
            fpr, tpr, thr = np.append(fpr, 1.0), np.append(tpr, 1.0), np.append(thr, 0.0)
        return fpr, tpr, thr

    def roc_auc(self):
        fpr, tpr, _ = self.roc_curve()
        return float(np.trapezoid(tpr, fpr))

    def pr_curve(self):
        tp, fp, P, _ = self._cum()
        denom = np.maximum(tp + fp, 1)
        precision = (tp / denom)[::-1]
        recall = (tp / max(P, 1))[::-1]
        keep = (tp + fp)[::-1] > 0
        return np.concatenate([[0.0], recall[keep]]), np.concatenate([[1.0], precision[keep]])

    def pr_auc(self):
        """Average precision (suma escalonada, como sklearn)."""
        r, p = self.pr_curve()
        return float(np.sum(np.diff(r) * p[1:]))

    def at_threshold(self, t=None):
        t = self.threshold if t is None else t
        k = int(round(t * self.n_bins))
        tp, fp, P, N = self._cum()
        TP = int(tp[k]) if k < self.n_bins else 0
        FP = int(fp[k]) if k < self.n_bins else 0
        FN, TN = int(P - TP), int(N - FP)
        prec = TP / (TP + FP) if TP + FP else 0.0
        rec = TP / (TP + FN) if TP + FN else 0.0
        return {
            "pixel_IoU": TP / (TP + FP + FN) if TP + FP + FN else 0.0,
            "pixel_Dice": 2 * TP / (2 * TP + FP + FN) if TP + FP + FN else 0.0,
            "pixel_precision": prec, "pixel_recall": rec,
            "pixel_accuracy": (TP + TN) / max(P + N, 1),
            "pixel_specificity": TN / (TN + FP) if TN + FP else 0.0,
        }

    def best_threshold_youden(self):
        fpr, tpr, thr = self.roc_curve()
        j = np.argmax(tpr - fpr)
        return float(thr[j]), float(tpr[j] - fpr[j])

    def summary(self):
        out = self.at_threshold()
        out.update({
            "ROC_AUC": self.roc_auc(), "PR_AUC": self.pr_auc(),
            "mIoU_por_imagen": float(np.mean(self.per_image_iou)) if self.per_image_iou else 0.0,
            "mDice_por_imagen": float(np.mean(self.per_image_dice)) if self.per_image_dice else 0.0,
        })
        t, j = self.best_threshold_youden()
        out["umbral_optimo_Youden"], out["J_Youden"] = t, j
        return out
