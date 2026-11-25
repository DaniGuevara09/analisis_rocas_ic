# ia/ — Investigación y entrenamiento del modelo

Código de la fase experimental del proyecto de Inteligencia Computacional, con las correcciones del profesor implementadas. **No forma parte de la aplicación:** `backend/` nunca lo importa. Contexto completo en `docs/ia.md`.

## Instalación

```powershell
cd ia
python -m venv .venv; .venv\Scripts\Activate.ps1
pip install -r requirements.txt
pytest -q tests/
```

## Pesos

Copiar de Drive:
- `best.pt` → `backend/modelos/best.pt` (el mismo archivo que usa el backend)
- `unet_best.pth` y `mobile_sam.pt` → `ia/pesos/`

Otras rutas se configuran con las variables `ROCAS_YOLO`, `ROCAS_UNET` y `ROCAS_WEIGHTS`. En Colab, `notebooks/pipeline_colab.ipynb` ya las apunta a Drive, así que los modelos entrenados se reutilizan sin reentrenar.

## Flujo

```powershell
# 1. Dataset (segmentación manual de las imágenes de Wilder, etiquetas "rock" y "referencia")
python scripts/preparar_dataset.py --labelme ..\datos\wilder --images ..\datos\wilder
python scripts/crear_excel_escalas.py --images data/dataset/images/test --out data/escalas_imagenes.xlsx
python scripts/marcar_escala.py --xlsx data/escalas_imagenes.xlsx --images data/dataset/images/test --longitud 300 --objeto Regla
python scripts/crear_excel_escalas.py --leer data/escalas_imagenes.xlsx

# 2. Evaluar los modelos YA entrenados con todas las métricas (AUC-ROC, ROC, IoU, Dice, AUC-PR, Boundary IoU, ER D50/D80)
python scripts/evaluar_modelos.py --modelos yolo unet hdbscan mobilesam
python scripts/semantica_vs_instancia.py
python scripts/evaluar_modelos.py --modelos yolo yolo_unet --out results/bordes_unet

# 3. Reentrenar (solo con dataset nuevo; en Colab con GPU). Los pesos nuevos quedan en ia/pesos/*_nuevo.*
python scripts/entrenar.py yolo --epochs 100
python scripts/entrenar.py unet --epochs 80 --resume pesos/unet_best.pth
```

Los resultados quedan en `results/`: tabla de métricas en CSV y Markdown, `roc_pixel.png`, `pr_pixel.png`, `pr_instancia.png` y el detalle por imagen.

## Notas para el documento

- **ROC/AUC a nivel de píxel.** Por fragmento no hay verdaderos negativos, así que allí se usa la curva PR y el AP.
- **Puntaje de píxel por modelo:**
  - U-Net: probabilidad sigmoide;
  - YOLO: máx(conf × máscara);
  - MobileSAM: máx(predicted_iou × máscara);
  - HDBSCAN: probabilidad de pertenencia al clúster.
- **El AUC-ROC de píxel sale alto casi siempre,** porque el fondo domina. Por eso se acompaña de AUC-PR, IoU y Dice.
- **U-Net semántica e instancia tienen la misma ROC** (comparten el mapa de foreground). La diferencia aparece en las métricas por fragmento y en el error de D50/D80, y ese es el argumento de semántica vs. instancia.
- **Curva granulométrica:** por defecto se pondera por volumen (d³), igual que el dominio de la app. Para el análisis de sensibilidad se puede usar `weighting="area"` o `"count"`.
