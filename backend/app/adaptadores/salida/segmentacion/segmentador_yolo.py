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
UMBRAL_DENSIDAD_MALLA = 220
LADO_MAX_UNICO_YOLO = 1024
LADO_MAX_MALLA_YOLO = 640
MAX_DET_MALLA = 400
SOLAPE_MALLA = 0.22
IOU_CAJA_RESPALDO_CUBIERTO = 0.70
AREA_MINIMA_DETECCION_PX2 = 180.0
SOLIDEZ_MINIMA_ROCA = 0.50
ASPECTO_MAXIMO_ROCA = 6.5
UMBRAL_CONF_CONFIABLE_YOLO = 0.25
UMBRAL_FG_UNET_MIN = 0.35
FRACCION_MINIMA_TRAS_PARTICION = 0.40

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


def _fusionar_detecciones_con_confianza(
    primarias: Sequence[tuple[Poligono, float]],
    respaldo: Sequence[tuple[Poligono, float]],
) -> list[tuple[Poligono, float]]:
    """Deduplica detecciones entre mosaicos usando rejilla espacial O(N)."""
    ordenadas = [
        *(sorted(primarias, key=lambda item: item[1], reverse=True)),
        *(sorted(respaldo, key=lambda item: item[1], reverse=True)),
    ]
    if not ordenadas:
        return []
    con_cajas = [(pol, conf, _bbox_poligono(pol)) for pol, conf in ordenadas]
    indice = _IndiceEspacial(_tamano_celda_para_cajas([box for _, _, box in con_cajas]))
    aceptados: list[tuple[Poligono, float, Caja]] = []
    for pol, conf, box in con_cajas:
        duplicado = False
        for idx_ok in indice.candidatos(box):
            pol_ok, _conf_ok, box_ok = aceptados[idx_ok]
            if box[2] <= box_ok[0] or box_ok[2] <= box[0]:
                continue
            if box[3] <= box_ok[1] or box_ok[3] <= box[1]:
                continue
            if _se_superponen_mucho(pol, box, pol_ok, box_ok):
                duplicado = True
                break
        if not duplicado:
            indice.agregar(len(aceptados), box)
            aceptados.append((pol, conf, box))
    return [(pol, conf) for pol, conf, _box in aceptados]


def fusionar_detecciones(
    primarias: Sequence[tuple[Poligono, float]],
    respaldo: Sequence[tuple[Poligono, float]],
) -> list[Poligono]:
    """Deduplica detecciones entre mosaicos y devuelve solo los polígonos."""
    return [pol for pol, _conf in _fusionar_detecciones_con_confianza(primarias, respaldo)]


def _es_geometria_roca_valida(contorno_cv: np.ndarray) -> bool:
    """Descarta artefactos imposibles (tiras muy delgadas o anillos de sombra huecos)."""
    import cv2  # type: ignore[import-not-found]

    area = float(cv2.contourArea(contorno_cv))
    if area <= 0.0:
        return False
    casco = cv2.convexHull(contorno_cv)
    area_casco = float(cv2.contourArea(casco))
    if area_casco > 0.0 and (area / area_casco) < SOLIDEZ_MINIMA_ROCA:
        return False
    _centro, (rw, rh), _ang = cv2.minAreaRect(contorno_cv)
    menor = min(rw, rh)
    mayor = max(rw, rh)
    if menor > 0.0 and (mayor / menor) > ASPECTO_MAXIMO_ROCA:
        return False
    return True


def particionar_poligonos_sin_solape(
    detecciones: Sequence[tuple[Poligono, float]],
    ancho_img: int,
    alto_img: int,
    area_minima_px: float,
    lado_max: int = 1024,
) -> list[Poligono]:
    """Asigna cada píxel a una sola roca (mayor confianza) sin tocar rocas aisladas."""
    if len(detecciones) <= 1:
        return [pol for pol, _ in detecciones]
    try:
        import cv2  # type: ignore[import-not-found]
    except ImportError:
        return [pol for pol, _ in detecciones]

    mayor_lado = max(1, ancho_img, alto_img)
    escala = min(1.0, lado_max / mayor_lado)
    cw = max(16, int(round(ancho_img * escala)))
    ch = max(16, int(round(alto_img * escala)))
    sx_inv = ancho_img / cw
    sy_inv = alto_img / ch

    ordenadas = sorted(detecciones, key=lambda item: item[1], reverse=True)
    etiquetas = np.zeros((ch, cw), dtype=np.int32)
    salida: list[Poligono] = []

    for idx, (pol, _conf) in enumerate(ordenadas, start=1):
        pts_c = np.array(
            [
                [
                    min(cw - 1, max(0, int(round(p.x * cw / ancho_img)))),
                    min(ch - 1, max(0, int(round(p.y * ch / alto_img)))),
                ]
                for p in pol.puntos
            ],
            dtype=np.int32,
        )
        x0 = int(pts_c[:, 0].min())
        y0 = int(pts_c[:, 1].min())
        x1 = int(pts_c[:, 0].max()) + 1
        y1 = int(pts_c[:, 1].max()) + 1
        if x1 <= x0 or y1 <= y0:
            continue

        sub_m = np.zeros((y1 - y0, x1 - x0), dtype=np.uint8)
        cv2.fillPoly(sub_m, [pts_c - np.array([x0, y0], dtype=np.int32)], (1,))
        pix_orig = int(np.count_nonzero(sub_m))
        if pix_orig == 0:
            continue

        vista = etiquetas[y0:y1, x0:x1]
        libre = (sub_m > 0) & (vista == 0)
        pix_libre = int(np.count_nonzero(libre))
        if pix_libre < pix_orig * FRACCION_MINIMA_TRAS_PARTICION:
            continue

        vista[libre] = idx
        if pix_libre == pix_orig:
            # Sin solapamiento con vecinas: conservar exactamente el polígono original.
            salida.append(pol)
            continue

        c_cv, _ = cv2.findContours(
            libre.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        if not c_cv:
            continue
        mayor = max(c_cv, key=cv2.contourArea)
        if len(mayor) < 3 or not _es_geometria_roca_valida(mayor):
            continue
        globales = [
            ((x0 + float(pt[0][0]) + 0.5) * sx_inv, (y0 + float(pt[0][1]) + 0.5) * sy_inv)
            for pt in mayor
        ]
        poligonos = poligonos_desde_contornos(
            [globales], ancho_img, alto_img, area_minima_px=area_minima_px
        )
        if poligonos:
            salida.append(poligonos[0])

    return salida


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
    unet: Any | None = None,
    fg_unet: np.ndarray | None = None,
    bd_unet: np.ndarray | None = None,
    indices: Sequence[int] | None = None,
) -> list[tuple[Poligono, float]]:
    """Convierte máscaras `retina_masks=True` a polígonos limpios (con validación U-Net)."""
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

    usar_unet = unet is not None and fg_unet is not None and bd_unet is not None
    uh, uw = fg_unet.shape[:2] if fg_unet is not None else (0, 0)

    mascaras_np = resultado.masks.data.cpu().numpy()
    objetivos = range(len(mascaras_np)) if indices is None else indices
    salida: list[tuple[Poligono, float]] = []
    pad_px = 6 if usar_unet else 2

    for idx in objetivos:
        m = mascaras_np[idx]
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

        conf = float(confs[idx]) if confs is not None and idx < len(confs) else 0.5
        sx = (tx1 - tx0) / max(1, wm)
        sy = (ty1 - ty0) / max(1, hm)

        if usar_unet and fg_unet is not None and bd_unet is not None:
            gx0 = tx0 + mx0 * sx
            gy0 = ty0 + my0 * sy
            gx1 = tx0 + mx1 * sx
            gy1 = ty0 + my1 * sy
            ux0 = max(0, min(uw - 1, int(math.floor(gx0 * uw / ancho_img))))
            uy0 = max(0, min(uh - 1, int(math.floor(gy0 * uh / alto_img))))
            ux1 = max(ux0 + 1, min(uw, int(math.ceil(gx1 * uw / ancho_img))))
            uy1 = max(uy0 + 1, min(uh, int(math.ceil(gy1 * uh / alto_img))))
            fg_crop = cv2.resize(
                fg_unet[uy0:uy1, ux0:ux1],
                (m_crop.shape[1], m_crop.shape[0]),
                interpolation=cv2.INTER_LINEAR,
            )
            bd_crop = cv2.resize(
                bd_unet[uy0:uy1, ux0:ux1],
                (m_crop.shape[1], m_crop.shape[0]),
                interpolation=cv2.INTER_LINEAR,
            )
            # Validador híbrido: si YOLO tiene baja confianza y U-Net ve fondo, descartar.
            if conf < UMBRAL_CONF_CONFIABLE_YOLO:
                media_fg = float(fg_crop[m_crop > 0].mean())
                if media_fg < UMBRAL_FG_UNET_MIN:
                    continue
            m_crop = unet.refinar_mascara_recorte(
                m_crop, fg_crop, bd_crop, radio_expand=2, radio_recorte=1
            )

        c_cv, _ = cv2.findContours(m_crop, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not c_cv:
            continue
        # Usar solo el contorno mayor evita las líneas puente de `masks.xy`.
        mayor = max(c_cv, key=cv2.contourArea)
        if len(mayor) < 3 or not _es_geometria_roca_valida(mayor):
            continue
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
            salida.append((poligonos[0], conf))

    del mascaras_np
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
            try:
                from app.adaptadores.salida.segmentacion.unet_bordes import RefinadorUNet

                self._unet = RefinadorUNet(ruta_unet)
            except Exception:  # noqa: BLE001 - U-Net es opcional; YOLO debe seguir operativo
                _LOG.exception(
                    "No se pudo cargar U-Net en %s; se continúa solo con YOLO",
                    ruta_unet,
                )
        self._refinar_con_unet = bool(refinar_con_unet and self._unet is not None)
        _LOG.info(
            "SegmentadorYOLO listo (unet_pincel=%s, unet_auto=%s)",
            bool(self._unet),
            self._refinar_con_unet,
        )

    def segmentar(self, imagen: bytes) -> list[Poligono]:
        """Híbrido rápido: YOLO 1024 retina + 1 sola pasada U-Net + partición sin solape."""
        t0 = time.perf_counter()
        foto = Image.open(io.BytesIO(imagen)).convert("RGB")
        w, h = foto.size
        foto_pred, w_pred, h_pred = _redimensionar_si_supera(foto, LADO_MAX_UNICO_YOLO)
        resultado = self._modelo.predict(
            foto_pred,
            imgsz=self._imgsz,
            conf=self._confianza,
            iou=IOU_NMS,
            max_det=self._max_det,
            retina_masks=True,
            verbose=False,
        )[0]
        if resultado.masks is None:
            return []

        n_det = len(resultado.masks)
        t_global = time.perf_counter() - t0

        # Una sola pasada de U-Net (640x640) para toda la imagen: valida falsos positivos
        # de baja confianza y refina bordes sin repetir U-Net por mosaico.
        unet_auto = self._unet if self._refinar_con_unet else None
        fg_unet = bd_unet = None
        t_unet_ini = time.perf_counter()
        if unet_auto is not None:
            fg_unet, bd_unet = unet_auto.mapas_probabilidad_nativas(
                np.array(foto_pred, dtype=np.uint8)
            )
        t_unet = time.perf_counter() - t_unet_ini

        t_malla_ini = time.perf_counter()
        modo = "unico"
        primarias: list[tuple[Poligono, float]] = []
        if n_det <= UMBRAL_DENSIDAD_MALLA:
            respaldo = _extraer_detecciones_retina(
                resultado,
                (0, 0, w, h),
                (w_pred, h_pred),
                w,
                h,
                filtrar_costura=False,
                unet=unet_auto,
                fg_unet=fg_unet,
                bd_unet=bd_unet,
            )
            del resultado
            gc.collect()
            t_malla = 0.0
            t_resp = time.perf_counter() - t_malla_ini
        else:
            cuadricula = generar_cuadricula(w, h, n_det)
            modo = f"malla({len(cuadricula)})"
            imgsz_malla = min(self._imgsz, LADO_MAX_MALLA_YOLO)
            for caja in cuadricula:
                tx0, ty0, tx1, ty1 = caja
                recorte = foto.crop((tx0, ty0, tx1, ty1))
                recorte_pred, tw_pred, th_pred = _redimensionar_si_supera(
                    recorte, LADO_MAX_MALLA_YOLO
                )
                res_tile = self._modelo.predict(
                    recorte_pred,
                    imgsz=imgsz_malla,
                    conf=self._confianza,
                    iou=IOU_NMS,
                    max_det=MAX_DET_MALLA,
                    retina_masks=True,
                    verbose=False,
                )[0]
                primarias.extend(
                    _extraer_detecciones_retina(
                        res_tile,
                        caja,
                        (tw_pred, th_pred),
                        w,
                        h,
                        filtrar_costura=True,
                        unet=unet_auto,
                        fg_unet=fg_unet,
                        bd_unet=bd_unet,
                    )
                )
                del res_tile
                gc.collect()
            t_malla = time.perf_counter() - t_malla_ini

            t_resp_ini = time.perf_counter()
            indices_resp: list[int] | None = None
            boxes_g = getattr(resultado, "boxes", None)
            xyxy_g = (
                boxes_g.xyxy.cpu().numpy()
                if boxes_g is not None and getattr(boxes_g, "xyxy", None) is not None
                else None
            )
            if primarias and xyxy_g is not None:
                sx_g = w / max(1, w_pred)
                sy_g = h / max(1, h_pred)
                cajas_primarias = [_bbox_poligono(p) for p, _ in primarias]
                cajas_resp: list[Caja] = [
                    (
                        float(b[0]) * sx_g,
                        float(b[1]) * sy_g,
                        float(b[2]) * sx_g,
                        float(b[3]) * sy_g,
                    )
                    for b in xyxy_g
                ]
                indices_resp = _filtrar_indices_respaldo(cajas_resp, cajas_primarias)
            respaldo = _extraer_detecciones_retina(
                resultado,
                (0, 0, w, h),
                (w_pred, h_pred),
                w,
                h,
                filtrar_costura=False,
                unet=unet_auto,
                fg_unet=fg_unet,
                bd_unet=bd_unet,
                indices=indices_resp,
            )
            del resultado
            gc.collect()
            t_resp = time.perf_counter() - t_resp_ini

        del fg_unet, bd_unet
        t_fus_ini = time.perf_counter()
        dedup = _fusionar_detecciones_con_confianza(primarias, respaldo)
        salida = particionar_poligonos_sin_solape(
            dedup, w, h, area_minima_px=_area_minima_segmentacion(w, h)
        )
        t_fus = time.perf_counter() - t_fus_ini
        _LOG.info(
            "Segmentación %dx%d [%s, unet=%s (%.2fs)]: global=%d (%.2fs), malla=%d (%.2fs), "
            "respaldo=%d (%.2fs), fusion=%d->%d (%.2fs), total=%.2fs",
            w,
            h,
            modo,
            self._refinar_con_unet,
            t_unet,
            n_det,
            t_global,
            len(primarias),
            t_malla,
            len(respaldo),
            t_resp,
            len(dedup),
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
                imgsz=min(self._imgsz, LADO_MAX_PINCEL_YOLO),
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
