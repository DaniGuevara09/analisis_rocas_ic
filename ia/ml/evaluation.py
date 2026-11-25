"""Evaluación unificada de cualquier segmentador sobre un COCO de test.

Por imagen calcula:
  * métricas de instancia (TP/FP/FN, IoU medio, Boundary IoU, BF-score)
  * acumula métricas de píxel (IoU, Dice, ROC, AUC-ROC, PR, AUC-PR)
  * granulometría del sistema vs. la del Ground Truth (D50, D80 y su error
    relativo, ecuación 5), usando el factor mm/px del Excel de escalas si
    existe (si no, en píxeles: el error relativo no depende de la escala).
Al final calcula mAP COCO (50, 75, 50-95).
"""
from pathlib import Path

import numpy as np
import pandas as pd

from . import granulometry as G
from .data.coco_utils import gt_masks, list_images, mask_to_rle, name_to_id, read_image_rgb, union_mask
from .metrics import (InstanceAccumulator, PixelMetricAccumulator, boundary_scores_matched,
                      coco_mask_map)


def evaluate(segmenter, coco, img_dir, escalas=None, ref_category="referencia",
             max_images=None, keep_outputs=False, progress=True):
    n2id = name_to_id(coco)
    paths = [p for p in list_images(img_dir) if Path(p).name in n2id][:max_images]
    pix = PixelMetricAccumulator()
    inst = InstanceAccumulator(0.5)
    rows, dt_list, lat, outputs = [], [], [], {}
    ref_cat = coco.getCatIds(catNms=[ref_category])

    it = paths
    if progress:
        try:
            from tqdm.auto import tqdm
            it = tqdm(paths, desc=segmenter.name)
        except ImportError:
            pass

    for p in it:
        name = Path(p).name
        img_id = n2id[name]
        img = read_image_rgb(p)
        gts = gt_masks(coco, img_id, category_names=["rock"])
        ref_masks = gt_masks(coco, img_id, category_names=[ref_category]) if ref_cat else []
        ignore = union_mask(ref_masks, img.shape[:2]) if ref_masks else None

        out = segmenter.predict(img)
        lat.append(out.latency_ms)
        preds = G.exclude_reference(out.masks, ignore) if ignore is not None else out.masks
        keep_idx = [i for i, m in enumerate(out.masks) if any(m is q for q in preds)]
        scores = out.scores[keep_idx] if len(out.scores) else np.ones(len(preds))

        pix.update(out.score_map, union_mask(gts, img.shape[:2]), ignore=ignore)
        r = inst.update(preds, gts, scores)
        b = boundary_scores_matched(preds, gts, r)

        f = (escalas or {}).get(name, {}).get("factor_mm_px", 1.0)
        unidad = "mm" if escalas and name in escalas else "px"
        d_sys = G.equivalent_diameters(preds, f)
        d_ref = G.equivalent_diameters(gts, f)
        ps, pr = G.percentiles(d_sys), G.percentiles(d_ref)
        rows.append({
            "imagen": name, "n_gt": len(gts), "n_pred": len(preds), "tp": r["tp"], "fp": r["fp"],
            "fn": r["fn"], "IoU_medio": r["mean_iou"], **b, "latencia_ms": out.latency_ms,
            "unidad": unidad, "factor_mm_px": f,
            "D50_sis": ps["D50"], "D50_ref": pr["D50"], "D80_sis": ps["D80"], "D80_ref": pr["D80"],
            "ER_D50_%": G.relative_error(ps["D50"], pr["D50"]),
            "ER_D80_%": G.relative_error(ps["D80"], pr["D80"]),
        })
        for m, s in zip(preds, scores):
            dt_list.append({"image_id": img_id, "category_id": coco.getCatIds(catNms=["rock"])[0],
                            "segmentation": mask_to_rle(m), "score": float(s)})
        if keep_outputs:
            outputs[name] = out

    per_img = pd.DataFrame(rows)
    summary = {"modelo": segmenter.name}
    summary.update(coco_mask_map(coco, dt_list, img_ids=[n2id[Path(p).name] for p in paths]))
    summary.update(inst.summary())
    summary.update(pix.summary())
    for k in ("boundary_IoU", "boundary_F1", "ER_D50_%", "ER_D80_%"):
        summary[k] = float(per_img[k].mean()) if len(per_img) else float("nan")
    summary["latencia_ms"] = float(np.mean(lat)) if lat else float("nan")
    summary["tamano_MB"] = segmenter.weights_size_mb
    return {"summary": summary, "per_image": per_img, "pixel_acc": pix, "inst_acc": inst,
            "outputs": outputs}
