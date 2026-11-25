# Modelo de IA

Fuente: documento del proyecto de Inteligencia Computacional ("Sistema de análisis granulométrico de roca mediante segmentación por instancias") y las correcciones del profesor. Este archivo es su resumen operativo para el código.

## Estado

La fase experimental terminó. Se compararon cuatro métodos en Google Colab (notebook "Granulometría", secciones Modelo 1–4). El test tenía 26 imágenes y 1459 rocas.

| Modelo | Mask mAP@50 | Mask mAP@50-95 | Latencia (ms) | Tamaño (MB) | Uso |
|---|---|---|---|---|---|
| **YOLOv11m-seg** | 0.9087 | 0.8158 | 56.42 | 45.20 | **Producción** (`SegmentadorYOLO`) |
| MobileSAM (zero-shot) | 0.7852 | 0.6796 | 12 145.55 | 40.73 | Solo benchmark |
| U-Net Dual-Head + Watershed | 0.6692 | 0.4797 | 172.56 | 132.59 | Solo benchmark / posible refinador de bordes |
| HDBSCAN | 0.0136 | 0.0038 | 2 108.52 | — | Solo benchmark |

**La aplicación solo usa YOLO**, y solo a través del puerto `Segmentador` (RNF-04). Cambiar de modelo o de versión de pesos no debe requerir cambios fuera de `adaptadores/salida/segmentacion/`.

## Pesos

| Archivo | Dónde está | Quién lo usa |
|---|---|---|
| `best.pt` (YOLO, ~45 MB) | Drive: `ThesisProject/Colab/results/yolo/yolo11m_seg_rocks-7/weights/best.pt` → se copia a `backend/modelos/best.pt` | Backend (`RUTA_MODELO`) y benchmark de `ia/` |
| `unet_best.pth` (~133 MB) | Drive: `ThesisProject/Colab/results/` | Solo `ia/` |
| `mobile_sam.pt` | Drive o descarga automática | Solo `ia/` |

- Los pesos **no se versionan**: `.gitignore` excluye `backend/modelos/*.pt`, y GitHub rechaza archivos de más de 100 MB.
- Si `backend/modelos/best.pt` no existe, la aplicación debe arrancar igual y solo la segmentación responde con error (ver T-007).
- Las pruebas que necesitan el modelo real se saltan con `pytest.mark.skipif`.

### Cómo se actualiza el modelo

1. Se reentrena en Colab con `ia/notebooks/pipeline_colab.ipynb`.
2. Se compara con el modelo actual usando `ia/scripts/evaluar_modelos.py`.
3. Si mejora, se reemplaza `backend/modelos/best.pt` y se anota la versión en el reporte de la tarea: fecha, dataset y mAP@50.

Ningún script reemplaza el `best.pt` del backend automáticamente.

## Parámetros de inferencia (los del documento)

`imgsz=640`, `conf=0.25`, `iou=0.5`, `max_det=1000`, una clase (`rock`). La salida son polígonos en **píxeles de la imagen original**.

## Carpeta `ia/` (investigación, fuera de la arquitectura hexagonal)

```
ia/
  ml/            modelos (YOLO, U-Net, HDBSCAN, MobileSAM, híbrido YOLO+U-Net), métricas, dataset
  scripts/       preparar_dataset, crear_excel_escalas, marcar_escala, entrenar, evaluar_modelos,
                 semantica_vs_instancia, descargar_pesos
  notebooks/     pipeline_colab.ipynb (entrenar/evaluar en Colab con GPU)
  tests/         pytest con datos sintéticos (independiente de backend/tests)
  requirements.txt
```

Reglas:

- **`backend/` nunca importa `ia/`.** La segmentación en la app pasa por `SegmentadorYOLO`.
- `ia/` sí puede leer `backend/modelos/best.pt` para evaluar exactamente el modelo desplegado.
- `ia/` tiene dependencias propias y pesadas (torch, albumentations, pycocotools). No se agregan a `backend/pyproject.toml`.
- Las fórmulas de la app viven en `backend/app/dominio/granulometria.py` y esa es la fuente de verdad. `ia/ml/granulometry` replica la misma ponderación por defecto (d³) para que el error de D50/D80 del benchmark sea comparable con lo que muestra la app.

## Correcciones del profesor → implementación

| Corrección | Dónde |
|---|---|
| Segmentación manual de las imágenes de Wilder | Anotar en LabelMe (`rock` y `referencia`) → `ia/scripts/preparar_dataset.py` |
| Excel con número de imagen y escala del objeto | `ia/scripts/crear_excel_escalas.py` y `marcar_escala.py` (ecuación del factor mm/px) |
| ¿Semántica o instancia? | `ia/scripts/semantica_vs_instancia.py` (rocas fusionadas, error de conteo, ER D50/D80, latencia) |
| U-Net para bordes | `ia/ml/models/unet_dual.py` (mapa de pesos de borde, Ronneberger 2015), `hybrid_yolo_unet.py`, Boundary IoU / BF-score |
| AUC, curva ROC, IoU | `ia/ml/metrics/` y `ia/scripts/evaluar_modelos.py` |
| Metodología CRISP-DM | Documento escrito; las carpetas de `ia/` siguen sus fases |

**Relación con RNF-01:** las imágenes de Wilder delineadas a mano (≥ 10), con su factor del Excel, son el conjunto de validación de RNF-01. `evaluar_modelos.py --modelos yolo` reporta `ER_D50_%` y `ER_D80_%` por imagen, que se comparan contra el umbral de 20 %.

## Decisiones abiertas

- **Ponderación de la curva** (d³ provisional en `dominio/granulometria.py`): pendiente de confirmar con el Ing. Wilder y el asesor de IA. `ia/` permite calcular el benchmark con `volumen`, `area` o `count` para mostrar la sensibilidad de D50/D80 a esa decisión.
- **¿Incluir U-Net como refinador de bordes?** Solo si el benchmark `yolo` vs `yolo_unet` muestra mejora en Boundary IoU y en el error de D50/D80 sin violar RNF-02. Hoy no está en la app.
