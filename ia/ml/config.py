"""Configuración central del módulo de IA.

Todas las rutas se pueden sobreescribir con variables de entorno para que el
mismo código funcione en local, en Google Colab y dentro de Docker.
"""
import os
from pathlib import Path

ROOT = Path(os.getenv("ROCAS_ROOT", Path(__file__).resolve().parents[1]))   # carpeta ia/
REPO_ROOT = ROOT.parent                                                       # raíz del repo

DATA_DIR = Path(os.getenv("ROCAS_DATA", ROOT / "data"))
DATASET_ROOT = Path(os.getenv("ROCAS_DATASET", DATA_DIR / "dataset"))
TRAIN_IMG_DIR = DATASET_ROOT / "images" / "train"
VAL_IMG_DIR = DATASET_ROOT / "images" / "val"
TEST_IMG_DIR = DATASET_ROOT / "images" / "test"
ANN_DIR = DATASET_ROOT / "annotations"
TRAIN_COCO = ANN_DIR / "train_coco.json"
VAL_COCO = ANN_DIR / "val_coco.json"
TEST_COCO = ANN_DIR / "test_coco.json"
DATA_YAML = DATASET_ROOT / "data.yaml"

# Excel con la escala de cada imagen (corrección del profesor)
ESCALAS_XLSX = Path(os.getenv("ROCAS_ESCALAS", DATA_DIR / "escalas_imagenes.xlsx"))

WEIGHTS_DIR = Path(os.getenv("ROCAS_WEIGHTS", ROOT / "pesos"))
# YOLO usa EL MISMO archivo que carga el backend (RUTA_MODELO = backend/modelos/best.pt),
# así lo que se evalúa aquí es exactamente lo que corre en la aplicación.
YOLO_WEIGHTS = Path(os.getenv("ROCAS_YOLO", REPO_ROOT / "backend" / "modelos" / "best.pt"))
UNET_WEIGHTS = Path(os.getenv("ROCAS_UNET", WEIGHTS_DIR / "unet_best.pth"))   # nombre usado en Drive
MOBILESAM_WEIGHTS = WEIGHTS_DIR / "mobile_sam.pt"

RESULTS_DIR = Path(os.getenv("ROCAS_RESULTS", ROOT / "results"))

# Clases: 0 = roca. La clase "referencia" (objeto de calibración) se anota
# aparte para poder excluirla del cálculo granulométrico.
CLASS_NAMES = ["rock"]
REFERENCE_CLASS = "referencia"

IMG_SIZE_YOLO = 640
IMG_SIZE_UNET = 512


def device() -> str:
    try:
        import torch
        return "cuda" if torch.cuda.is_available() else "cpu"
    except ImportError:
        return "cpu"
