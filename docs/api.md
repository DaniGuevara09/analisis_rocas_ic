# Contrato de la API

Base: `/api`. Formato JSON salvo carga de imágenes (multipart) y exportación (CSV).
FastAPI publica la especificación en `/api/docs` (Swagger UI) y `/api/openapi.json`.

Las rutas marcadas como **[Sprint 3]** o **[Sprint 4]** no se implementan todavía; están aquí para que el diseño sea coherente.

## Formato de error

```json
{ "codigo": "ESCALA_NO_CALIBRADA", "detalle": "Calibre la escala antes de segmentar" }
```

| Excepción | HTTP | codigo |
|---|---|---|
| `FormatoImagenNoValido` | 415 | `FORMATO_NO_VALIDO` |
| `CalibracionNoValida`, `PoligonoNoValido`, `ImagenNoValida`, `FragmentoEnRegionExcluida`, `DatosNoValidos` | 422 | `DATOS_NO_VALIDOS` |
| `AnalisisNoEncontrado`, `FragmentoNoEncontrado` | 404 | `NO_ENCONTRADO` |
| `EscalaNoCalibrada` | 409 | `ESCALA_NO_CALIBRADA` |
| `DatosInsuficientes` | 409 | `DATOS_INSUFICIENTES` |
| `ModeloNoDisponible` (aplicación: falta `best.pt` o no cargó) | 503 | `MODELO_NO_DISPONIBLE` |
| Imagen de más de 20 MB (no es excepción de dominio) | 413 | `ARCHIVO_DEMASIADO_GRANDE` |

## Rutas

### Salud
`GET /api/salud` → `200 {"estado": "ok"}`

### Análisis (CRUD) — HU-01, HU-10
| Método y ruta | Entrada | Salida |
|---|---|---|
| `POST /api/analisis` | multipart: `nombre` (texto), `imagen` (archivo JPG/PNG) | `201` AnalisisResumen |
| `GET /api/analisis` | — | `200` lista de AnalisisResumen, más reciente primero |
| `GET /api/analisis/{id}` | — | `200` AnalisisDetalle |
| `PATCH /api/analisis/{id}` | `{"nombre": "..."}` | `200` AnalisisResumen |
| `DELETE /api/analisis/{id}` | — | `204` (elimina también la imagen del disco) |
| `GET /api/analisis/{id}/imagen` | — | `200` archivo de imagen |

### Calibración y exclusión — HU-02, HU-03
| Método y ruta | Entrada | Salida |
|---|---|---|
| `PUT /api/analisis/{id}/calibracion` | `{"inicio":{"x":..,"y":..},"fin":{"x":..,"y":..},"longitud_real_mm":300}` | `200 {"factor_mm_por_px": 0.42, "estado": "CALIBRADO"}` |
| `PUT /api/analisis/{id}/region-excluida` | `{"poligono":[{"x":..,"y":..}, ...]}` | `200` AnalisisDetalle |
| `DELETE /api/analisis/{id}/region-excluida` | — | `204` |

### Segmentación y edición — HU-04 a HU-06
| Método y ruta | Entrada | Salida |
|---|---|---|
| `POST /api/analisis/{id}/segmentacion` | — | `200` lista de Fragmento (origen `MODELO`; reemplaza **todos** los fragmentos) · `404` · `409 ESCALA_NO_CALIBRADA` · `503 MODELO_NO_DISPONIBLE` |
| `PUT /api/analisis/{id}/fragmentos` | `{"fragmentos": [FragmentoSolicitud, ...]}` | `200` lista de Fragmento vigente · `404` · `409 ESCALA_NO_CALIBRADA` · `422` (polígono inválido, fuera de la imagen, en la región excluida o ids repetidos) |

`PUT /fragmentos` reemplaza la lista completa: el editor envía todos los fragmentos que quedan. Unir y dividir se calculan en el frontend (`polygon-clipping`, solo geometría de contornos); el resultado se envía como fragmentos nuevos sin `id`.

### Resultados y exportación — HU-07 a HU-09
| Método y ruta | Salida |
|---|---|
| `GET /api/analisis/{id}/resultados` | `200` Resultados · `409 DATOS_INSUFICIENTES` (menos de 3 fragmentos) · `409 ESCALA_NO_CALIBRADA` |
| `GET /api/analisis/{id}/resultados.csv` **[Sprint 4]** | CSV con tamaño por fragmento, indicadores y supuestos (RNF-07) |

El informe PDF (RF-11) se genera en el navegador: la pantalla de resultados tiene estilos de impresión y el botón "Exportar PDF" abre *Imprimir → Guardar como PDF*. No hay ruta de API para el PDF.

## Esquemas

```text
Punto            { x: float, y: float }
AnalisisResumen  { id: uuid, nombre: str, fecha_creacion: datetime, estado: str, numero_fragmentos: int }
AnalisisDetalle  AnalisisResumen + {
                   imagen: { url: str, ancho_px: int, alto_px: int, formato: "JPG"|"PNG" },
                   calibracion: { inicio: Punto, fin: Punto, longitud_real_mm: float, factor_mm_por_px: float } | null,
                   region_excluida: { poligono: Punto[] } | null,
                   fragmentos: Fragmento[]
                 }
Fragmento        { id: uuid, poligono: Punto[], origen: "MODELO"|"MANUAL", diametro_equivalente_mm: float | null }
FragmentoSolicitud { id?: uuid (omitir si es nuevo), poligono: Punto[], origen: "MODELO"|"MANUAL" (por defecto "MANUAL") }
Resultados       { d20, d50, d60, d80, d90: float (mm), indice_n: float, numero_fragmentos: int,
                   curva: { diametro_mm, pasante_pct }[],
                   rangos: { indice: 0..4, limite_inferior_mm, limite_superior_mm | null }[],
                   histograma: { limite_inferior_mm, limite_superior_mm, numero_fragmentos, porcentaje_retenido }[],
                   fragmentos: { id, diametro_equivalente_mm, indice_rango }[],
                   supuestos: str[] }
```
