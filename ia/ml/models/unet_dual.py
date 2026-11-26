"""Modelo 2: U-Net Dual-Head (foreground + bordes) con Watershed.

Cambios respecto al notebook original:
  * La arquitectura y los nombres de capas son IDÉNTICOS, así que los pesos
    `unet_best.pth` ya entrenados cargan sin reentrenar.
  * Corrección del profesor "cómo U-Net puede determinar los bordes":
      - Se añade el mapa de pesos del U-Net original (Ronneberger et al.,
        2015, ec. 2):  w(x) = w_c(x) + w0 * exp(-(d1(x)+d2(x))^2 / (2 sigma^2))
        que penaliza más los píxeles de fondo estrechos que separan dos rocas
        en contacto. Es justo el mecanismo que U-Net propuso para separar
        objetos que se tocan.
      - El objetivo de borde se divide en "contorno" y "contacto entre rocas"
        (los contactos son los que de verdad separan instancias).
  * Dos modos de inferencia para el experimento semántica vs instancia:
      - mode="instance": fg + borde -> Watershed (instancias).
      - mode="semantic": solo fg -> umbral -> componentes conexas.
  * Se arregla el bug de `generate_border_mask` con listas vacías y la línea
    que construía la máscara fg con `mean(0)*0`.
  * Se añade validación por época (antes se guardaba el mejor por loss de
    TRAIN, lo que premia el sobreajuste).
"""
import os

import cv2
import numpy as np
from scipy import ndimage as ndi

from .. import config
from .base import BaseSegmenter, SegmentationOutput

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
except ImportError:  # permite importar el módulo sin torch (p. ej. tests de métricas)
    torch = nn = F = None


# ------------------------------------------------------------------ arquitectura
if nn is not None:
    class DoubleConv(nn.Module):
        def __init__(self, in_ch, out_ch, residual=False):
            super().__init__()
            self.residual = residual
            self.conv = nn.Sequential(
                nn.Conv2d(in_ch, out_ch, 3, padding=1, bias=False),
                nn.BatchNorm2d(out_ch), nn.ReLU(inplace=True),
                nn.Conv2d(out_ch, out_ch, 3, padding=1, bias=False),
                nn.BatchNorm2d(out_ch),
            )
            self.relu = nn.ReLU(inplace=True)
            self.shortcut = (nn.Conv2d(in_ch, out_ch, 1, bias=False)
                             if residual and in_ch != out_ch else nn.Identity())

        def forward(self, x):
            out = self.conv(x)
            return self.relu(out + self.shortcut(x) if self.residual else out)

    class Down(nn.Module):
        def __init__(self, in_ch, out_ch):
            super().__init__()
            self.block = nn.Sequential(nn.MaxPool2d(2), DoubleConv(in_ch, out_ch, residual=True))

        def forward(self, x):
            return self.block(x)

    class Up(nn.Module):
        def __init__(self, in_ch, out_ch, align_corners=True):
            super().__init__()
            self._align_corners = align_corners
            self.up = nn.Upsample(scale_factor=2, mode="bilinear", align_corners=align_corners)
            self.conv = DoubleConv(in_ch, out_ch, residual=True)

        def forward(self, x, skip):
            x = self.up(x)
            if x.shape[2:] != skip.shape[2:]:
                x = F.interpolate(
                    x, size=skip.shape[2:], mode="bilinear", align_corners=self._align_corners
                )
            return self.conv(torch.cat([skip, x], dim=1))

    class UNetDualHeadResNet34(nn.Module):
        """U-Net Dual-Head con encoder ResNet-34 (V3 640px y V3 1024px letterbox)."""

        def __init__(self, pretrained=False):
            super().__init__()
            from torchvision.models import ResNet34_Weights, resnet34

            weights = ResNet34_Weights.IMAGENET1K_V1 if pretrained else None
            backbone = resnet34(weights=weights)
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

        def forward(self, x):
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

    class UNetDualHead(nn.Module):
        def __init__(self, in_channels=3, features=(64, 128, 256, 512)):
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

        def forward(self, x):
            s0 = self.enc0(x); s1 = self.enc1(s0); s2 = self.enc2(s1); s3 = self.enc3(s2)
            d = self.dec3(self.bottleneck(s3), s3)
            d = self.dec2(d, s2); d = self.dec1(d, s1); d = self.dec0(d, s0)
            return self.head_fg(d), self.head_bd(d)


# ------------------------------------------------------------------ objetivos de borde
def border_targets(instance_masks, shape, radius=2):
    """Devuelve (contorno, contacto). 'contacto' = píxeles a <= 2*radius de
    dos o más rocas distintas (fronteras entre rocas que se tocan)."""
    h, w = shape
    contour = np.zeros((h, w), np.uint8)
    touch_count = np.zeros((h, w), np.uint8)
    if not instance_masks:
        return contour, contour.copy()
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * radius + 1, 2 * radius + 1))
    for m in instance_masks:
        m = m.astype(np.uint8)
        contour |= (m - cv2.erode(m, k))
        touch_count += cv2.dilate(m, k, iterations=2)
    contact = (touch_count >= 2).astype(np.uint8)
    return contour, contact


def unet_weight_map(instance_masks, shape, w0=10.0, sigma=5.0, class_balance=True):
    """Mapa de pesos del U-Net original (Ronneberger 2015, ec. 2)."""
    h, w = shape
    fg = np.zeros((h, w), np.uint8)
    for m in instance_masks:
        fg |= m.astype(np.uint8)
    wc = np.ones((h, w), np.float32)
    if class_balance and fg.any():
        frac = fg.mean()
        wc[fg > 0] = 0.5 / max(frac, 1e-6)
        wc[fg == 0] = 0.5 / max(1 - frac, 1e-6)
        wc /= wc.mean()
    if len(instance_masks) < 2:
        return wc
    # d1, d2 = distancia a la 1ª y 2ª roca más cercana. Se calculan en recortes
    # locales: para d1+d2 > 3*sigma*... el término es ~0, así que basta un
    # margen de 3*sigma alrededor de cada roca.
    big = 1e4
    d1 = np.full((h, w), big, np.float32)
    d2 = np.full((h, w), big, np.float32)
    margin = int(np.ceil(3 * sigma))
    for m in instance_masks:
        ys, xs = np.nonzero(m)
        if len(ys) == 0:
            continue
        y0, y1 = max(ys.min() - margin, 0), min(ys.max() + margin + 1, h)
        x0, x1 = max(xs.min() - margin, 0), min(xs.max() + margin + 1, w)
        d = ndi.distance_transform_edt(1 - m[y0:y1, x0:x1].astype(np.uint8)).astype(np.float32)
        a1, a2 = d1[y0:y1, x0:x1], d2[y0:y1, x0:x1]
        closer = d < a1
        a2[:] = np.where(closer, a1, np.minimum(a2, d))
        a1[:] = np.where(closer, d, a1)
    border_w = w0 * np.exp(-((d1 + d2) ** 2) / (2 * sigma ** 2))
    return (wc + border_w * (fg == 0)).astype(np.float32)


# ------------------------------------------------------------------ dataset
class RockDataset(torch.utils.data.Dataset if torch is not None else object):
    def __init__(self, img_dir, coco, img_size=512, augment=True, use_weight_map=True,
                 category_names=("rock",)):
        import albumentations as A
        from albumentations.pytorch import ToTensorV2
        self.img_dir, self.coco, self.sz = img_dir, coco, img_size
        self.ids = list(coco.imgs.keys())
        self.augment, self.use_weight_map = augment, use_weight_map
        self.cat_ids = coco.getCatIds(catNms=list(category_names)) if category_names else []
        self.aug = A.Compose([
            A.HorizontalFlip(p=0.5), A.VerticalFlip(p=0.3), A.RandomRotate90(p=0.5),
            A.Affine(scale=(0.8, 1.2), rotate=(-15, 15), translate_percent=0.05, p=0.6),
            A.RandomBrightnessContrast(p=0.5), A.HueSaturationValue(p=0.3), A.GaussNoise(p=0.2),
        ], additional_targets={"inst": "mask"})
        self.resize = A.Resize(img_size, img_size, interpolation=cv2.INTER_LINEAR,
                               mask_interpolation=cv2.INTER_NEAREST)
        self.norm = A.Compose([A.Normalize((0.485, 0.456, 0.406), (0.229, 0.224, 0.225)),
                               ToTensorV2()])

    def __len__(self):
        return len(self.ids)

    def __getitem__(self, idx):
        info = self.coco.imgs[self.ids[idx]]
        img = cv2.cvtColor(cv2.imread(os.path.join(self.img_dir, info["file_name"])), cv2.COLOR_BGR2RGB)
        anns = self.coco.loadAnns(self.coco.getAnnIds(imgIds=info["id"], catIds=self.cat_ids))
        # mapa de instancias (uint16) para que las aumentaciones geométricas
        # mantengan la identidad de cada roca
        inst = np.zeros(img.shape[:2], np.uint16)
        for k, a in enumerate(anns, start=1):
            inst[self.coco.annToMask(a) > 0] = k
        if self.augment:
            o = self.aug(image=img, inst=inst)
            img, inst = o["image"], o["inst"]
        o = self.resize(image=img, mask=inst)
        img, inst = o["image"], o["mask"]
        masks = [(inst == k).astype(np.uint8) for k in np.unique(inst) if k > 0]
        fg = (inst > 0).astype(np.float32)
        contour, contact = border_targets(masks, inst.shape)
        bd = np.maximum(contour, contact).astype(np.float32)
        wmap = (unet_weight_map(masks, inst.shape) if self.use_weight_map
                else np.ones_like(fg))
        t = lambda a: torch.from_numpy(np.ascontiguousarray(a)).float().unsqueeze(0)  # noqa: E731
        return self.norm(image=img)["image"], t(fg), t(bd), t(wmap)


# ------------------------------------------------------------------ pérdida
if nn is not None:
    class DiceLoss(nn.Module):
        def forward(self, logits, targets, eps=1e-6):
            p = torch.sigmoid(logits)
            i = (p * targets).sum((2, 3))
            u = p.sum((2, 3)) + targets.sum((2, 3))
            return 1 - ((2 * i + eps) / (u + eps)).mean()

    class DualHeadLoss(nn.Module):
        """L = w_fg*(BCE_ponderada_fg + Dice_fg) + w_bd*(BCE_bd(pos_weight) + Dice_bd)"""

        def __init__(self, w_fg=1.0, w_bd=0.5, bd_pos_weight=5.0):
            super().__init__()
            self.w_fg, self.w_bd, self.dice = w_fg, w_bd, DiceLoss()
            self.bd_pos_weight = bd_pos_weight

        def forward(self, pf, pb, gf, gb, wmap=None):
            bce_fg = F.binary_cross_entropy_with_logits(pf, gf, reduction="none")
            bce_fg = (bce_fg * wmap).mean() if wmap is not None else bce_fg.mean()
            pw = torch.tensor(self.bd_pos_weight, device=pb.device)
            bce_bd = F.binary_cross_entropy_with_logits(pb, gb, pos_weight=pw)
            l_fg = bce_fg + self.dice(pf, gf)
            l_bd = bce_bd + self.dice(pb, gb)
            return self.w_fg * l_fg + self.w_bd * l_bd, l_fg.detach(), l_bd.detach()


def train_unet(train_img_dir, train_coco_json, val_img_dir=None, val_coco_json=None,
               out_path=config.UNET_WEIGHTS, epochs=80, lr=3e-4, batch=4, img_size=512,
               use_weight_map=True, resume_from=None, device=None, workers=2):
    """Entrena U-Net Dual-Head. Si se pasa val, guarda el mejor por IoU de validación."""
    from torch.utils.data import DataLoader
    from ..data.coco_utils import load_coco
    device = device or config.device()
    tr = RockDataset(train_img_dir, load_coco(train_coco_json), img_size, True, use_weight_map)
    tl = DataLoader(tr, batch_size=batch, shuffle=True, num_workers=workers, pin_memory=True)
    vl = None
    if val_coco_json:
        va = RockDataset(val_img_dir, load_coco(val_coco_json), img_size, False, use_weight_map)
        vl = DataLoader(va, batch_size=batch, shuffle=False, num_workers=workers)

    model = UNetDualHead().to(device)
    if resume_from:
        model.load_state_dict(torch.load(resume_from, map_location=device)["model_state_dict"])
    crit = DualHeadLoss()
    opt = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    sch = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=epochs, eta_min=1e-6)
    use_amp = device == "cuda"
    scaler = torch.amp.GradScaler("cuda", enabled=use_amp)
    best, history = -1.0, []

    for ep in range(1, epochs + 1):
        model.train(); tot = 0.0
        for x, gf, gb, wm in tl:
            x, gf, gb, wm = (t.to(device) for t in (x, gf, gb, wm))
            opt.zero_grad()
            with torch.autocast(device_type="cuda", enabled=use_amp):
                pf, pb = model(x)
                loss, *_ = crit(pf, pb, gf, gb, wm)
            scaler.scale(loss).backward()
            scaler.unscale_(opt); nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            scaler.step(opt); scaler.update(); tot += loss.item()
        sch.step()
        row = {"epoch": ep, "train_loss": tot / len(tl)}
        if vl is not None:
            model.eval(); inter = union = 0.0
            with torch.no_grad():
                for x, gf, _, _ in vl:
                    p = (torch.sigmoid(model(x.to(device))[0]) > 0.5).float().cpu()
                    inter += (p * gf).sum().item(); union += ((p + gf) > 0).sum().item()
            row["val_IoU"] = inter / max(union, 1)
        metric = row.get("val_IoU", -row["train_loss"])
        if metric > best:
            best = metric
            os.makedirs(os.path.dirname(str(out_path)) or ".", exist_ok=True)
            torch.save(
                {
                    "epoch": ep,
                    "img_size": img_size,
                    "letterbox": False,
                    "model_state_dict": model.state_dict(),
                    **row,
                },
                out_path,
            )
        history.append(row)
        if ep == 1 or ep % 5 == 0:
            print(row)
    return out_path, history


# ------------------------------------------------------------------ letterbox y post-proceso
def letterbox_image(img, target_size, pad_val=0, is_mask=False):
    """Redimensiona preservando relación de aspecto con relleno centrado en `target_size`."""
    h, w = img.shape[:2]
    scale = min(target_size / float(max(1, w)), target_size / float(max(1, h)))
    nw = max(1, min(target_size, int(round(w * scale))))
    nh = max(1, min(target_size, int(round(h * scale))))
    interp = cv2.INTER_NEAREST if is_mask else (cv2.INTER_AREA if scale < 1.0 else cv2.INTER_LINEAR)
    resized = cv2.resize(img, (nw, nh), interpolation=interp)
    shape = (target_size, target_size) if img.ndim == 2 else (target_size, target_size, img.shape[2])
    canvas = np.full(shape, pad_val, dtype=img.dtype)
    pad_x = (target_size - nw) // 2
    pad_y = (target_size - nh) // 2
    canvas[pad_y : pad_y + nh, pad_x : pad_x + nw] = resized
    return canvas, (pad_x, pad_y, nw, nh)


def unpad_letterbox(arr, box):
    """Recorta la región válida `(nh, nw)` sin las bandas de relleno del letterbox."""
    pad_x, pad_y, nw, nh = box
    return arr[pad_y : pad_y + nh, pad_x : pad_x + nw]


def watershed_instances(
    fg_prob,
    bd_prob,
    fg_thresh=0.5,
    bd_thresh=0.45,
    min_distance=10,
    min_area=200,
    scale_ref=640.0,
):
    """Watershed guiado por bordes con escalado automático a 640px o 1024px."""
    from skimage.feature import peak_local_max
    from skimage.segmentation import watershed

    h, w = fg_prob.shape[:2]
    scale = max(1.0, max(h, w) / float(scale_ref))
    fg = (fg_prob > fg_thresh).astype(np.uint8)
    seeds = np.clip(fg - (bd_prob > bd_thresh).astype(np.uint8), 0, 1)
    if seeds.sum() < 0.05 * max(fg.sum(), 1):
        # la cabeza de bordes cubre casi todo el foreground (modelo poco
        # entrenado o umbral muy bajo): se usa el foreground como semilla
        seeds = fg.copy()
    dist = ndi.distance_transform_edt(seeds)
    dist_smooth = ndi.gaussian_filter(dist, sigma=1.2 * scale)
    eff_min_dist = max(4, int(round(min_distance * scale)))
    coords = peak_local_max(dist_smooth, min_distance=eff_min_dist, labels=fg)
    markers = np.zeros(dist.shape, np.int32)
    if len(coords):
        markers[coords[:, 0], coords[:, 1]] = np.arange(1, len(coords) + 1)
    else:
        markers, _ = ndi.label(seeds)
    d_norm = dist_smooth / (dist_smooth.max() + 1e-6)
    elevation = bd_prob.astype(np.float32) * 0.70 - d_norm.astype(np.float32) * 0.30
    eff_min_area = max(1, int(round(min_area * (scale ** 2))))
    labels = watershed(elevation, markers, mask=fg)
    return labels_to_masks(labels, eff_min_area)


def semantic_instances(fg_prob, fg_thresh=0.5, min_area=200):
    """Segmentación SEMÁNTICA -> instancias por componentes conexas (sin bordes)."""
    labels, _ = ndi.label(fg_prob > fg_thresh)
    return labels_to_masks(labels, min_area)


def labels_to_masks(labels, min_area):
    ids, counts = np.unique(labels, return_counts=True)
    return [(labels == i).astype(np.uint8) for i, c in zip(ids, counts) if i != 0 and c >= min_area]


class UNetSegmenter(BaseSegmenter):
    def __init__(self, weights=config.UNET_WEIGHTS, img_size=None, mode="instance",
                 fg_thresh=0.5, bd_thresh=0.45, min_distance=10, min_area=200,
                 letterbox=None, device=None):
        assert mode in ("instance", "semantic")
        self.device = device or config.device()
        self.weights = str(weights)
        ck = torch.load(self.weights, map_location=self.device, weights_only=False)
        es_dict = isinstance(ck, dict)
        state = ck.get("model_state_dict", ck) if es_dict else ck
        use_resnet34 = isinstance(state, dict) and "input_conv.conv.0.weight" in state
        self.model = (
            UNetDualHeadResNet34(pretrained=False) if use_resnet34 else UNetDualHead()
        ).to(self.device).eval()
        self.model.load_state_dict(state)
        self.sz = (
            int(img_size)
            if img_size is not None
            else (int(ck.get("img_size", 512)) if es_dict else 512)
        )
        self.letterbox = (
            bool(letterbox)
            if letterbox is not None
            else (bool(ck.get("letterbox", False)) if es_dict else False)
        )
        self.mode = mode
        self.kw = dict(fg_thresh=fg_thresh, bd_thresh=bd_thresh, min_distance=min_distance,
                       min_area=min_area)
        self.name = "U-Net" if mode == "instance" else "U-Net semántica"
        self.mean = np.array([0.485, 0.456, 0.406], np.float32)
        self.std = np.array([0.229, 0.224, 0.225], np.float32)

    def prob_maps_native(self, img_rgb):
        """Probabilidades fg y borde en resolución nativa (sin bandas si usa letterbox)."""
        box = None
        if self.letterbox:
            canvas, box = letterbox_image(img_rgb, self.sz, pad_val=0, is_mask=False)
            x = canvas.astype(np.float32) / 255.0
        else:
            x = cv2.resize(img_rgb, (self.sz, self.sz), interpolation=cv2.INTER_AREA).astype(
                np.float32
            ) / 255.0
        x = torch.from_numpy(((x - self.mean) / self.std).transpose(2, 0, 1)).unsqueeze(0).to(self.device)
        with torch.no_grad(), torch.autocast(device_type="cuda", enabled=self.device == "cuda"):
            fl, bl = self.model(x)
        fg = torch.sigmoid(fl.float()).squeeze().cpu().numpy()
        bd = torch.sigmoid(bl.float()).squeeze().cpu().numpy()
        if box is not None:
            fg = unpad_letterbox(fg, box)
            bd = unpad_letterbox(bd, box)
        return fg, bd

    def prob_maps(self, img_rgb):
        """Probabilidades fg y borde a la resolución original."""
        h, w = img_rgb.shape[:2]
        fg, bd = self.prob_maps_native(img_rgb)
        if fg.shape != (h, w):
            fg = cv2.resize(fg, (w, h), interpolation=cv2.INTER_LINEAR)
            bd = cv2.resize(bd, (w, h), interpolation=cv2.INTER_LINEAR)
        return fg, bd

    def _predict(self, img_rgb):
        h, w = img_rgb.shape[:2]
        fg_s, bd_s = self.prob_maps_native(img_rgb)
        if self.mode == "instance":
            small = watershed_instances(fg_s, bd_s, **self.kw)
        else:
            scale = max(1.0, max(fg_s.shape[:2]) / 640.0)
            eff_min_area = max(1, int(round(self.kw["min_area"] * (scale ** 2))))
            small = semantic_instances(fg_s, self.kw["fg_thresh"], eff_min_area)
        masks = [cv2.resize(m, (w, h), interpolation=cv2.INTER_NEAREST) for m in small]
        scores = np.array([float(fg_s[m.astype(bool)].mean()) for m in small], dtype=np.float32)
        fg = (
            cv2.resize(fg_s, (w, h), interpolation=cv2.INTER_LINEAR)
            if fg_s.shape != (h, w)
            else fg_s
        )
        bd = (
            cv2.resize(bd_s, (w, h), interpolation=cv2.INTER_LINEAR)
            if bd_s.shape != (h, w)
            else bd_s
        )
        return SegmentationOutput(masks, scores, fg.astype(np.float32), {"fg_prob": fg, "bd_prob": bd})

    @property
    def weights_size_mb(self):
        return os.path.getsize(self.weights) / 1e6
