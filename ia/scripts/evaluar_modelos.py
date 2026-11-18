"""Benchmark con TODAS las métricas: las del documento (mAP@50, mAP@50-95,
latencia, tamaño) + las nuevas pedidas (AUC-ROC, curva ROC, IoU) + Dice,
AUC-PR, Boundary IoU y error relativo de D50/D80.

  python scripts/evaluar_modelos.py --modelos yolo unet hdbscan mobilesam
  python scripts/evaluar_modelos.py --modelos yolo yolo_unet --max-imagenes 5   # prueba rápida

Salidas en results/benchmark/:
  tabla_metricas.csv / .md     tabla para el documento
  roc_pixel.png, pr_pixel.png  curvas ROC y PR a nivel de píxel
  pr_instancia.png             curva PR por fragmento
  por_imagen_<modelo>.csv      detalle por imagen
"""
import argparse
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ml import config  # noqa: E402
from ml.data.coco_utils import load_coco  # noqa: E402
from ml.data.escalas import leer_escalas  # noqa: E402
from ml.evaluation import evaluate  # noqa: E402
from ml.metrics.plots import plot_instance_pr, plot_pr, plot_roc  # noqa: E402
from ml.models import build_model  # noqa: E402

COLS = [("modelo", "Modelo"), ("mAP50", "Mask mAP@50"), ("mAP50_95", "Mask mAP@50-95"),
        ("pixel_IoU", "IoU (píxel)"), ("inst_mean_IoU", "IoU medio (instancia)"),
        ("pixel_Dice", "Dice"), ("ROC_AUC", "AUC-ROC"), ("PR_AUC", "AUC-PR"),
        ("boundary_IoU", "Boundary IoU"), ("inst_F1", "F1 instancia"),
        ("ER_D50_%", "ER D50 (%)"), ("ER_D80_%", "ER D80 (%)"),
        ("latencia_ms", "Latencia (ms)"), ("tamano_MB", "Tamaño (MB)")]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--modelos", nargs="+", default=["yolo", "unet", "hdbscan", "mobilesam"])
    ap.add_argument("--coco", default=str(config.TEST_COCO))
    ap.add_argument("--images", default=str(config.TEST_IMG_DIR))
    ap.add_argument("--escalas", default=str(config.ESCALAS_XLSX))
    ap.add_argument("--max-imagenes", type=int)
    ap.add_argument("--out", default=str(config.RESULTS_DIR / "benchmark"))
    a = ap.parse_args()

    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    coco = load_coco(a.coco)
    escalas = leer_escalas(a.escalas) if Path(a.escalas).exists() else None
    print("Escalas:", f"{len(escalas)} imágenes calibradas" if escalas else "no hay Excel -> píxeles")

    summaries, pix, inst = [], {}, {}
    for m in a.modelos:
        seg = build_model(m)
        res = evaluate(seg, coco, a.images, escalas, max_images=a.max_imagenes)
        summaries.append(res["summary"]); pix[seg.name] = res["pixel_acc"]; inst[seg.name] = res["inst_acc"]
        res["per_image"].to_csv(out / f"por_imagen_{m}.csv", index=False)
        print(json.dumps(res["summary"], indent=1, default=float))

    df = pd.DataFrame(summaries)
    df.to_csv(out / "tabla_metricas_completa.csv", index=False)
    tab = df[[c for c, _ in COLS if c in df]].rename(columns=dict(COLS))
    tab.to_csv(out / "tabla_metricas.csv", index=False)
    (out / "tabla_metricas.md").write_text(tab.to_markdown(index=False, floatfmt=".4f"), encoding="utf-8")
    plot_roc(pix, out / "roc_pixel.png")
    plot_pr(pix, out / "pr_pixel.png")
    plot_instance_pr(inst, out / "pr_instancia.png")
    print(tab.to_string(index=False))
    print(f"\nResultados en {out}")


if __name__ == "__main__":
    main()
