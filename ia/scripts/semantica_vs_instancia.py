"""Corrección: "Mirar si es más eficiente segmentación semántica o de instancia".

Compara, sobre el MISMO test, tres configuraciones:
  1. U-Net semántica      : solo foreground + componentes conexas (sin bordes)
  2. U-Net instancia      : foreground + bordes + Watershed
  3. YOLO instancia       : YOLOv11m-seg
  4. YOLO "semantizado"   : unión de las máscaras de YOLO + componentes conexas
     (aísla el efecto de PERDER la separación entre rocas con el mismo modelo)

El criterio no es solo la calidad de píxel (donde la semántica puede salir
bien), sino lo que el sistema necesita medir: el tamaño de CADA fragmento.
Por eso se reportan: IoU de píxel (semántica), F1/IoU por instancia,
error de conteo, % de rocas fusionadas y error de D50/D80, además de la
latencia (eficiencia computacional).

  python scripts/semantica_vs_instancia.py [--max-imagenes 10]
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import ndimage as ndi

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ml import config  # noqa: E402
from ml.data.coco_utils import load_coco  # noqa: E402
from ml.data.escalas import leer_escalas  # noqa: E402
from ml.evaluation import evaluate  # noqa: E402
from ml.metrics.instance import iou_matrix  # noqa: E402
from ml.models import build_model  # noqa: E402
from ml.models.base import BaseSegmenter, SegmentationOutput  # noqa: E402


class SemanticFromInstances(BaseSegmenter):
    """Convierte la salida de un modelo de instancias en semántica."""

    def __init__(self, inner, min_area=200):
        self.inner, self.min_area = inner, min_area
        self.name = f"{inner.name} (semantizado)"

    def _predict(self, img):
        o = self.inner._predict(img)
        fg = np.zeros(img.shape[:2], np.uint8)
        for m in o.masks:
            fg |= m
        lab, n = ndi.label(fg)
        masks = [(lab == i).astype(np.uint8) for i in range(1, n + 1) if (lab == i).sum() >= self.min_area]
        return SegmentationOutput(masks, np.ones(len(masks)), fg.astype(np.float32))

    @property
    def weights_size_mb(self):
        return self.inner.weights_size_mb


def merged_fraction(pred_masks, gt_masks, cover=0.5):
    """% de rocas GT que quedaron fusionadas con otra en una misma predicción
    (una predicción cubre >= `cover` de 2 o más rocas GT)."""
    if not pred_masks or not gt_masks:
        return 0.0
    M = iou_matrix(pred_masks, gt_masks)
    ga = np.array([g.sum() for g in gt_masks], float)
    pa = np.array([p.sum() for p in pred_masks], float)
    # intersección = IoU*(A_p + A_g)/(1+IoU)
    inter = M * (pa[:, None] + ga[None, :]) / (1 + M)
    covered = inter / ga[None, :] >= cover
    merged = set()
    for i in range(len(pred_masks)):
        js = np.nonzero(covered[i])[0]
        if len(js) >= 2:
            merged.update(js.tolist())
    return 100.0 * len(merged) / len(gt_masks)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-imagenes", type=int)
    ap.add_argument("--out", default=str(config.RESULTS_DIR / "semantica_vs_instancia"))
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)

    coco = load_coco(config.TEST_COCO)
    escalas = leer_escalas(config.ESCALAS_XLSX) if config.ESCALAS_XLSX.exists() else None
    yolo = build_model("yolo")
    configs = {
        "semántica": [build_model("unet_semantic"), SemanticFromInstances(yolo)],
        "instancia": [build_model("unet"), yolo],
    }
    rows = []
    for tipo, models in configs.items():
        for seg in models:
            res = evaluate(seg, coco, config.TEST_IMG_DIR, escalas, max_images=a.max_imagenes,
                           keep_outputs=True)
            s = res["summary"]
            # % de rocas fusionadas (solo necesita las salidas guardadas)
            from ml.data.coco_utils import gt_masks, name_to_id
            n2id = name_to_id(coco)
            mf = [merged_fraction(o.masks, gt_masks(coco, n2id[n], ["rock"]))
                  for n, o in res["outputs"].items()]
            rows.append({"tipo": tipo, "modelo": seg.name,
                         "IoU píxel": s["pixel_IoU"], "AUC-ROC": s["ROC_AUC"],
                         "F1 instancia": s["inst_F1"], "IoU medio inst.": s["inst_mean_IoU"],
                         "mAP@50": s["mAP50"], "error conteo (%)": 100 * s["error_conteo_medio"],
                         "rocas fusionadas (%)": float(np.mean(mf)) if mf else 0.0,
                         "ER D50 (%)": s["ER_D50_%"], "ER D80 (%)": s["ER_D80_%"],
                         "latencia (ms)": s["latencia_ms"]})
    df = pd.DataFrame(rows)
    df.to_csv(out / "comparacion.csv", index=False)
    print(df.to_string(index=False, float_format=lambda v: f"{v:.3f}"))
    print("\nLectura: si la versión semántica tiene IoU de píxel parecido pero más rocas "
          "fusionadas, mayor error de conteo y mayor ER en D50/D80, la segmentación de "
          "INSTANCIA es la adecuada para granulometría aunque la semántica sea igual o más rápida.")


if __name__ == "__main__":
    main()
