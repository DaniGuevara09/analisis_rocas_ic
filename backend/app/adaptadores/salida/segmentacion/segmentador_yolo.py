"""Adaptador del puerto `Segmentador` con YOLOv11m-seg (ultralytics)."""

import io
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from app.adaptadores.salida.segmentacion.contornos import poligonos_desde_contornos
from app.adaptadores.salida.segmentacion.pincel import (
    cajas_para_trazo,
    mascaras_a_poligonos_limpios,
    mejor_poligono_para_trazo,
    segmentar_recorte_grabcut,
)
from app.dominio.modelo import Poligono, Punto

IOU_NMS = 0.5
CONFIANZA_PINCEL = 0.05


class SegmentadorYOLO:
    """Carga YOLO (y opcionalmente U-Net para bordes) y devuelve polígonos en px originales."""

    def __init__(
        self,
        ruta_modelo: str,
        confianza: float = 0.25,
        imgsz: int = 640,
        max_det: int = 1000,
        ruta_unet: str | None = None,
    ) -> None:
        from ultralytics import YOLO  # import diferido: las pruebas no cargan torch

        self._modelo: Any = YOLO(ruta_modelo)
        self._confianza = confianza
        self._imgsz = imgsz
        self._max_det = max_det
        self._unet: Any = None
        if ruta_unet and Path(ruta_unet).is_file():
            from app.adaptadores.salida.segmentacion.unet_bordes import RefinadorUNet

            self._unet = RefinadorUNet(ruta_unet)

    def segmentar(self, imagen: bytes) -> list[Poligono]:
        """Ejecuta la inferencia (y refina bordes si U-Net está disponible)."""
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
        if self._unet is not None:
            import cv2

            img_rgb = np.array(foto, dtype=np.uint8)
            h, w = img_rgb.shape[:2]
            mascaras = []
            for m in resultado.masks.data.cpu().numpy():
                if m.shape != (h, w):
                    m = cv2.resize(m, (w, h), interpolation=cv2.INTER_NEAREST)
                mascaras.append((m > 0.5).astype(np.uint8))
            refinadas = self._unet.refinar_mascaras(img_rgb, mascaras)
            contornos = []
            for m in refinadas:
                c_cv, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                if c_cv:
                    mayor = max(c_cv, key=cv2.contourArea)
                    if len(mayor) >= 3:
                        contornos.append([(float(pt[0][0]), float(pt[0][1])) for pt in mayor])
            return poligonos_desde_contornos(contornos, w, h)
        return poligonos_desde_contornos(resultado.masks.xy, foto.width, foto.height)

    def segmentar_zona(
        self, imagen: bytes, trazo: list[Punto], radio_px: float
    ) -> Poligono | None:
        """Segmenta con YOLO probando contexto multi-escala; si no detecta, usa U-Net o Watershed."""
        foto = Image.open(io.BytesIO(imagen)).convert("RGB")
        cajas = cajas_para_trazo(foto.width, foto.height, trazo, radio_px)
        for caja in cajas:
            x0, y0, x1, y1 = caja
            recorte = foto.crop((x0, y0, x1, y1))
            resultado = self._modelo.predict(
                recorte,
                imgsz=self._imgsz,
                conf=min(self._confianza, CONFIANZA_PINCEL),
                iou=IOU_NMS,
                max_det=200,
                retina_masks=True,
                verbose=False,
            )[0]
            if resultado.masks is not None:
                candidatos = mascaras_a_poligonos_limpios(
                    resultado.masks.data.cpu().numpy(),
                    caja,
                    foto.width,
                    foto.height,
                )
                elegido = mejor_poligono_para_trazo(
                    candidatos,
                    trazo,
                    radio_px,
                    caja=caja,
                    ancho_img=foto.width,
                    alto_img=foto.height,
                )
                if elegido is not None:
                    return elegido
        if self._unet is not None:
            elegido_unet = self._unet.segmentar_zona(foto, trazo, radio_px)
            if elegido_unet is not None:
                return elegido_unet
        return segmentar_recorte_grabcut(foto, trazo, radio_px)
