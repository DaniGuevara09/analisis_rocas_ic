"""Módulo opcional U-Net Dual-Head (foreground + bordes) para refinar contornos y pincel."""

from collections.abc import Sequence

import numpy as np
from PIL import Image

from app.adaptadores.salida.segmentacion.contornos import poligonos_desde_contornos
from app.adaptadores.salida.segmentacion.pincel import es_trazo_envolvente, recorte_para_trazo
from app.dominio.modelo import Poligono, Punto

_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)


def _construir_arquitectura(usar_resnet34: bool = False):
    """Construye UNetDualHead (clásica o con backbone ResNet-34) según el checkpoint."""
    import torch  # type: ignore[import-not-found]
    import torch.nn as nn  # type: ignore[import-not-found]
    import torch.nn.functional as F  # type: ignore[import-not-found]

    class DoubleConv(nn.Module):
        def __init__(self, in_ch: int, out_ch: int, residual: bool = False) -> None:
            super().__init__()
            self.residual = residual
            self.conv = nn.Sequential(
                nn.Conv2d(in_ch, out_ch, 3, padding=1, bias=False),
                nn.BatchNorm2d(out_ch),
                nn.ReLU(inplace=True),
                nn.Conv2d(out_ch, out_ch, 3, padding=1, bias=False),
                nn.BatchNorm2d(out_ch),
            )
            self.relu = nn.ReLU(inplace=True)
            self.shortcut = (
                nn.Conv2d(in_ch, out_ch, 1, bias=False)
                if residual and in_ch != out_ch
                else nn.Identity()
            )

        def forward(self, x: torch.Tensor) -> torch.Tensor:
            out = self.conv(x)
            return self.relu(out + self.shortcut(x) if self.residual else out)

    class Down(nn.Module):
        def __init__(self, in_ch: int, out_ch: int) -> None:
            super().__init__()
            self.block = nn.Sequential(nn.MaxPool2d(2), DoubleConv(in_ch, out_ch, residual=True))

        def forward(self, x: torch.Tensor) -> torch.Tensor:
            return self.block(x)

    class Up(nn.Module):
        def __init__(self, in_ch: int, out_ch: int, align_corners: bool = True) -> None:
            super().__init__()
            self._align_corners = align_corners
            self.up = nn.Upsample(scale_factor=2, mode="bilinear", align_corners=align_corners)
            self.conv = DoubleConv(in_ch, out_ch, residual=True)

        def forward(self, x: torch.Tensor, skip: torch.Tensor) -> torch.Tensor:
            x = self.up(x)
            if x.shape[2:] != skip.shape[2:]:
                x = F.interpolate(
                    x,
                    size=skip.shape[2:],
                    mode="bilinear",
                    align_corners=self._align_corners,
                )
            return self.conv(torch.cat([skip, x], dim=1))

    if usar_resnet34:
        from torchvision.models import resnet34  # type: ignore[import-not-found]

        class UNetDualHeadResNet34(nn.Module):
            def __init__(self) -> None:
                super().__init__()
                backbone = resnet34(weights=None)
                self.input_conv = DoubleConv(3, 32, residual=True)
                self.enc0 = nn.Sequential(backbone.conv1, backbone.bn1, backbone.relu)
                self.enc1 = nn.Sequential(backbone.maxpool, backbone.layer1)
                self.enc2 = backbone.layer2
                self.enc3 = backbone.layer3
                self.bottleneck = backbone.layer4
                self.dec3 = Up(512 + 256, 256, align_corners=False)
                self.dec2 = Up(256 + 128, 128, align_corners=False)
                self.dec1 = Up(128 + 64, 64, align_corners=False)
                self.dec0 = Up(64 + 64, 64, align_corners=False)
                self.dec_full = Up(64 + 32, 32, align_corners=False)
                self.head_fg = nn.Conv2d(32, 1, 1)
                self.head_bd = nn.Conv2d(32, 1, 1)

            def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
                s_in = self.input_conv(x)
                s0 = self.enc0(x)
                s1 = self.enc1(s0)
                s2 = self.enc2(s1)
                s3 = self.enc3(s2)
                d = self.dec3(self.bottleneck(s3), s3)
                d = self.dec2(d, s2)
                d = self.dec1(d, s1)
                d = self.dec0(d, s0)
                d = self.dec_full(d, s_in)
                return self.head_fg(d), self.head_bd(d)

        return UNetDualHeadResNet34()

    class UNetDualHead(nn.Module):
        def __init__(
            self, in_channels: int = 3, features: tuple[int, ...] = (64, 128, 256, 512)
        ) -> None:
            super().__init__()
            f = features
            self.enc0 = DoubleConv(in_channels, f[0], residual=True)
            self.enc1 = Down(f[0], f[1])
            self.enc2 = Down(f[1], f[2])
            self.enc3 = Down(f[2], f[3])
            self.bottleneck = Down(f[3], f[3] * 2)
            self.dec3 = Up(f[3] * 2 + f[3], f[3])
            self.dec2 = Up(f[3] + f[2], f[2])
            self.dec1 = Up(f[2] + f[1], f[1])
            self.dec0 = Up(f[1] + f[0], f[0])
            self.head_fg = nn.Conv2d(f[0], 1, 1)
            self.head_bd = nn.Conv2d(f[0], 1, 1)

        def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
            s0 = self.enc0(x)
            s1 = self.enc1(s0)
            s2 = self.enc2(s1)
            s3 = self.enc3(s2)
            d = self.dec3(self.bottleneck(s3), s3)
            d = self.dec2(d, s2)
            d = self.dec1(d, s1)
            d = self.dec0(d, s0)
            return self.head_fg(d), self.head_bd(d)

    return UNetDualHead()


class RefinadorUNet:
    """Carga `unet_best.pth` una vez y proporciona mapas de foreground y bordes."""

    def __init__(self, ruta_pesos: str, img_size: int = 512) -> None:
        import torch  # type: ignore[import-not-found]

        self._device = "cuda" if torch.cuda.is_available() else "cpu"
        checkpoint = torch.load(ruta_pesos, map_location=self._device, weights_only=False)
        self._sz = (
            int(checkpoint.get("img_size", img_size)) if isinstance(checkpoint, dict) else img_size
        )
        estado = (
            checkpoint.get("model_state_dict", checkpoint)
            if isinstance(checkpoint, dict)
            else checkpoint
        )
        usar_resnet34 = isinstance(estado, dict) and "input_conv.conv.0.weight" in estado
        self._model = _construir_arquitectura(usar_resnet34=usar_resnet34).to(self._device).eval()
        self._model.load_state_dict(estado)

    def mapas_probabilidad_nativas(self, img_rgb: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Devuelve (fg_prob, bd_prob) en resolución interna (`img_size`×`img_size`)."""
        import cv2  # type: ignore[import-not-found]
        import torch  # type: ignore[import-not-found]

        x = cv2.resize(img_rgb, (self._sz, self._sz), interpolation=cv2.INTER_AREA).astype(
            np.float32
        ) / 255.0
        x = ((x - _MEAN) / _STD).transpose(2, 0, 1)
        tensor = torch.from_numpy(x).unsqueeze(0).to(self._device)
        with torch.inference_mode():
            fl, bl = self._model(tensor)
        fg = torch.sigmoid(fl.float()).squeeze().cpu().numpy()
        bd = torch.sigmoid(bl.float()).squeeze().cpu().numpy()
        return fg, bd

    def mapas_probabilidad(self, img_rgb: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Devuelve (fg_prob, bd_prob) en resolución original del array RGB."""
        import cv2  # type: ignore[import-not-found]

        h, w = img_rgb.shape[:2]
        fg, bd = self.mapas_probabilidad_nativas(img_rgb)
        if fg.shape != (h, w):
            fg = cv2.resize(fg, (w, h), interpolation=cv2.INTER_LINEAR)
            bd = cv2.resize(bd, (w, h), interpolation=cv2.INTER_LINEAR)
        return fg, bd

    def segmentar_zona(
        self, foto: Image.Image, trazo: Sequence[Punto], radio_px: float
    ) -> Poligono | None:
        """Usa el mapa de bordes aprendido por U-Net + Watershed para segmentar un toque o trazo."""
        import cv2  # type: ignore[import-not-found]

        if not trazo:
            return None
        ancho, alto = foto.size
        x0, y0, x1, y1 = recorte_para_trazo(ancho, alto, trazo, radio_px)
        recorte = foto.crop((x0, y0, x1, y1))
        w_rec, h_rec = recorte.size
        if w_rec < 8 or h_rec < 8:
            return None

        img_rgb = np.array(recorte, dtype=np.uint8)
        fg_prob, bd_prob = self.mapas_probabilidad(img_rgb)

        # La elevación de Watershed combina probabilidad de borde (grietas) y fondo.
        borde_u8 = np.clip((bd_prob * 0.8 + (1.0 - fg_prob) * 0.2) * 255.0, 0, 255).astype(np.uint8)
        borde_3c = cv2.cvtColor(borde_u8, cv2.COLOR_GRAY2BGR)

        pts_locales = np.array(
            [[int(round(p.x - x0)), int(round(p.y - y0))] for p in trazo], dtype=np.int32
        )
        es_toque = len(pts_locales) == 1

        # 2 = fondo definitivo, 0 = por resolver, 1 = semilla de la roca tocada/pintada.
        marcadores = np.zeros((h_rec, w_rec), dtype=np.int32)
        marcadores[fg_prob < 0.25] = 2
        marcadores[bd_prob > 0.50] = 2
        marcadores[0, :] = 2
        marcadores[-1, :] = 2
        marcadores[:, 0] = 2
        marcadores[:, -1] = 2

        if es_toque:
            pt = (int(pts_locales[0][0]), int(pts_locales[0][1]))
            radio_semilla = max(3, int(round(radio_px * 0.5)))
            cv2.circle(marcadores, pt, radio_semilla, 1, -1)
        elif es_trazo_envolvente(trazo, radio_px):
            relleno = np.zeros((h_rec, w_rec), dtype=np.uint8)
            cv2.fillPoly(relleno, [pts_locales], 255)
            k_banda = max(3, int(round(radio_px))) | 1
            elem = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k_banda, k_banda))
            interior = cv2.erode(relleno, elem)
            exterior = cv2.dilate(relleno, elem)
            marcadores[exterior == 0] = 2
            marcadores[interior > 0] = 1
        else:
            radio_semilla = max(2, int(round(radio_px * 0.6)))
            cv2.polylines(marcadores, [pts_locales], False, 1, thickness=radio_semilla * 2)

        if not np.any(marcadores == 1) or not np.any(marcadores == 2):
            return None

        try:
            cv2.watershed(borde_3c, marcadores)
        except Exception:  # noqa: BLE001
            return None

        binaria = np.where(marcadores == 1, 255, 0).astype(np.uint8)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        binaria = cv2.morphologyEx(binaria, cv2.MORPH_CLOSE, kernel)

        contornos_cv, _ = cv2.findContours(binaria, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contornos_cv:
            return None
        mayor = max(contornos_cv, key=cv2.contourArea)
        if len(mayor) < 3:
            return None

        contorno_img = [[(float(pt[0][0]) + x0, float(pt[0][1]) + y0) for pt in mayor]]
        poligonos = poligonos_desde_contornos(contorno_img, ancho, alto)
        return poligonos[0] if poligonos else None

    def refinar_mascara_recorte(
        self,
        mascara: np.ndarray,
        fg_recorte: np.ndarray,
        bd_recorte: np.ndarray | None = None,
        radio_expand: int = 2,
        radio_recorte: int = 1,
    ) -> np.ndarray:
        """Ajusta el contorno de una roca sin dividirla ni invadir vecinas."""
        import cv2  # type: ignore[import-not-found]

        m_bin = mascara.astype(np.uint8) > 0
        k_in_lado = max(3, radio_recorte * 2 + 1)
        k_out_lado = max(3, radio_expand * 2 + 1)
        k_in = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k_in_lado, k_in_lado))
        k_out = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k_out_lado, k_out_lado))

        m_u8 = m_bin.astype(np.uint8)
        interior = cv2.erode(m_u8, k_in) > 0
        if not np.any(interior):
            interior = m_bin
        exterior = cv2.dilate(m_u8, k_out) > 0

        borde_interno = m_bin & (~interior)
        anillo_ext = exterior & (~m_bin)

        if bd_recorte is not None:
            mantiene_borde = borde_interno & (fg_recorte > 0.42) & (bd_recorte < 0.48)
            expande = anillo_ext & (fg_recorte > 0.58) & (bd_recorte < 0.35)
        else:
            mantiene_borde = borde_interno & (fg_recorte > 0.42)
            expande = anillo_ext & (fg_recorte > 0.58)

        ajustada = interior | mantiene_borde | expande
        n_comp, etiquetas, stats, _ = cv2.connectedComponentsWithStats(ajustada.astype(np.uint8))
        if n_comp > 2:
            # Conservar la componente anclada al núcleo original de YOLO.
            etiquetas_centro = etiquetas[interior]
            etiquetas_centro = etiquetas_centro[etiquetas_centro > 0]
            if len(etiquetas_centro) > 0:
                valores, cuentas = np.unique(etiquetas_centro, return_counts=True)
                elegida = int(valores[np.argmax(cuentas)])
            else:
                elegida = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
            ajustada = etiquetas == elegida
        return ajustada.astype(np.uint8)

    def refinar_mascaras(self, img_rgb: np.ndarray, mascaras: list[np.ndarray]) -> list[np.ndarray]:
        """Refina los contornos de las máscaras de YOLO usando los mapas de U-Net."""
        if not mascaras:
            return mascaras
        fg_prob, bd_prob = self.mapas_probabilidad(img_rgb)
        return [self.refinar_mascara_recorte(m, fg_prob, bd_prob) for m in mascaras]


def recuperar_rocas_en_huecos(
    fg_prob: np.ndarray,
    bd_prob: np.ndarray,
    poligonos_existentes: Sequence[Poligono],
    ancho_img: int,
    alto_img: int,
    area_minima_px: float = 75.0,
    max_nuevas: int = 350,
    fg_semilla_umbral: float = 0.56,
    fg_crecimiento_umbral: float = 0.38,
    bd_umbral: float = 0.38,
    fg_medio_min: float = 0.60,
) -> list[Poligono]:
    """Recupera rocas en huecos no cubiertos por YOLO usando Watershed con histéresis."""
    if max_nuevas <= 0 or fg_prob.size == 0:
        return []
    try:
        import cv2  # type: ignore[import-not-found]
    except ImportError:
        return []

    uh, uw = fg_prob.shape[:2]
    cubierto = np.zeros((uh, uw), dtype=np.uint8)
    for pol in poligonos_existentes:
        pts = np.array(
            [
                [
                    min(uw - 1, max(0, int(round(p.x * uw / ancho_img)))),
                    min(uh - 1, max(0, int(round(p.y * uh / alto_img)))),
                ]
                for p in pol.puntos
            ],
            dtype=np.int32,
        )
        if len(pts) >= 3:
            cv2.fillPoly(cubierto, [pts], (1,))

    # Zona de crecimiento hasta el borde real de la roca (evita polígonos encogidos).
    fg_crecimiento = ((fg_prob > fg_crecimiento_umbral) & (cubierto == 0)).astype(np.uint8)
    if int(np.count_nonzero(fg_crecimiento)) < 16:
        return []

    k3 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    # Dilatar 1 px la zona cubierta solo para semillas evita halos finos pegados a rocas YOLO.
    cubierto_semilla = cv2.dilate(cubierto, k3, iterations=1) if np.any(cubierto) else cubierto
    bd_bin = (bd_prob > bd_umbral).astype(np.uint8)
    semillas = (
        (fg_prob > fg_semilla_umbral) & (bd_bin == 0) & (cubierto_semilla == 0)
    ).astype(np.uint8)
    semillas = cv2.morphologyEx(semillas, cv2.MORPH_OPEN, k3)
    if not np.any(semillas):
        return []

    dist = cv2.distanceTransform(semillas, cv2.DIST_L2, 5)
    dist_suave = cv2.GaussianBlur(dist, (3, 3), 0.9)

    # 1. Semillas en picos locales de distancia (evita partir una misma roca pequeña en dos).
    k_pico = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 11))
    es_pico = (
        (semillas > 0)
        & (dist_suave >= 1.8)
        & (dist_suave == cv2.dilate(dist_suave, k_pico))
    )
    n_picos, mapa_picos = cv2.connectedComponents(es_pico.astype(np.uint8))

    marcadores = np.zeros((uh, uw), dtype=np.int32)
    marcadores[fg_crecimiento == 0] = 1  # fondo definitivo + rocas ya cubiertas por YOLO
    next_id = 2
    if n_picos > 1:
        mascara_p = mapa_picos > 0
        marcadores[mascara_p] = mapa_picos[mascara_p] + 1
        next_id = n_picos + 1

    # 2. Garantizar semilla a núcleos pequeños válidos sin pico local >= 1.8 px.
    escala_area_grid = (uw * uh) / max(1.0, float(ancho_img * alto_img))
    min_area_grid = max(12, int(round(area_minima_px * escala_area_grid)))
    min_semilla_grid = max(6, min_area_grid // 2)

    n_cc, cc_map, cc_stats, _ = cv2.connectedComponentsWithStats(semillas)
    if n_cc > 1:
        cubiertos_cc = set(np.unique(cc_map[marcadores >= 2]).tolist())
        for cc_id in range(1, n_cc):
            if cc_id in cubiertos_cc:
                continue
            if int(cc_stats[cc_id, cv2.CC_STAT_AREA]) < min_semilla_grid:
                continue
            x0 = int(cc_stats[cc_id, cv2.CC_STAT_LEFT])
            y0 = int(cc_stats[cc_id, cv2.CC_STAT_TOP])
            cw = int(cc_stats[cc_id, cv2.CC_STAT_WIDTH])
            ch = int(cc_stats[cc_id, cv2.CC_STAT_HEIGHT])
            sub_cc = cc_map[y0 : y0 + ch, x0 : x0 + cw] == cc_id
            sub_dist = dist[y0 : y0 + ch, x0 : x0 + cw]
            ys_l, xs_l = np.nonzero(sub_cc)
            if len(ys_l) == 0:
                continue
            mejor = int(np.argmax(sub_dist[ys_l, xs_l]))
            marcadores[y0 + int(ys_l[mejor]), x0 + int(xs_l[mejor])] = next_id
            next_id += 1

    if next_id <= 2:
        return []

    elevacion_f = np.clip(bd_prob * 0.65 + (1.0 - fg_prob) * 0.35, 0.0, 1.0)
    elevacion_u8 = cv2.GaussianBlur((elevacion_f * 255.0).astype(np.uint8), (3, 3), 0.7)
    elevacion_3c = cv2.cvtColor(elevacion_u8, cv2.COLOR_GRAY2BGR)
    try:
        cv2.watershed(elevacion_3c, marcadores)
    except Exception:  # noqa: BLE001
        return []

    ys, xs = np.nonzero(marcadores >= 2)
    if len(ys) == 0:
        return []
    lbls = marcadores[ys, xs]
    orden = np.argsort(lbls, kind="mergesort")
    ys, xs, lbls = ys[orden], xs[orden], lbls[orden]
    _unicos, inicios, cuentas = np.unique(lbls, return_index=True, return_counts=True)

    sx_inv = ancho_img / float(uw)
    sy_inv = alto_img / float(uh)
    candidatos: list[tuple[float, Poligono]] = []

    for ini, cnt in zip(inicios.tolist(), cuentas.tolist(), strict=True):
        if cnt < min_area_grid:
            continue
        ys_r = ys[ini : ini + cnt]
        xs_r = xs[ini : ini + cnt]
        media_fg = float(fg_prob[ys_r, xs_r].mean())
        if media_fg < fg_medio_min:
            continue

        x0 = max(0, int(xs_r.min()) - 1)
        y0 = max(0, int(ys_r.min()) - 1)
        x1 = min(uw, int(xs_r.max()) + 2)
        y1 = min(uh, int(ys_r.max()) + 2)
        parche = np.zeros((y1 - y0, x1 - x0), dtype=np.uint8)
        parche[ys_r - y0, xs_r - x0] = 1

        # Suavizado 2× en parches pequeños para eliminar escalones de la rejilla 640×640.
        ph, pw = parche.shape[:2]
        factor = 2 if max(ph, pw) < 40 else 1
        if factor > 1:
            suave = cv2.resize(
                parche.astype(np.float32),
                (pw * factor, ph * factor),
                interpolation=cv2.INTER_LINEAR,
            )
            parche_bin = (suave > 0.5).astype(np.uint8)
        else:
            parche_bin = parche

        c_cv, _ = cv2.findContours(parche_bin, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not c_cv:
            continue
        mayor = max(c_cv, key=cv2.contourArea)
        if len(mayor) < 3:
            continue
        area_c = float(cv2.contourArea(mayor))
        if area_c <= 0.0:
            continue
        casco = cv2.convexHull(mayor)
        area_casco = float(cv2.contourArea(casco))
        if area_casco > 0.0 and (area_c / area_casco) < 0.62:
            continue
        _centro, (rw, rh), _ang = cv2.minAreaRect(mayor)
        if min(rw, rh) > 0.0 and (max(rw, rh) / min(rw, rh)) > 3.8:
            continue

        offset = 0.5 / factor
        globales = [
            (
                (x0 + float(pt[0][0]) / factor + offset) * sx_inv,
                (y0 + float(pt[0][1]) / factor + offset) * sy_inv,
            )
            for pt in mayor
        ]
        poligonos = poligonos_desde_contornos(
            [globales], ancho_img, alto_img, area_minima_px=area_minima_px
        )
        if poligonos:
            candidatos.append((media_fg * float(cnt), poligonos[0]))

    candidatos.sort(key=lambda item: item[0], reverse=True)
    return [pol for _score, pol in candidatos[:max_nuevas]]
