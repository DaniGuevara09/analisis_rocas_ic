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

### Segmentación y edición — HU-04 a HU-06 **[Sprint 3]**
| Método y ruta | Salida |
|---|---|
| `POST /api/analisis/{id}/segmentacion` | `200` lista de Fragmento · `409 ESCALA_NO_CALIBRADA` |
| `PUT /api/analisis/{id}/fragmentos` | Reemplaza la lista completa de fragmentos editada por el operador |

### Resultados y exportación — HU-07 a HU-09 **[Sprint 3–4]**
| Método y ruta | Salida |
|---|---|
| `GET /api/analisis/{id}/resultados` | ResultadoGranulometrico + rango de cada fragmento |
| `GET /api/analisis/{id}/resultados.csv` | CSV con tamaño por fragmento, indicadores y supuestos (RNF-07) |

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
```
