"""Módulo opcional U-Net Dual-Head (foreground + bordes) para refinar contornos y pincel."""

from collections.abc import Sequence

import numpy as np
from PIL import Image

from app.adaptadores.salida.segmentacion.contornos import poligonos_desde_contornos
from app.adaptadores.salida.segmentacion.pincel import es_trazo_envolvente, recorte_para_trazo
from app.dominio.modelo import Poligono, Punto

_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)


def _construir_arquitectura():
    """Construye UNetDualHead con los mismos nombres de capa que `unet_best.pth`."""
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
        def __init__(self, in_ch: int, out_ch: int) -> None:
            super().__init__()
            self.up = nn.Upsample(scale_factor=2, mode="bilinear", align_corners=True)
            self.conv = DoubleConv(in_ch, out_ch, residual=True)

        def forward(self, x: torch.Tensor, skip: torch.Tensor) -> torch.Tensor:
            x = self.up(x)
            if x.shape[2:] != skip.shape[2:]:
                x = F.interpolate(x, size=skip.shape[2:], mode="bilinear", align_corners=True)
            return self.conv(torch.cat([skip, x], dim=1))

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
        self._sz = img_size
        self._model = _construir_arquitectura().to(self._device).eval()
        checkpoint = torch.load(ruta_pesos, map_location=self._device, weights_only=False)
        estado = (
            checkpoint.get("model_state_dict", checkpoint)
            if isinstance(checkpoint, dict)
            else checkpoint
        )
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
        marcadores[fg_prob < 0.2] = 2
        marcadores[bd_prob > 0.7] = 2
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
            mantiene_borde = borde_interno & (fg_recorte > 0.45) & (bd_recorte < 0.55)
            expande = anillo_ext & (fg_recorte > 0.55) & (bd_recorte < 0.42)
        else:
            mantiene_borde = borde_interno & (fg_recorte > 0.45)
            expande = anillo_ext & (fg_recorte > 0.55)

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
