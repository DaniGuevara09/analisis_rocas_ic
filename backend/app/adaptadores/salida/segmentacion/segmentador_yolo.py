"""Adaptador del puerto `Segmentador` con YOLOv11m-seg (ultralytics)."""
import io
from typing import Any

from PIL import Image

from app.adaptadores.salida.segmentacion.contornos import poligonos_desde_contornos
from app.dominio.modelo import Poligono

IOU_NMS = 0.5


class SegmentadorYOLO:
    """Carga el modelo una sola vez y devuelve polígonos en píxeles de la imagen original."""

    def __init__(
        self,
        ruta_modelo: str,
        confianza: float = 0.25,
        imgsz: int = 640,
        max_det: int = 1000,
    ) -> None:
        from ultralytics import YOLO  # import diferido: las pruebas no cargan torch

        self._modelo: Any = YOLO(ruta_modelo)
        self._confianza = confianza
        self._imgsz = imgsz
        self._max_det = max_det

    def segmentar(self, imagen: bytes) -> list[Poligono]:
        """Ejecuta la inferencia y convierte las máscaras en polígonos."""
        foto = Image.open(io.BytesIO(imagen)).convert("RGB")
        resultado = self._modelo.predict(
            foto,
            imgsz=self._imgsz,
            conf=self._confianza,
            iou=IOU_NMS,
            max_det=self._max_det,
            retina_masks=False,
            verbose=False,
        )[0]
        if resultado.masks is None:
            return []
        return poligonos_desde_contornos(resultado.masks.xy, foto.width, foto.height)
