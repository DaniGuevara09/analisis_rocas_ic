"""Adaptador del puerto `Segmentador` con YOLOv11m-seg (ultralytics)."""

import gc
import io
import logging
import math
import time
from collections.abc import Sequence
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
from app.dominio.modelo import AREA_MINIMA_FRAGMENTO_PX2, Poligono, Punto

IOU_NMS = 0.45
CONFIANZA_PINCEL = 0.05
LADO_MAX_PINCEL_YOLO = 640
MAX_DET_PINCEL = 60
UMBRAL_DENSIDAD_MALLA = 80
LADO_MAX_UNICO_YOLO = 1280
LADO_MAX_MALLA_YOLO = 640
MAX_DET_MALLA = 400
SOLAPE_MALLA = 0.22
IOU_CAJA_RESPALDO_CUBIERTO = 0.70
AREA_MINIMA_DETECCION_PX2 = 180.0

_LOG = logging.getLogger(__name__)
Caja = tuple[float, float, float, float]


def _ejes_cuadricula(
    total: int, partes: int, solape: float = SOLAPE_MALLA
) -> list[tuple[int, int]]:
    """Divide un eje `[0, total]` en `partes` tramos solapados."""
    if partes <= 1:
        return [(0, total)]
    paso_rel = 1.0 - solape
    tam = min(total, int(math.ceil(total / (1.0 + (partes - 1) * paso_rel))))
    if tam >= total:
        return [(0, total)]
    espacio = (total - tam) / (partes - 1)
    tramos: list[tuple[int, int]] = []
    for i in range(partes):
        inicio = total - tam if i == partes - 1 else int(round(i * espacio))
        tramos.append((inicio, inicio + tam))
    return tramos


def generar_cuadricula(
    ancho: int, alto: int, n_detecciones: int, solape: float = SOLAPE_MALLA
) -> list[tuple[int, int, int, int]]:
    """Genera mosaicos solapados (2x2 o 3x2/2x3) según la densidad detectada."""
    if n_detecciones <= 220:
        cols, filas = 2, 2
    elif ancho >= alto:
        cols, filas = 3, 2
    else:
        cols, filas = 2, 3
    xs = _ejes_cuadricula(ancho, cols, solape)
    ys = _ejes_cuadricula(alto, filas, solape)
    return [(x0, y0, x1, y1) for y0, y1 in ys for x0, x1 in xs]


def _redimensionar_si_supera(
    imagen: Image.Image, lado_max: int
) -> tuple[Image.Image, int, int]:
    w, h = imagen.size
    mayor = max(w, h)
    if mayor <= lado_max:
        return imagen, w, h
    escala = lado_max / mayor
    w_pred = max(32, int(round(w * escala)))
    h_pred = max(32, int(round(h * escala)))
    return imagen.resize((w_pred, h_pred), Image.Resampling.BILINEAR), w_pred, h_pred


def _bbox_poligono(poligono: Poligono) -> Caja:
    xs = [p.x for p in poligono.puntos]
    ys = [p.y for p in poligono.puntos]
    return min(xs), min(ys), max(xs), max(ys)


class _IndiceEspacial:
    """Rejilla espacial 2D para evitar comparaciones O(N²) entre polígonos lejanos."""

    def __init__(self, tam_celda: float) -> None:
        self._tam = max(16.0, float(tam_celda))
        self._celdas: dict[tuple[int, int], list[int]] = {}

    def _rango(self, box: Caja) -> tuple[int, int, int, int]:
        inv = 1.0 / self._tam
        return (
            int(math.floor(box[0] * inv)),
            int(math.floor(box[1] * inv)),
            int(math.floor(box[2] * inv)),
            int(math.floor(box[3] * inv)),
        )

    def agregar(self, idx: int, box: Caja) -> None:
        cx0, cy0, cx1, cy1 = self._rango(box)
        for cy in range(cy0, cy1 + 1):
            for cx in range(cx0, cx1 + 1):
                clave = (cx, cy)
                cubo = self._celdas.get(clave)
                if cubo is None:
                    self._celdas[clave] = [idx]
                else:
                    cubo.append(idx)

    def candidatos(self, box: Caja) -> set[int]:
        cx0, cy0, cx1, cy1 = self._rango(box)
        vistos: set[int] = set()
        for cy in range(cy0, cy1 + 1):
            for cx in range(cx0, cx1 + 1):
                cubo = self._celdas.get((cx, cy))
                if cubo is not None:
                    vistos.update(cubo)
        return vistos


def _tamano_celda_para_cajas(cajas: Sequence[Caja]) -> float:
    if not cajas:
        return 128.0
    lados = sorted(max(b[2] - b[0], b[3] - b[1]) for b in cajas)
    mediana = lados[len(lados) // 2]
    max_x = max(b[2] for b in cajas) - min(b[0] for b in cajas)
    max_y = max(b[3] for b in cajas) - min(b[1] for b in cajas)
    piso_ext = max(max_x, max_y) / 32.0
    return max(32.0, min(512.0, max(mediana * 2.0, piso_ext)))


def _iou_cajas(box_a: Caja, box_b: Caja) -> float:
    ix0 = max(box_a[0], box_b[0])
    iy0 = max(box_a[1], box_b[1])
    ix1 = min(box_a[2], box_b[2])
    iy1 = min(box_a[3], box_b[3])
    if ix1 <= ix0 or iy1 <= iy0:
        return 0.0
    inter = (ix1 - ix0) * (iy1 - iy0)
    area_a = max(1.0, (box_a[2] - box_a[0]) * (box_a[3] - box_a[1]))
    area_b = max(1.0, (box_b[2] - box_b[0]) * (box_b[3] - box_b[1]))
    return inter / max(1.0, area_a + area_b - inter)


def _filtrar_indices_respaldo(
    cajas_respaldo: Sequence[Caja],
    cajas_primarias: Sequence[Caja],
    iou_min: float = IOU_CAJA_RESPALDO_CUBIERTO,
) -> list[int]:
    """Devuelve solo los índices globales que no están ya cubiertos por un mosaico."""
    if not cajas_respaldo:
        return []
    if not cajas_primarias:
        return list(range(len(cajas_respaldo)))

    indice = _IndiceEspacial(_tamano_celda_para_cajas(cajas_primarias))
    for i, box in enumerate(cajas_primarias):
        indice.agregar(i, box)

    pendientes: list[int] = []
    for idx, box in enumerate(cajas_respaldo):
        cubierto = False
        for j in indice.candidatos(box):
            if _iou_cajas(box, cajas_primarias[j]) >= iou_min:
                cubierto = True
                break
        if not cubierto:
            pendientes.append(idx)
    return pendientes


def _se_superponen_mucho(
    pol_a: Poligono,
    box_a: Caja,
    pol_b: Poligono,
    box_b: Caja,
) -> bool:
    """Comprueba solapamiento real entre dos polígonos con cajas coincidentes."""
    ix0 = max(box_a[0], box_b[0])
    iy0 = max(box_a[1], box_b[1])
    ix1 = min(box_a[2], box_b[2])
    iy1 = min(box_a[3], box_b[3])
    if ix1 <= ix0 or iy1 <= iy0:
        return False
    area_inter_box = (ix1 - ix0) * (iy1 - iy0)
    area_box_a = max(1.0, (box_a[2] - box_a[0]) * (box_a[3] - box_a[1]))
    area_box_b = max(1.0, (box_b[2] - box_b[0]) * (box_b[3] - box_b[1]))
    if area_inter_box / min(area_box_a, area_box_b) < 0.35:
        return False

    try:
        import cv2  # type: ignore[import-not-found]
    except ImportError:
        area_union = max(1.0, area_box_a + area_box_b - area_inter_box)
        return (
            (area_inter_box / area_union) >= 0.40
            or (area_inter_box / min(area_box_a, area_box_b)) >= 0.60
        )

    ux0 = min(box_a[0], box_b[0])
    uy0 = min(box_a[1], box_b[1])
    ux1 = max(box_a[2], box_b[2])
    uy1 = max(box_a[3], box_b[3])
    uw = max(1e-6, ux1 - ux0)
    uh = max(1e-6, uy1 - uy0)
    tam = 32
    pts_a = np.array(
        [[[int(round((p.x - ux0) * (tam - 1) / uw)), int(round((p.y - uy0) * (tam - 1) / uh))]
          for p in pol_a.puntos]],
        dtype=np.int32,
    )
    pts_b = np.array(
        [[[int(round((p.x - ux0) * (tam - 1) / uw)), int(round((p.y - uy0) * (tam - 1) / uh))]
          for p in pol_b.puntos]],
        dtype=np.int32,
    )
    ma = np.zeros((tam, tam), dtype=np.uint8)
    mb = np.zeros((tam, tam), dtype=np.uint8)
    cv2.fillPoly(ma, pts_a, (1,))
    cv2.fillPoly(mb, pts_b, (1,))
    inter = int(np.count_nonzero(ma & mb))
    if inter == 0:
        return False
    union = int(np.count_nonzero(ma | mb))
    ca = int(np.count_nonzero(ma))
    cb = int(np.count_nonzero(mb))
    return (inter / union) >= 0.35 or (inter / min(ca, cb)) >= 0.55


def fusionar_detecciones(
    primarias: Sequence[tuple[Poligono, float]],
    respaldo: Sequence[tuple[Poligono, float]],
) -> list[Poligono]:
    """Deduplica detecciones entre mosaicos usando rejilla espacial O(N)."""
    ordenadas = [
        *(sorted(primarias, key=lambda item: item[1], reverse=True)),
        *(sorted(respaldo, key=lambda item: item[1], reverse=True)),
    ]
    if not ordenadas:
        return []
    con_cajas = [(pol, _bbox_poligono(pol)) for pol, _conf in ordenadas]
    indice = _IndiceEspacial(_tamano_celda_para_cajas([box for _, box in con_cajas]))
    aceptados: list[tuple[Poligono, Caja]] = []
    for pol, box in con_cajas:
        duplicado = False
        for idx_ok in indice.candidatos(box):
            pol_ok, box_ok = aceptados[idx_ok]
            if box[2] <= box_ok[0] or box_ok[2] <= box[0]:
                continue
            if box[3] <= box_ok[1] or box_ok[3] <= box[1]:
                continue
            if _se_superponen_mucho(pol, box, pol_ok, box_ok):
                duplicado = True
                break
        if not duplicado:
            indice.agregar(len(aceptados), box)
            aceptados.append((pol, box))
    return [pol for pol, _box in aceptados]


def _area_minima_segmentacion(ancho_img: int, alto_img: int) -> float:
    """Excluye motas no resolubles (~15 px de diámetro) manteniendo rocas medibles."""
    return max(
        AREA_MINIMA_FRAGMENTO_PX2,
        min(AREA_MINIMA_DETECCION_PX2, float(ancho_img * alto_img) * 0.0005),
    )


def _extraer_detecciones_retina(
    resultado: Any,
    caja: tuple[int, int, int, int],
    tam_pred: tuple[int, int],
    ancho_img: int,
    alto_img: int,
    filtrar_costura: bool,
    recorte_rgb: np.ndarray | None = None,
    unet: Any | None = None,
) -> list[tuple[Poligono, float]]:
    """Convierte máscaras `retina_masks=True` a polígonos simples sin líneas puente."""
    if resultado.masks is None:
        return []
    import cv2  # type: ignore[import-not-found]

    tx0, ty0, tx1, ty1 = caja
    w_pred, h_pred = tam_pred
    escala_x = (tx1 - tx0) / max(1, w_pred)
    escala_y = (ty1 - ty0) / max(1, h_pred)
    margen_borde = max(8.0, escala_x * 2.5, escala_y * 2.5)
    area_minima = _area_minima_segmentacion(ancho_img, alto_img)

    boxes = getattr(resultado, "boxes", None)
    confs = (
        boxes.conf.cpu().numpy()
        if boxes is not None and getattr(boxes, "conf", None) is not None
        else None
    )
    xyxy = (
        boxes.xyxy.cpu().numpy()
        if boxes is not None and getattr(boxes, "xyxy", None) is not None
        else None
    )

    usar_unet = unet is not None and recorte_rgb is not None
    fg_mapa = bd_mapa = None
    if usar_unet:
        fg_mapa, bd_mapa = unet.mapas_probabilidad(recorte_rgb)

    mascaras_np = resultado.masks.data.cpu().numpy()
    salida: list[tuple[Poligono, float]] = []
    pad_px = 6 if usar_unet else 2

    for idx, m in enumerate(mascaras_np):
        hm, wm = m.shape[:2]
        if xyxy is not None and idx < len(xyxy):
            bx0, by0, bx1, by1 = (float(v) for v in xyxy[idx])
            mx0 = max(0, int(math.floor(bx0 * wm / w_pred)) - pad_px)
            my0 = max(0, int(math.floor(by0 * hm / h_pred)) - pad_px)
            mx1 = min(wm, int(math.ceil(bx1 * wm / w_pred)) + pad_px + 1)
            my1 = min(hm, int(math.ceil(by1 * hm / h_pred)) + pad_px + 1)
        else:
            ys, xs = np.where(m > 0.5)
            if len(xs) == 0:
                continue
            mx0 = max(0, int(xs.min()) - pad_px)
            my0 = max(0, int(ys.min()) - pad_px)
            mx1 = min(wm, int(xs.max()) + pad_px + 1)
            my1 = min(hm, int(ys.max()) + pad_px + 1)

        if mx1 <= mx0 or my1 <= my0:
            continue
        m_crop = (m[my0:my1, mx0:mx1] > 0.5).astype(np.uint8)
        if not np.any(m_crop):
            continue

        if usar_unet and fg_mapa is not None and bd_mapa is not None:
            if hm != h_pred or wm != w_pred:
                fx0 = max(0, min(w_pred - 1, int(math.floor(mx0 * w_pred / wm))))
                fy0 = max(0, min(h_pred - 1, int(math.floor(my0 * h_pred / hm))))
                fx1 = max(fx0 + 1, min(w_pred, int(math.ceil(mx1 * w_pred / wm))))
                fy1 = max(fy0 + 1, min(h_pred, int(math.ceil(my1 * h_pred / hm))))
                fg_crop = cv2.resize(
                    fg_mapa[fy0:fy1, fx0:fx1],
                    (m_crop.shape[1], m_crop.shape[0]),
                    interpolation=cv2.INTER_LINEAR,
                )
                bd_crop = cv2.resize(
                    bd_mapa[fy0:fy1, fx0:fx1],
                    (m_crop.shape[1], m_crop.shape[0]),
                    interpolation=cv2.INTER_LINEAR,
                )
            else:
                fg_crop = fg_mapa[my0:my1, mx0:mx1]
                bd_crop = bd_mapa[my0:my1, mx0:mx1]
            m_crop = unet.refinar_mascara_recorte(
                m_crop, fg_crop, bd_crop, radio_expand=2, radio_recorte=1
            )

        c_cv, _ = cv2.findContours(m_crop, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not c_cv:
            continue
        # Usar solo el contorno mayor evita las líneas puente de `masks.xy`.
        mayor = max(c_cv, key=cv2.contourArea)
        if len(mayor) < 3:
            continue
        sx = (tx1 - tx0) / max(1, wm)
        sy = (ty1 - ty0) / max(1, hm)
        globales = [
            ((mx0 + float(pt[0][0])) * sx + tx0, (my0 + float(pt[0][1])) * sy + ty0)
            for pt in mayor
        ]
        if filtrar_costura and _toca_costura(globales, caja, ancho_img, alto_img, margen_borde):
            continue
        poligonos = poligonos_desde_contornos(
            [globales], ancho_img, alto_img, area_minima_px=area_minima
        )
        if poligonos:
            conf = float(confs[idx]) if confs is not None and idx < len(confs) else 0.5
            salida.append((poligonos[0], conf))

    del fg_mapa, bd_mapa, mascaras_np
    return salida


def _toca_costura(
    globales: Sequence[tuple[float, float]],
    caja: tuple[int, int, int, int],
    ancho_img: int,
    alto_img: int,
    margen_borde: float,
) -> bool:
    tx0, ty0, tx1, ty1 = caja
    xs = [p[0] for p in globales]
    ys = [p[1] for p in globales]
    return (
        (tx0 > 0 and min(xs) <= tx0 + margen_borde)
        or (tx1 < ancho_img and max(xs) >= tx1 - margen_borde)
        or (ty0 > 0 and min(ys) <= ty0 + margen_borde)
        or (ty1 < alto_img and max(ys) >= ty1 - margen_borde)
    )


def _extraer_contornos_mascaras(
    mascaras_u8: np.ndarray,
    confs: np.ndarray | None,
    xyxy: np.ndarray | None,
    tam_img: tuple[int, int],
    indices: Sequence[int] | None = None,
) -> list[tuple[Poligono, float]]:
    """Convierte máscaras YOLO a polígonos respetando letterbox y con mínimo uso de RAM."""
    import cv2  # type: ignore[import-not-found]

    w, h = tam_img
    area_minima = _area_minima_segmentacion(w, h)
    objetivos = range(len(mascaras_u8)) if indices is None else indices

    salida: list[tuple[Poligono, float]] = []
    for idx in objetivos:
        m = mascaras_u8[idx]
        hm, wm = m.shape[:2]
        gain = min(hm / h, wm / w)
        pad_x = (wm - w * gain) / 2.0
        pad_y = (hm - h * gain) / 2.0

        if xyxy is not None and idx < len(xyxy):
            bx0, by0, bx1, by1 = (float(v) for v in xyxy[idx])
            mx0 = max(0, int(math.floor(bx0 * gain + pad_x)) - 2)
            my0 = max(0, int(math.floor(by0 * gain + pad_y)) - 2)
            mx1 = min(wm, int(math.ceil(bx1 * gain + pad_x)) + 3)
            my1 = min(hm, int(math.ceil(by1 * gain + pad_y)) + 3)
        else:
            ys, xs = np.where(m > 0)
            if len(xs) == 0:
                continue
            mx0 = max(0, int(xs.min()) - 2)
            my0 = max(0, int(ys.min()) - 2)
            mx1 = min(wm, int(xs.max()) + 3)
            my1 = min(hm, int(ys.max()) + 3)

        if mx1 <= mx0 or my1 <= my0:
            continue
        recorte_m = m[my0:my1, mx0:mx1].astype(np.float32)
        if not np.any(recorte_m):
            continue
        mh_c, mw_c = recorte_m.shape[:2]
        factor = 1 if (hm, wm) == (h, w) else max(1, min(8, int(math.ceil(0.5 / gain))))

        if factor > 1:
            suave = cv2.resize(
                recorte_m, (mw_c * factor, mh_c * factor), interpolation=cv2.INTER_CUBIC
            )
            k_suave = (max(3, factor // 2) | 1)
            if min(suave.shape[:2]) >= k_suave:
                suave = cv2.GaussianBlur(suave, (k_suave, k_suave), 0)
            binaria = (suave > 0.5).astype(np.uint8)
        else:
            binaria = (recorte_m > 0.5).astype(np.uint8)

        c_cv, _ = cv2.findContours(binaria, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not c_cv:
            continue
        mayor = max(c_cv, key=cv2.contourArea)
        if len(mayor) < 3:
            continue
        offset = 0.0 if factor == 1 else (0.5 / factor - 0.5)
        contorno = [
            (
                (mx0 + float(pt[0][0]) / factor + offset - pad_x) / gain,
                (my0 + float(pt[0][1]) / factor + offset - pad_y) / gain,
            )
            for pt in mayor
        ]
        poligonos = poligonos_desde_contornos([contorno], w, h, area_minima_px=area_minima)
        if poligonos:
            conf = float(confs[idx]) if confs is not None and idx < len(confs) else 0.5
            salida.append((poligonos[0], conf))

    return salida


class SegmentadorYOLO:
    """Carga YOLO (y opcionalmente U-Net para bordes) y devuelve polígonos en px originales."""

    def __init__(
        self,
        ruta_modelo: str,
        confianza: float = 0.25,
        imgsz: int = 640,
        max_det: int = 1000,
        ruta_unet: str | None = None,
        refinar_con_unet: bool = False,
    ) -> None:
        # Import diferido: las pruebas unitarias no cargan torch ni ultralytics.
        from ultralytics import YOLO  # type: ignore[import-not-found]

        self._modelo: Any = YOLO(ruta_modelo)
        self._confianza = confianza
        self._imgsz = imgsz
        self._max_det = max_det
        self._unet: Any = None
        if ruta_unet and Path(ruta_unet).is_file():
            from app.adaptadores.salida.segmentacion.unet_bordes import RefinadorUNet

            self._unet = RefinadorUNet(ruta_unet)
        self._refinar_con_unet = bool(refinar_con_unet and self._unet is not None)
        _LOG.info(
            "SegmentadorYOLO listo (unet_pincel=%s, unet_auto=%s)",
            bool(self._unet),
            self._refinar_con_unet,
        )

    def segmentar(self, imagen: bytes) -> list[Poligono]:
        """Ejecuta YOLO con `retina_masks=True` por mosaicos si hay muchas rocas (baja RAM)."""
        t0 = time.perf_counter()
        foto = Image.open(io.BytesIO(imagen)).convert("RGB")
        w, h = foto.size
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

        n_det = len(resultado.masks)
        mascaras_u8 = (resultado.masks.data.cpu().numpy() > 0.5).astype(np.uint8)
        boxes = getattr(resultado, "boxes", None)
        confs = (
            boxes.conf.cpu().numpy()
            if boxes is not None and getattr(boxes, "conf", None) is not None
            else None
        )
        xyxy = (
            boxes.xyxy.cpu().numpy()
            if boxes is not None and getattr(boxes, "xyxy", None) is not None
            else None
        )
        del resultado
        gc.collect()
        t_global = time.perf_counter() - t0

        unet_auto = self._unet if self._refinar_con_unet else None
        t_malla_ini = time.perf_counter()
        modo = "unico"
        if n_det <= UMBRAL_DENSIDAD_MALLA:
            foto_pred, w_pred, h_pred = _redimensionar_si_supera(foto, LADO_MAX_UNICO_YOLO)
            res_alta = self._modelo.predict(
                foto_pred,
                imgsz=self._imgsz,
                conf=self._confianza,
                iou=IOU_NMS,
                max_det=self._max_det,
                retina_masks=True,
                verbose=False,
            )[0]
            foto_rgb = np.array(foto_pred, dtype=np.uint8) if unet_auto is not None else None
            primarias = _extraer_detecciones_retina(
                res_alta,
                (0, 0, w, h),
                (w_pred, h_pred),
                w,
                h,
                filtrar_costura=False,
                recorte_rgb=foto_rgb,
                unet=unet_auto,
            )
            del res_alta, foto_rgb
            gc.collect()
        else:
            cuadricula = generar_cuadricula(w, h, n_det)
            modo = f"malla({len(cuadricula)})"
            primarias = []
            for caja in cuadricula:
                tx0, ty0, tx1, ty1 = caja
                recorte = foto.crop((tx0, ty0, tx1, ty1))
                recorte_pred, w_pred, h_pred = _redimensionar_si_supera(
                    recorte, LADO_MAX_MALLA_YOLO
                )
                res_tile = self._modelo.predict(
                    recorte_pred,
                    imgsz=self._imgsz,
                    conf=self._confianza,
                    iou=IOU_NMS,
                    max_det=MAX_DET_MALLA,
                    retina_masks=True,
                    verbose=False,
                )[0]
                recorte_rgb = (
                    np.array(recorte_pred, dtype=np.uint8) if unet_auto is not None else None
                )
                primarias.extend(
                    _extraer_detecciones_retina(
                        res_tile,
                        caja,
                        (w_pred, h_pred),
                        w,
                        h,
                        filtrar_costura=True,
                        recorte_rgb=recorte_rgb,
                        unet=unet_auto,
                    )
                )
                del res_tile, recorte_rgb
                gc.collect()
        t_malla = time.perf_counter() - t_malla_ini

        t_resp_ini = time.perf_counter()
        indices_resp: list[int] | None = None
        if primarias and xyxy is not None:
            cajas_primarias = [_bbox_poligono(p) for p, _ in primarias]
            cajas_resp: list[Caja] = [
                (float(b[0]), float(b[1]), float(b[2]), float(b[3])) for b in xyxy
            ]
            indices_resp = _filtrar_indices_respaldo(cajas_resp, cajas_primarias)
        respaldo = _extraer_contornos_mascaras(
            mascaras_u8, confs, xyxy, (w, h), indices=indices_resp
        )
        del mascaras_u8
        t_resp = time.perf_counter() - t_resp_ini

        t_fus_ini = time.perf_counter()
        if primarias:
            salida = fusionar_detecciones(primarias, respaldo)
        else:
            salida = [p for p, _ in respaldo]
        t_fus = time.perf_counter() - t_fus_ini
        _LOG.info(
            "Segmentación %dx%d [%s, unet=%s]: global=%d (%.2fs), malla=%d (%.2fs), "
            "respaldo=%d (%.2fs), fusion=%d (%.2fs), total=%.2fs",
            w,
            h,
            modo,
            self._refinar_con_unet,
            n_det,
            t_global,
            len(primarias),
            t_malla,
            len(respaldo),
            t_resp,
            len(salida),
            t_fus,
            time.perf_counter() - t0,
        )
        return salida

    def segmentar_zona(
        self, imagen: bytes, trazo: list[Punto], radio_px: float
    ) -> Poligono | None:
        """Segmenta con YOLO multiescala; si no detecta, usa U-Net o Watershed."""
        foto = Image.open(io.BytesIO(imagen)).convert("RGB")
        cajas = cajas_para_trazo(foto.width, foto.height, trazo, radio_px)
        for caja in cajas:
            x0, y0, x1, y1 = caja
            recorte = foto.crop((x0, y0, x1, y1))
            w_rec, h_rec = recorte.size
            lado_max = max(w_rec, h_rec)
            if lado_max > LADO_MAX_PINCEL_YOLO:
                escala = LADO_MAX_PINCEL_YOLO / lado_max
                w_pred = max(32, int(round(w_rec * escala)))
                h_pred = max(32, int(round(h_rec * escala)))
                recorte_pred = recorte.resize((w_pred, h_pred), Image.Resampling.BILINEAR)
            else:
                recorte_pred = recorte
                w_pred, h_pred = w_rec, h_rec
            resultado = self._modelo.predict(
                recorte_pred,
                imgsz=self._imgsz,
                conf=min(self._confianza, CONFIANZA_PINCEL),
                iou=IOU_NMS,
                max_det=MAX_DET_PINCEL,
                retina_masks=True,
                verbose=False,
            )[0]
            if resultado.masks is not None:
                candidatos = mascaras_a_poligonos_limpios(
                    resultado.masks.data.cpu().numpy(),
                    caja,
                    foto.width,
                    foto.height,
                    tam_inferencia=(w_pred, h_pred),
                )
                elegido = mejor_poligono_para_trazo(
                    candidatos,
                    trazo,
                    radio_px,
                    caja=caja,
                    ancho_img=foto.width,
                    alto_img=foto.height,
                )
            else:
                elegido = None
            del resultado
            gc.collect()
            if elegido is not None:
                return elegido
        if self._unet is not None:
            elegido_unet = self._unet.segmentar_zona(foto, trazo, radio_px)
            if elegido_unet is not None:
                return elegido_unet
        return segmentar_recorte_grabcut(foto, trazo, radio_px)
