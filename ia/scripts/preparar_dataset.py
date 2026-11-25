"""Convierte la segmentación manual a la estructura de entrenamiento.

Caso A — anotado en LabelMe (un .json por imagen junto a las imágenes):
  python scripts/preparar_dataset.py --labelme data/raw/wilder --images data/raw/wilder

Caso B — exportado como COCO desde CVAT/Roboflow:
  python scripts/preparar_dataset.py --coco data/annotations/wilder_coco.json --images data/raw/wilder

Genera data/dataset/{images,labels,annotations}/{train,val,test}, data.yaml y
un reporte CSV con el número de fragmentos por imagen.
"""
import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ml import config  # noqa: E402
from ml.data.coco_utils import coco_to_yolo_seg  # noqa: E402
from ml.data.manual_annotations import annotation_report, labelme_folder_to_coco, split_coco  # noqa: E402
from ml.models.yolo_seg import write_data_yaml  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--labelme")
ap.add_argument("--coco")
ap.add_argument("--images", required=True)
ap.add_argument("--out", default=str(config.DATASET_ROOT))
ap.add_argument("--ratios", default="0.7,0.15,0.15")
ap.add_argument("--seed", type=int, default=42)
a = ap.parse_args()

coco_json = a.coco
if a.labelme:
    coco_json = str(Path(a.out) / "annotations" / "all_coco.json")
    info = labelme_folder_to_coco(a.labelme, coco_json)
    print(f"LabelMe -> COCO: {info['imagenes']} imágenes, {info['anotaciones']} polígonos")
    if info["omitidas"]:
        print(f"  {len(info['omitidas'])} formas omitidas (etiqueta desconocida o no polígono), "
              f"ej.: {info['omitidas'][:5]}")

summary = split_coco(coco_json, a.images, a.out, tuple(map(float, a.ratios.split(","))), a.seed)
print("Partición:", summary)

out = Path(a.out)
for split in ("train", "val", "test"):
    coco_to_yolo_seg(out / "annotations" / f"{split}_coco.json", out / "labels" / split)
write_data_yaml(out, out / "data.yaml")
pd.DataFrame(annotation_report(coco_json)).to_csv(out / "reporte_anotaciones.csv", index=False)
print(f"Listo. data.yaml en {out / 'data.yaml'}")
