"""Herramienta local para marcar los 2 puntos del objeto de referencia con el
mouse y escribirlos directamente en el Excel de escalas.

Uso (en un PC con pantalla, no en Colab):
  python scripts/marcar_escala.py --xlsx data/escalas_imagenes.xlsx --images data/raw/wilder \
      --longitud 300 --objeto Regla --anotador Bibian

Controles: clic izquierdo = punto (2 por imagen) | r = reiniciar | n = siguiente
           s = saltar | q = salir. Se pregunta la longitud real si no se pasa --longitud.
"""
import argparse
import sys
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ml.data.escalas import escribir_puntos, leer_escalas  # noqa: E402
from ml.data.coco_utils import IMG_EXTS  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--xlsx", required=True)
ap.add_argument("--images", required=True)
ap.add_argument("--longitud", type=float, help="longitud real en mm (si es la misma para todas)")
ap.add_argument("--objeto", default=None)
ap.add_argument("--anotador", default=None)
ap.add_argument("--solo-pendientes", action="store_true", help="omitir imágenes ya calibradas")
ap.add_argument("--max-lado", type=int, default=1400, help="tamaño máximo de la ventana")
a = ap.parse_args()

hechas = set(leer_escalas(a.xlsx)) if a.solo_pendientes else set()
paths = [p for p in sorted(Path(a.images).iterdir()) if p.suffix.lower() in IMG_EXTS and p.name not in hechas]
pts = []


def on_mouse(ev, x, y, *_):
    if ev == cv2.EVENT_LBUTTONDOWN and len(pts) < 2:
        pts.append((x, y))


cv2.namedWindow("escala", cv2.WINDOW_NORMAL)
cv2.setMouseCallback("escala", on_mouse)
for p in paths:
    img = cv2.imread(str(p))
    s = min(1.0, a.max_lado / max(img.shape[:2]))
    view = cv2.resize(img, None, fx=s, fy=s)
    pts.clear()
    while True:
        canvas = view.copy()
        for q in pts:
            cv2.circle(canvas, q, 5, (0, 255, 255), -1)
        if len(pts) == 2:
            cv2.line(canvas, pts[0], pts[1], (0, 255, 255), 2)
        cv2.putText(canvas, f"{p.name}  puntos: {len(pts)}/2  [n]=guardar [r]=reiniciar [s]=saltar [q]=salir",
                    (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
        cv2.imshow("escala", canvas)
        k = cv2.waitKey(20) & 0xFF
        if k == ord("r"):
            pts.clear()
        elif k == ord("s"):
            break
        elif k == ord("q"):
            sys.exit(0)
        elif k == ord("n") and len(pts) == 2:
            (x1, y1), (x2, y2) = [(u / s, v / s) for u, v in pts]  # a coordenadas originales
            L = a.longitud or float(input(f"Longitud real (mm) del objeto en {p.name}: "))
            escribir_puntos(a.xlsx, p.name, x1, y1, x2, y2, L, a.objeto, a.anotador)
            print(f"{p.name}: guardado")
            break
cv2.destroyAllWindows()
