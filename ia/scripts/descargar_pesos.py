"""Descarga los pesos entrenados desde GitHub Releases (o cualquier URL).

Los pesos NO van dentro del historial de Git:
  - unet_dual_best.pth pesa ~133 MB y GitHub rechaza archivos > 100 MB.
  - Cada reentrenamiento agregaría otros 45-130 MB al repo para siempre.

Flujo: subir los .pt/.pth como "assets" de un Release (p. ej. tag v1.0-modelos)
y poner aquí las URLs. El backend/Docker ejecuta este script al construir.

  python scripts/descargar_pesos.py            # descarga los que falten
  python scripts/descargar_pesos.py --forzar   # vuelve a descargar todos
"""
import argparse
import hashlib
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ml import config  # noqa: E402

REPO = "DaniGuevara09/analisis_rocas_ic"
TAG = "v1.0-modelos"
PESOS = {
    # archivo local: (url, sha256 opcional para verificar integridad)
    "YOLO": (f"https://github.com/{REPO}/releases/download/{TAG}/best.pt", None),
    "UNET": (f"https://github.com/{REPO}/releases/download/{TAG}/unet_best.pth", None),
    "MOBILESAM": ("https://github.com/ChaoningZhang/MobileSAM/raw/master/weights/mobile_sam.pt", None),
}


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


ap = argparse.ArgumentParser()
ap.add_argument("--forzar", action="store_true")
a = ap.parse_args()
config.WEIGHTS_DIR.mkdir(parents=True, exist_ok=True)
DESTINOS = {"YOLO": config.YOLO_WEIGHTS, "UNET": config.UNET_WEIGHTS,
            "MOBILESAM": config.MOBILESAM_WEIGHTS}
for clave, (url, digest) in PESOS.items():
    dst = DESTINOS[clave]
    dst.parent.mkdir(parents=True, exist_ok=True)
    name = dst.name
    if dst.exists() and not a.forzar:
        print(f"✓ {name} ya existe ({dst.stat().st_size / 1e6:.1f} MB)")
        continue
    print(f"↓ {name}  <-  {url}")
    try:
        urllib.request.urlretrieve(url, dst)
    except Exception as e:  # noqa: BLE001
        print(f"  ✗ no se pudo descargar ({e}). ¿Ya se publicó el Release {TAG}?")
        continue
    if digest and sha256(dst) != digest:
        dst.unlink()
        print("  ✗ checksum incorrecto, archivo eliminado")
