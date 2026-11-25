"""Registro de modelos: build_model("yolo" | "unet" | "unet_semantic" |
"hdbscan" | "mobilesam" | "yolo_unet")."""
from .base import BaseSegmenter, SegmentationOutput  # noqa: F401


def build_model(name, **kw):
    name = name.lower()
    if name == "yolo":
        from .yolo_seg import YoloSegmenter
        return YoloSegmenter(**kw)
    if name == "unet":
        from .unet_dual import UNetSegmenter
        return UNetSegmenter(mode="instance", **kw)
    if name == "unet_semantic":
        from .unet_dual import UNetSegmenter
        return UNetSegmenter(mode="semantic", **kw)
    if name == "hdbscan":
        from .hdbscan_seg import HDBSCANSegmenter
        return HDBSCANSegmenter(**kw)
    if name == "mobilesam":
        from .mobilesam_seg import MobileSAMSegmenter
        return MobileSAMSegmenter(**kw)
    if name == "yolo_unet":
        from .hybrid_yolo_unet import YoloUNetBorderSegmenter
        from .unet_dual import UNetSegmenter
        from .yolo_seg import YoloSegmenter
        return YoloUNetBorderSegmenter(YoloSegmenter(**kw.get("yolo", {})),
                                       UNetSegmenter(**kw.get("unet", {})))
    raise ValueError(f"Modelo desconocido: {name}")
