# Modelos entrenados

Esta carpeta es el **espacio reservado para el modelo de segmentación**. El contenedor `backend` la monta en `/app/modelos`, y la aplicación busca el modelo en:

```
backend/modelos/best.pt        (dentro del contenedor: /app/modelos/best.pt, variable RUTA_MODELO)
backend/modelos/unet_best.pth  (opcional: /app/modelos/unet_best.pth, variable RUTA_MODELO_UNET)
```

## Estado sin modelo

La aplicación funciona completa aunque esta carpeta esté vacía:

- `GET /api/salud` responde `"modelo_disponible": false`.
- El editor muestra el aviso "Modelo de IA no instalado" y desactiva el botón **Segmentar con IA**.
- `POST /api/analisis/{id}/segmentacion` responde `503 MODELO_NO_DISPONIBLE`.
- Todo lo demás funciona: el operador puede dibujar los fragmentos a mano, ver los resultados, exportar el CSV y el PDF.

## Instalar un modelo cuando esté listo

1. Entrena o descarga el modelo YOLOv11-seg. Ver `docs/ia.md` y `ia/notebooks/pipeline_colab.ipynb`.
2. Copia el archivo de pesos aquí **con el nombre exacto `best.pt`**:

   ```powershell
   Copy-Item C:\ruta\a\tu\best.pt backend\modelos\best.pt
   ```

3. Reinicia solo el backend, porque el modelo se carga una vez al arrancar:

   ```powershell
   docker compose restart backend
   ```

4. Verifica que lo detectó:

   ```powershell
   curl.exe http://localhost/api/salud
   # {"estado":"ok","modelo_disponible":true}
   ```

## Requisitos del modelo

- Un modelo de **segmentación de instancias** de Ultralytics (YOLOv8/YOLO11 `-seg`) con la clase `rock`. Un modelo de detección sin máscaras no sirve.
- Parámetros de inferencia: `imgsz=640`, `conf=0.25`, `iou=0.5`, `max_det=1000`. Se cambian con las variables `SEGMENTACION_CONFIANZA`, `SEGMENTACION_IMGSZ` y `SEGMENTACION_MAX_DET` del `.env`.
- Para reemplazar el modelo por otro, basta con sustituir `best.pt` y reiniciar. No hay que cambiar código (RNF-04).

## Reglas

- Los archivos `*.pt` **no se versionan**: `.gitignore` los excluye, y GitHub rechaza archivos de más de 100 MB.
- Anota en el reporte de la tarea qué versión del modelo se instaló: fecha, dataset y mAP@50.
