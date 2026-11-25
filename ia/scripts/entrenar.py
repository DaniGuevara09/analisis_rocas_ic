"""Entrenamiento de los modelos supervisados.

  python scripts/entrenar.py yolo  --epochs 100 --batch 4
  python scripts/entrenar.py unet  --epochs 80  [--sin-weight-map] [--resume weights/unet_dual_best.pth]
"""
import argparse
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ml import config  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("modelo", choices=["yolo", "unet"])
ap.add_argument("--epochs", type=int)
ap.add_argument("--batch", type=int, default=4)
ap.add_argument("--sin-weight-map", action="store_true")
ap.add_argument("--resume")
a = ap.parse_args()

config.WEIGHTS_DIR.mkdir(parents=True, exist_ok=True)
if a.modelo == "yolo":
    from ml.models.yolo_seg import train_yolo, write_data_yaml
    if not config.DATA_YAML.exists():
        write_data_yaml()
    best = train_yolo(epochs=a.epochs or 100, batch=a.batch)
    destino = config.WEIGHTS_DIR / "yolo_best_nuevo.pt"
    shutil.copy2(best, destino)
    print(f"Pesos nuevos en {destino}. NO reemplazan backend/modelos/best.pt automáticamente:")
    print("compáralos con evaluar_modelos.py y, si son mejores, cópialos a mano (ver docs/ia.md).")
else:
    from ml.models.unet_dual import train_unet
    val_json = config.VAL_COCO if config.VAL_COCO.exists() else None
    path, hist = train_unet(config.TRAIN_IMG_DIR, config.TRAIN_COCO,
                            out_path=config.WEIGHTS_DIR / "unet_best_nuevo.pth",
                            config.VAL_IMG_DIR if val_json else None, val_json,
                            epochs=a.epochs or 80, batch=a.batch,
                            use_weight_map=not a.sin_weight_map, resume_from=a.resume)
    import pandas as pd
    config.RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(hist).to_csv(config.RESULTS_DIR / "unet_historial.csv", index=False)
    print(f"Mejor modelo: {path}")
