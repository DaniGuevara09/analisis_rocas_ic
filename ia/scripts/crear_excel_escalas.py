"""Crea el Excel con número de imagen y escala del objeto de referencia.

Uso:
  python scripts/crear_excel_escalas.py --images data/raw/wilder --out data/escalas_imagenes.xlsx
  python scripts/crear_excel_escalas.py --leer data/escalas_imagenes.xlsx   # verifica factores
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ml.data.escalas import crear_plantilla, leer_escalas  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--images", help="carpeta con las imágenes (las de Wilder)")
ap.add_argument("--out", default="data/escalas_imagenes.xlsx")
ap.add_argument("--fuente", default="Wilder")
ap.add_argument("--leer", help="leer un Excel ya llenado y exportar calibracion.json")
a = ap.parse_args()

if a.leer:
    esc = leer_escalas(a.leer)
    out = Path(a.leer).with_name("calibracion.json")
    json.dump(esc, open(out, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    print(f"{len(esc)} imágenes con escala válida -> {out}")
    for k, v in list(esc.items())[:10]:
        print(f"  {v['n_imagen']:>4}  {k:<30} {v['factor_mm_px']:.4f} mm/px")
else:
    n = crear_plantilla(a.images, a.out, a.fuente)
    print(f"Plantilla creada con {n} imágenes: {a.out}")
