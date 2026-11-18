"""Prueba con el modelo real; se salta si best.pt o ultralytics no están disponibles.

Con `IMAGEN_PRUEBA_SEGMENTACION=<ruta a una foto real>` además exige al menos un polígono.
"""
import importlib.util
import io
import os
import time
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

RAIZ_BACKEND = Path(__file__).resolve().parents[2]
RUTA_MODELO = Path(os.getenv("RUTA_MODELO_PRUEBA", RAIZ_BACKEND / "modelos" / "best.pt"))
IMAGEN_REAL = os.getenv("IMAGEN_PRUEBA_SEGMENTACION")

pytestmark = pytest.mark.skipif(
    not RUTA_MODELO.is_file() or importlib.util.find_spec("ultralytics") is None,
    reason="Requiere backend/modelos/best.pt y el extra [yolo]",
)


def imagen_sintetica() -> bytes:
    """Imagen Full HD con elipses grises sobre fondo claro."""
    foto = Image.new("RGB", (1920, 1080), (205, 200, 190))
    dibujo = ImageDraw.Draw(foto)
    for i in range(40):
        x, y = 60 + (i % 10) * 180, 80 + (i // 10) * 240
        gris = (95 + i, 90 + i, 85 + i)
        dibujo.ellipse((x, y, x + 140, y + 110), fill=gris, outline=(40, 40, 40))
    salida = io.BytesIO()
    foto.save(salida, format="JPEG")
    return salida.getvalue()


def test_segmenta_y_devuelve_poligonos_dentro_de_la_imagen() -> None:
    from app.adaptadores.salida.segmentacion.segmentador_yolo import SegmentadorYOLO

    contenido = Path(IMAGEN_REAL).read_bytes() if IMAGEN_REAL else imagen_sintetica()
    ancho, alto = Image.open(io.BytesIO(contenido)).size
    segmentador = SegmentadorYOLO(str(RUTA_MODELO))

    inicio = time.perf_counter()
    poligonos = segmentador.segmentar(contenido)
    segundos = time.perf_counter() - inicio
    print(f"\nTiempo de inferencia: {segundos:.2f} s, {len(poligonos)} poligonos")

    if IMAGEN_REAL:
        assert len(poligonos) >= 1
    assert all(0 <= p.x <= ancho and 0 <= p.y <= alto for pol in poligonos for p in pol.puntos)
