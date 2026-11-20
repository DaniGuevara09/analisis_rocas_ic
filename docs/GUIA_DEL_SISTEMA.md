# Guía del sistema: cómo funciona y cómo se prueba

Sistema de análisis granulométrico de roca: a partir de una fotografía de una pila de roca fragmentada, estima la distribución de tamaños (D20–D90, índice n, curva e histograma) y exporta el resultado a CSV y PDF.

Esta guía explica el sistema de punta a punta: qué hace cada pieza, qué pasa por dentro en cada paso del operador, cómo se calcula cada número y cómo se prueba todo, con los comandos exactos.

> Los comandos están escritos para **PowerShell** en Windows. Cuando cambian en **CMD**, se indica. En macOS o Linux, `Copy-Item` es `cp` y `.\.venv\Scripts\Activate.ps1` es `source .venv/bin/activate`.

---

## Índice

1. [Visión general](#1-visión-general)
2. [Arquitectura](#2-arquitectura)
3. [Flujo completo del operador, paso a paso](#3-flujo-completo-del-operador-paso-a-paso)
4. [Cómo se calcula la granulometría](#4-cómo-se-calcula-la-granulometría)
5. [Modelo de IA: el espacio para los modelos entrenados](#5-modelo-de-ia-el-espacio-para-los-modelos-entrenados)
6. [Datos y persistencia](#6-datos-y-persistencia)
7. [Configuración (variables de entorno, modo local y nube)](#7-configuración)
8. [Instalación y ejecución](#8-instalación-y-ejecución)
9. [Cómo se prueba (todos los comandos)](#9-cómo-se-prueba)
10. [Trazabilidad: requisito → dónde está → cómo se prueba](#10-trazabilidad-requisitos)
11. [Solución de problemas](#11-solución-de-problemas)
12. [Referencia rápida de comandos](#12-referencia-rápida-de-comandos)

---

## 1. Visión general

| | |
|---|---|
| **Usuario** | Operador de planta (ingeniero de minas) |
| **Entrada** | Foto JPG o PNG de la pila, con un objeto de tamaño conocido (regla, escalímetro, bola de referencia) |
| **Salida** | D20, D50, D60, D80, D90, índice de uniformidad n (Rosin-Rammler), curva granulométrica, histograma, fragmentos coloreados por rango, CSV e informe PDF |
| **Acceso** | Navegador web: `http://localhost` |
| **Despliegue** | `docker compose up --build` (3 contenedores: `db`, `backend` y `frontend`) |

### Las 6 etapas del flujo

```
1. Cargar foto  →  2. Calibrar escala  →  3. Excluir objeto de escala
        →  4. Segmentar (IA)  →  5. Revisar y corregir (human-in-the-loop)
        →  6. Resultados  →  CSV / PDF
```

### Estado de los requisitos

| Requisito | Estado |
|---|---|
| RF-01 a RF-12 (núcleo y complementarios de exportación e historial) | ✅ Implementados |
| RF-14 Configurar rangos y colores | ✅ Implementado |
| RF-13 Usuarios con roles | ❌ No implementado (complementario, fuera de alcance) |
| RF-04 Segmentación automática | ✅ Implementado. **Requiere colocar el modelo entrenado** (ver §5) |

---

## 2. Arquitectura

### 2.1 Contenedores

```mermaid
flowchart LR
    N["Navegador<br/>(operador)"] -- "http://localhost :80" --> F
    subgraph Docker Compose
        F["frontend<br/>nginx + React"] -- "/api/* → :8000" --> B["backend<br/>FastAPI + YOLO"]
        B --> D[("db<br/>PostgreSQL 16")]
        B --> V[("volumen imagenes<br/>fotos")]
        M[["backend/modelos/<br/>best.pt (opcional)"]] -. "montado en /app/modelos" .-> B
    end
```

| Contenedor | Qué hace | Puerto | ¿Expuesto? |
|---|---|---|---|
| `frontend` | nginx sirve la aplicación React y reenvía `/api/*` al backend (timeout de 180 s para la inferencia) | 80 | **Sí** (`PUERTO_WEB`, por defecto 80) |
| `backend` | API REST (FastAPI). Aplica las migraciones al arrancar, carga el modelo si existe y hace todos los cálculos | 8000 | No |
| `db` | PostgreSQL 16 con los análisis, los fragmentos y la configuración | 5432 | No |

### 2.2 Backend: arquitectura hexagonal

```
backend/app/
├── dominio/          Reglas de negocio puras (solo biblioteca estándar)
│   ├── modelo.py         Analisis, Fragmento, Poligono, Calibracion, RegionExcluida...
│   ├── granulometria.py  Fórmulas: diámetro equivalente, curva, Dx, n, histograma
│   ├── configuracion.py  ConfiguracionRangos (RF-14) y su valor por defecto
│   ├── resultado.py      Objetos de valor del resultado y del reporte
│   └── errores.py        Excepciones de negocio
├── aplicacion/       Casos de uso + puertos (interfaces)
│   ├── puertos.py        Segmentador, RepositorioAnalisis, RepositorioConfiguracion,
│   │                     AlmacenImagenes, InspectorImagenes
│   └── casos_de_uso/     Un archivo por caso de uso
└── adaptadores/      Lo único que conoce frameworks
    ├── entrada/api/      Rutas FastAPI, esquemas, errores HTTP, exportación CSV
    └── salida/
        ├── persistencia/     PostgreSQL (SQLAlchemy) para análisis y configuración
        ├── almacenamiento/   Imágenes en disco local o en S3/R2; Pillow para inspeccionar
        └── segmentacion/     SegmentadorYOLO, SegmentadorNoDisponible, conversión de contornos
```

Las dependencias siempre apuntan hacia adentro: `adaptadores → aplicacion → dominio`. La prueba `tests/unit/test_arquitectura.py` falla si el dominio importa FastAPI, SQLAlchemy, ultralytics, etc. **El frontend nunca calcula indicadores**: los pide a la API.

### 2.3 Frontend

```
frontend/src/
├── api/            Cliente HTTP tipado y traducción de errores a mensajes en español
├── pantallas/      MisAnalisis, NuevoAnalisis, CalibrarExcluir, EditorFragmentos,
│                   Resultados, Configuracion
├── editor/         Lienzo Konva y geometría de polígonos (unir, dividir)
├── graficos/       Curva, histograma y vista de fragmentos (SVG)
├── componentes/    Botón, encabezado, leyenda de rangos, modal, indicador de pasos...
└── tema/tokens.css ÚNICO lugar con colores, fuentes y espaciados
```

| Ruta | Pantalla |
|---|---|
| `/` | Mis análisis (historial) |
| `/analisis/nuevo` | Nuevo análisis (cargar foto) |
| `/analisis/:id/calibracion` | Calibrar y excluir |
| `/analisis/:id/editor` | Segmentar y editar |
| `/analisis/:id/resultados` | Resultados, CSV y PDF |
| `/configuracion` | Rangos de tamaño y colores |

---

## 3. Flujo completo del operador, paso a paso

Para cada paso se indica qué hace el operador, qué llamada a la API se produce, qué hace el backend y qué cambia en la base de datos.

### Estados del análisis

```
IMAGEN_CARGADA ──calibrar──▶ CALIBRADO ──segmentar o dibujar──▶ SEGMENTADO
                                ▲                                   │
                                └──── recalibrar (sigue SEGMENTADO) ┘
```

### Paso 1. Mis análisis (historial, RF-12)

- **Pantalla:** `/`. Lista todos los análisis, del más reciente al más antiguo, con su nombre, fecha, estado y número de fragmentos.
- **Acciones del operador:**
  - Buscar por nombre y filtrar por estado.
  - **Abrir:** retoma el análisis donde quedó. Va a calibración si solo tiene la imagen; en cualquier otro caso, al editor.
  - **Resultados:** acceso directo; aparece si el análisis tiene 3 o más fragmentos.
  - **Eliminar:** pide confirmación y borra también la imagen.
- **API:** `GET /api/analisis` y `DELETE /api/analisis/{id}`.

### Paso 2. Nuevo análisis: cargar la foto (RF-01, HU-01)

- **Pantalla:** `/analisis/nuevo`. El operador escribe un nombre y arrastra o elige la foto.
- **Validaciones:**
  - **Navegador:** solo JPG o PNG, de 20 MB como máximo.
  - **Servidor:** detecta el formato **por el contenido** del archivo (Pillow), no por la extensión.
- **API:** `POST /api/analisis` (multipart: `nombre`, `imagen`) → `201`.
- **Backend:**
  1. `InspectorImagenesPillow` obtiene el formato y las dimensiones en px.
  2. `AlmacenImagenes` guarda el archivo (volumen local o bucket R2).
  3. Se crea el `Analisis` en estado `IMAGEN_CARGADA` y se guarda en la tabla `analisis`.
- **Errores:**
  - `415 FORMATO_NO_VALIDO`: no es JPG ni PNG.
  - `413 ARCHIVO_DEMASIADO_GRANDE`: el archivo supera los 20 MB.
  - `422`: el nombre está vacío o tiene más de 150 caracteres.

### Paso 3. Calibrar la escala (RF-02, HU-02)

- **Pantalla:** `/analisis/:id/calibracion`.
  1. **Trazar línea:** dos clics en los extremos del objeto de referencia. Los extremos se pueden arrastrar después.
  2. Escribir la **longitud real en mm** y pulsar **Calibrar**.
- **API:** `PUT /api/analisis/{id}/calibracion` con el cuerpo `{"inicio":{x,y},"fin":{x,y},"longitud_real_mm":300}`.
- **Backend:** se calcula `factor_mm_por_px = longitud_real_mm / distancia_px`, y el estado pasa a `CALIBRADO`. La pantalla muestra el factor.
- **Reglas:**
  - La longitud debe ser mayor que 0.
  - Los dos puntos no pueden coincidir y deben estar dentro de la imagen.
  - **Sin calibración no se puede segmentar ni calcular** (`409 ESCALA_NO_CALIBRADA`).

### Paso 4. Excluir el objeto de escala (RF-03, HU-03)

- **Pantalla:** la misma de calibración.
  1. **Marcar región:** clics alrededor del objeto de escala.
  2. **Cerrar región** y luego **Guardar región**. **Quitar región** la elimina.
- **API:** `PUT /api/analisis/{id}/region-excluida` con `{"poligono":[...]}`; `DELETE` para quitarla.
- **Efecto:** todo fragmento cuyo **centroide** caiga dentro de la región:
  - se borra si ya existía;
  - se omite al segmentar;
  - se rechaza si se intenta dibujar.

  Así el objeto de escala no aparece en el conteo, las métricas ni la curva.
- El botón **Continuar: segmentar y editar** se activa al calibrar.

### Paso 5. Segmentación automática (RF-04, HU-04)

- **Pantalla:** `/analisis/:id/editor`, botón **Segmentar con IA**.
  - Si ya hay fragmentos, pide confirmación, porque la segmentación **reemplaza todos**, incluidos los editados a mano. Se puede deshacer.
  - Si no hay modelo instalado, se muestra el aviso "Modelo de IA no instalado" y el botón queda desactivado (ver §5).
- **API:** `POST /api/analisis/{id}/segmentacion` → `200` con la lista de fragmentos.
- **Backend (`SegmentarAnalisis` → `SegmentadorYOLO`):**
  1. Verifica la calibración **antes** de gastar CPU.
  2. Lee la imagen y ejecuta YOLOv11-seg con `imgsz=640`, `conf=0.25`, `iou=0.5` y `max_det=1000`.
  3. Toma el contorno de cada máscara en píxeles de la imagen original.
  4. `poligonos_desde_contornos`:
     - recorta cada contorno a la imagen;
     - lo simplifica con Douglas-Peucker (tolerancia de 1 px);
     - descarta los contornos con menos de 3 puntos, colineales o de área menor a 20 px².
  5. Registra los fragmentos con origen `MODELO`, omite los de la región excluida y deja el estado en `SEGMENTADO`.
- **Tiempo de referencia:** unos 4,7 s por imagen Full HD en CPU, medido en un portátil del equipo (RNF-02).

### Paso 6. Revisión y corrección (RF-05, HU-05, HU-06)

En la misma pantalla del editor:

| Herramienta / acción | Cómo se usa | Atajo |
|---|---|---|
| **Seleccionar** | Clic en un fragmento; Shift+clic para varios; clic en vacío deselecciona | V |
| **Dibujar** | Clics alrededor de una roca omitida; se termina con un clic en el primer punto, doble clic, Enter o el botón *Terminar fragmento* | D |
| **Dividir** | Dos clics trazando una línea que cruce la roca; se divide el fragmento que contiene el punto medio de la línea | C |
| **Unir** | Seleccionar 2 o más fragmentos que se toquen o solapen | U |
| **Borrar** | Borra los seleccionados | Supr |
| **Deshacer** | Deshace la última acción (hasta 50) | Ctrl+Z |
| **Zoom / mover** | Rueda del ratón para el zoom; arrastrar para moverse; *Ajustar a la pantalla* | — |
| **Mostrar contornos** | Oculta o muestra los polígonos para ver la foto | — |
| **Etiqueta flotante** | Al pasar el ratón sobre un fragmento se muestra su diámetro equivalente | — |

**Qué pasa en cada acción:**

1. El navegador calcula la **geometría** del contorno. Unir usa la librería `polygon-clipping`; dividir intersecta el polígono con los dos semiplanos de la línea.
2. Envía **la lista completa** de fragmentos: `PUT /api/analisis/{id}/fragmentos` (los fragmentos nuevos van sin `id`).
3. El dominio valida **todo antes de guardar**: ids únicos, vértices dentro de la imagen y ningún centroide en la región excluida. Si algo falla, no se cambia nada (`422`).
4. El editor pide `GET /api/analisis/{id}/resultados` y actualiza en vivo el N, D50, D80, n, los colores y la leyenda.

Todo se guarda automáticamente (indicador *Cambios guardados*). Al cerrar el navegador y volver a abrir el análisis se restauran la imagen, la escala, la región y los polígonos (RF-10).

### Paso 7. Resultados (RF-06, RF-07, RF-08, RNF-07)

- **Pantalla:** `/analisis/:id/resultados`. Requiere al menos 3 fragmentos.
- **Contenido:**
  - Indicadores D20, D50, D60, D80, D90 e índice n.
  - **Curva granulométrica:** % pasante contra tamaño, con eje x logarítmico, guías en D50 y D80 y una etiqueta al pasar el ratón.
  - **Histograma:** % retenido en masa por clase de tamaño; al pasar el ratón muestra el intervalo, el % y el número de fragmentos.
  - Foto con los fragmentos **coloreados por rango**, con su leyenda y el conteo de cada rango.
  - **Supuestos del cálculo** (RNF-07): esfericidad, finos no visibles, superficie 2D, ponderación por volumen y "no reemplaza el tamizado".
  - **Ver datos:** tablas del histograma y de cada fragmento.
- **API:** `GET /api/analisis/{id}/resultados`.

### Paso 8. Exportar (RF-09, RF-11)

- **Exportar CSV:** `GET /api/analisis/{id}/resultados.csv` descarga `granulometria_<nombre>.csv`.
  - Formato: UTF-8 con BOM, separador `;` y coma decimal, para que se abra directo en Excel en español.
  - Contenido: datos del análisis, indicadores, supuestos, rangos, puntos de la curva y una fila por fragmento (área en px² y mm², diámetro y rango).
- **Exportar PDF:** abre el diálogo de impresión del navegador → *Guardar como PDF*.
  - La página tiene estilos de impresión: oculta los botones, despliega las tablas y conserva los colores.
  - No hay ruta de API para el PDF.

### Paso 9. Configuración de rangos y colores (RF-14)

- **Pantalla:** `/configuracion`, enlace *Configuración* en el encabezado.
- **Tipo de límites:**
  - **Relativos a la curva:** los límites son % pasante; por ejemplo, 50 equivale a D50. Es la opción por defecto y se adapta a cada pila.
  - **Tamaño fijo:** los límites son milímetros. Sirve para comparar pilas entre sí.
- **Edición:** cada rango tiene color, nombre y límite superior. Se pueden agregar rangos (máximo 8) y quitarlos (mínimo 2). Una vista previa muestra los colores.
- **Botones:** *Guardar*, *Descartar cambios* y *Restablecer valores por defecto*.
- **Valores por defecto:** 5 rangos `< D20`, `D20–D50`, `D50–D80`, `D80–D90` y `≥ D90` (Finos, Pequeños, Medianos, Gruesos y Sobretamaño), con una rampa de azules de claro a oscuro.
- **API:** `GET`, `PUT` y `DELETE /api/configuracion/rangos`.
- **Alcance:** la configuración es **global**. Se aplica a los resultados, el editor, el CSV y el PDF de **todos** los análisis, porque se calcula al consultar.

---

## 4. Cómo se calcula la granulometría

Todo vive en `backend/app/dominio/granulometria.py` y `configuracion.py`: funciones puras con pruebas calculadas a mano.

| # | Magnitud | Fórmula |
|---|---|---|
| 1 | Factor de escala | `f = longitud_real_mm / distancia_px(inicio, fin)` |
| 2 | Área del polígono | Fórmula del zapato (shoelace), en px² |
| 3 | Área real | `area_mm2 = area_px · f²` |
| 4 | Diámetro equivalente (esfericidad) | `d = √(4 · area_mm2 / π)` |
| 5 | Curva granulométrica | Diámetros ordenados de menor a mayor, peso `w_i = d_i³` (volumen de esfera): `P(d_k) = 100 · Σ_{i≤k} w_i / Σ w_i` |
| 6 | Dx (D20…D90) | Tamaño con `P = x %`, por **interpolación lineal** entre los dos puntos de la curva que lo encierran |
| 7 | Índice n (Rosin-Rammler) | `P(x) = 1 − exp(−(x/x_c)^n)`. Se linealiza como `ln(−ln(1−P)) = n·ln(x) − n·ln(x_c)` y se ajusta por mínimos cuadrados con los puntos `0 < P < 1`; **n es la pendiente**. Requiere al menos 3 fragmentos |
| 8 | Histograma | Clases de igual ancho entre el diámetro menor y el mayor; número de clases por Sturges, `⌈log₂N⌉ + 1` (máximo 12); `% retenido` con el mismo peso d³ |
| 9 | Rangos | Relativos: límite = `Dx(corte)`. Absolutos: límite = corte en mm. Cada fragmento va al primer rango `[inferior, superior)` que lo contiene |

**Ejemplo a mano (sirve para verificar HU-08):**

1. **Calibración:** una línea de (0, 0) a (300, 400) mide 500 px. Si representa 250 mm, `f = 0,5 mm/px`.
2. **Área:** un fragmento cuadrado de 100 × 100 px tiene `10 000 px²`. En mm: `10 000 · 0,5² = 2 500 mm²`.
3. **Diámetro equivalente:** `d = √(4 · 2 500 / π) = 56,42 mm`.

Con los 4 cuadrados del script de prueba de humo (lados de 40, 80, 160 y 60 px) la API da `D50 = 63,3 mm`, `D80 = 79,5 mm` y `n = 5,80`. Se puede reproducir en una hoja de cálculo con las fórmulas de arriba.

---

## 5. Modelo de IA: el espacio para los modelos entrenados

La aplicación está **completa y funciona sin el modelo**. El modelo solo habilita el botón *Segmentar con IA*.

| Dónde | `backend/modelos/best.pt` (dentro del contenedor: `/app/modelos/best.pt`) |
|---|---|
| Cómo llega al contenedor | `docker-compose.yml` monta la carpeta `./backend/modelos` en `/app/modelos` |
| Cuándo se carga | Una vez, al arrancar el backend |
| Versionado | **No** se versiona: `.gitignore` excluye `*.pt` |
| Instrucciones | `backend/modelos/README.md` |

### Sin modelo

- `GET /api/salud` → `{"estado":"ok","modelo_disponible":false}`.
- El editor muestra el aviso y desactiva *Segmentar con IA*.
- `POST /segmentacion` → `503 MODELO_NO_DISPONIBLE`.
- **Todo lo demás funciona:** dibujar a mano, unir, dividir, resultados, CSV, PDF y configuración.

### Instalar el modelo cuando esté entrenado

```powershell
# 1. Copiar el archivo con el nombre exacto best.pt
Copy-Item C:\ruta\a\best.pt backend\modelos\best.pt
# 2. Reiniciar solo el backend (el modelo se carga al arrancar)
docker compose restart backend
# 3. Verificar
curl.exe http://localhost/api/salud
#    {"estado":"ok","modelo_disponible":true}
```

- **Tipo de modelo:** de **segmentación de instancias** de Ultralytics (YOLOv8/YOLO11 `-seg`) con la clase `rock`.
- **Cambiar de modelo:** basta con reemplazar `best.pt` y reiniciar. No se toca código (RNF-04: el modelo solo se usa a través del puerto `Segmentador`).
- **Ajustar la inferencia:** las variables `SEGMENTACION_CONFIANZA`, `SEGMENTACION_IMGSZ` y `SEGMENTACION_MAX_DET` del `.env`.
- **Entrenar y evaluar modelos nuevos:** carpeta `ia/` y `docs/ia.md`. Esa carpeta es independiente de la aplicación.

---

## 6. Datos y persistencia

### Tablas (PostgreSQL)

Las crean las migraciones de Alembic al arrancar el backend.

| Tabla | Contenido | Migración |
|---|---|---|
| `analisis` | id, nombre, fecha, estado, ruta y dimensiones de la imagen | 0001 |
| `calibracion` | puntos de la línea y longitud real (1:1 con el análisis) | 0001 |
| `region_excluida` | polígono en JSONB (1:1) | 0001 |
| `fragmento` | polígono en JSONB y origen `MODELO`/`MANUAL` (N:1) | 0001 |
| `configuracion` | pares clave/valor JSONB; la clave `rangos` guarda la configuración de RF-14 | 0002 |

Borrar un análisis borra en cascada su calibración, su región y sus fragmentos, y también su imagen.

### Imágenes

Se guardan fuera de la base de datos: en el volumen Docker `imagenes` (modo local) o en un bucket privado de Cloudflare R2 (modo nube). La base guarda solo la ruta.

### Volúmenes Docker

| Volumen | Contenido |
|---|---|
| `pgdata` | Base de datos |
| `imagenes` | Fotos |

`docker compose down` los conserva. `docker compose down -v` **los borra**.

---

## 7. Configuración

### Variables de entorno

Todas son opcionales en modo local. Van en el archivo `.env` de la raíz.

| Variable | Por defecto | Para qué |
|---|---|---|
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | `rocas` / `cambiar_esta_clave` / `analisis_rocas` | Credenciales del contenedor `db` |
| `DATABASE_URL` | `postgresql+psycopg://rocas:cambiar_esta_clave@db:5432/analisis_rocas` | Base de datos del backend |
| `ALMACEN_IMAGENES` | `local` | `local` (volumen) o `s3` (Cloudflare R2) |
| `S3_ENDPOINT_URL`, `S3_BUCKET`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`, `S3_REGION` | vacías / `auto` | Solo con `ALMACEN_IMAGENES=s3` |
| `SEGMENTACION_CONFIANZA` / `SEGMENTACION_IMGSZ` / `SEGMENTACION_MAX_DET` | `0.25` / `640` / `1000` | Parámetros de YOLO |
| `PUERTO_WEB` | `80` | Puerto del navegador (por ejemplo, `8080` si el 80 está ocupado) |

**Sin `.env` el sistema arranca en modo local (RNF-06).** `docker-compose.yml` declara `env_file` con `required: false` y valores por defecto.

### Modo local y modo nube

| | Local (por defecto) | Nube |
|---|---|---|
| Base de datos | Contenedor `db` | Neon (compartida por el equipo) |
| Imágenes | Volumen `imagenes` | Bucket privado de R2 |
| Cómo se activa | Sin `.env`, o `Copy-Item .env.example .env` | `Copy-Item .env.nube .env` (el archivo `.env.nube` lo entrega Camilo por privado) |
| Uso | Desarrollar y **probar** | Demos y datos compartidos |

> ⛔ **Las pruebas se hacen siempre en modo local.** En modo nube, lo que se borra desaparece para todo el equipo.
>
> ⛔ **Nunca** pongas credenciales reales en `.env.example`, que sí se versiona. Las reales van solo en `.env` o `.env.nube`, que git ignora.

---

## 8. Instalación y ejecución

### Requisitos

| Herramienta | Para qué | Versión |
|---|---|---|
| Docker Desktop (con Compose v2.24 o superior) | Ejecutar el sistema | Abierto y con *Engine running* |
| Git | Clonar | — |
| Python | Pruebas del backend fuera de Docker | 3.12 o superior (3.13 funciona) |
| Node.js | Pruebas del frontend fuera de Docker | **22 LTS** (o 20.19 o superior) |

### Primera ejecución

```powershell
git clone https://github.com/Cristian13Galindo/analisis_rocas.git
cd analisis_rocas

# (opcional) copiar el modelo entrenado si ya existe
Copy-Item C:\ruta\a\best.pt backend\modelos\best.pt

docker compose up --build
```

La primera vez tarda varios minutos, porque descarga PyTorch para CPU; la imagen del backend pesa unos 2 GB. Está listo cuando el log muestra:

```
backend-1  | INFO:     Uvicorn running on http://0.0.0.0:8000
```

| Servicio | URL |
|---|---|
| Aplicación | http://localhost |
| Documentación interactiva de la API (Swagger) | http://localhost/api/docs |
| Salud y estado del modelo | http://localhost/api/salud |

### Operación diaria

```powershell
docker compose up -d                 # arrancar en segundo plano
docker compose ps                    # ver estado de los contenedores
docker compose logs -f backend       # ver el log del backend (Ctrl+C para salir)
docker compose restart backend       # recargar el modelo tras copiar best.pt
docker compose down                  # detener (conserva datos)
docker compose down -v               # detener y BORRAR datos locales
docker compose up -d --build         # reconstruir tras cambiar código
```

---

## 9. Cómo se prueba

Hay cuatro niveles. Ejecútalos en este orden:

| Nivel | Qué prueba | Herramienta | Tiempo |
|---|---|---|---|
| 9.1 | Dominio, casos de uso y API (backend) | pytest + ruff | ~20 s |
| 9.2 | Geometría, gráficos, hooks y componentes (frontend) | vitest + tsc | ~45 s |
| 9.3 | Flujo completo contra el sistema en Docker | `scripts/prueba_humo.ps1` | ~15 s |
| 9.4 | Uso real en el navegador | Lista de verificación manual | ~15 min |

### 9.1 Backend: pruebas automáticas

```powershell
cd backend
python -m venv .venv                      # solo la primera vez (Python 3.12 o superior)
.\.venv\Scripts\Activate.ps1              # CMD: .venv\Scripts\activate.bat
pip install -e ".[dev]"                   # solo la primera vez
pytest                                    # todas las pruebas
ruff check .                              # estilo y errores estáticos
```

> Si `python` apunta a la versión 3.11, crea el entorno con `py -3.13 -m venv .venv`. Sin activar el entorno también funciona: `.\.venv\Scripts\python.exe -m pytest`.

**Resultado esperado:** todo en verde. Sin base de datos de prueba se omiten 10 pruebas: las de PostgreSQL y la del modelo real.

**Ejecutar solo una parte:**

```powershell
pytest tests/unit                                    # dominio + casos de uso (sin red ni BD)
pytest tests/unit/dominio/test_granulometria.py      # solo las fórmulas
pytest tests/integracion/test_api_fragmentos.py      # API de segmentación, edición y resultados
pytest tests/integracion/test_api_configuracion_y_csv.py   # RF-14 y CSV
pytest -k "csv"                                      # por nombre
pytest --cov=app --cov-report=term-missing           # cobertura
```

**Con PostgreSQL real.** Usa una base **desechable**, nunca la de Neon:

```powershell
docker run --rm -d --name pg-pruebas -e POSTGRES_PASSWORD=pruebas -p 55432:5432 postgres:16
$env:TEST_DATABASE_URL = "postgresql+psycopg://postgres:pruebas@localhost:55432/postgres"
pytest                                   # ahora corren también las de repositorio (solo 1 omitida)
docker stop pg-pruebas                   # el contenedor se borra solo (--rm)
Remove-Item Env:TEST_DATABASE_URL
```

En CMD, la variable se define con `set TEST_DATABASE_URL=postgresql+psycopg://postgres:pruebas@localhost:55432/postgres`.

**Con el modelo real.** Opcional; necesita `best.pt` e instala PyTorch (unos 2 GB):

```powershell
pip install -e ".[dev,yolo]"
$env:IMAGEN_PRUEBA_SEGMENTACION = "C:\ruta\a\una\foto_real.jpg"   # opcional: exige ≥ 1 roca
pytest -s tests/integracion/test_segmentador_yolo_real.py          # imprime el tiempo de inferencia
```

| Carpeta | Contenido |
|---|---|
| `tests/unit/dominio` | Fórmulas, entidades, rangos, histograma, edición y configuración |
| `tests/unit/aplicacion` | Casos de uso con adaptadores falsos en memoria (`fakes.py`) |
| `tests/unit/adaptadores` | Conversión de contornos de YOLO a polígonos |
| `tests/unit/test_arquitectura.py` | Que el dominio y la aplicación no importen frameworks |
| `tests/integracion` | API completa (con fakes), PostgreSQL, S3 (moto), Pillow y modelo real |

### 9.2 Frontend: pruebas automáticas

**Con Node 22 instalado** (recomendado):

```powershell
cd frontend
npm install          # solo la primera vez
npm test             # vitest: geometría, escalas de gráficos, edición de rangos, hooks, componentes
npm run build        # tsc (tipos estrictos) + build de producción
```

**Si tu Node es 20.18 o anterior**, `npm test` falla con `ERR_REQUIRE_ESM`. En ese caso, usa Node 22 de forma temporal sin instalarlo:

```powershell
npx -y -p node@22 node node_modules/vitest/vitest.mjs run
npx tsc -b
npx -y -p node@22 node node_modules/vite/bin/vite.js build
```

Otra alternativa es ejecutarlo dentro de Docker:

```powershell
docker run --rm -v "${PWD}:/app" -v frontend_nm:/app/node_modules -w /app node:22-alpine sh -c "npm ci && npm test && npm run build"
```

**Resultado esperado:** todas las pruebas pasan en 10 archivos, y el build termina con `✓ built`.

### 9.3 Prueba de humo: flujo completo contra el sistema real

Con el sistema levantado (`docker compose up -d`) **en modo local**:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\prueba_humo.ps1
# o, si usas otro puerto:
powershell -ExecutionPolicy Bypass -File scripts\prueba_humo.ps1 -Url http://localhost:8080
```

El script recorre el flujo del operador por la API, verifica cada respuesta y **borra al final** el análisis que crea:

| # | Paso | Requisito |
|---|---|---|
| 1 | `GET /salud` e informe del estado del modelo | RF-04 |
| 2 | Crear un análisis con un JPG; rechazar un `.txt` con `415` | RF-01 |
| 3 | Segmentar sin calibrar → `409` | HU-02 |
| 4 | Calibrar (factor 0,5 mm/px) | RF-02 |
| 5 | Excluir una región | RF-03 |
| 6 | Segmentar: `200` con modelo o `503` sin modelo | RF-04 |
| 7 | Guardar 4 fragmentos manuales; rechazar uno en la región excluida con `422` | RF-05 |
| 8 | Resultados: Dx ordenados, n y rangos | RF-06 a RF-08 |
| 9 | Descargar el CSV y comprobar su encabezado y D50 | RF-09 |
| 10 | Reabrir: se conservan la calibración, la región y los fragmentos | RF-10 |
| 11 | Leer la configuración de rangos | RF-14 |
| 12 | Historial y eliminación | RF-12 |

Salida esperada: 15 líneas `[PASA]` y `Todo correcto.` (código de salida 0).

**Probar sin `.env` (RNF-06) y sin tocar tu entorno.** Levanta una copia aislada en el puerto 8080 con volúmenes propios:

```powershell
Set-Content -Path $env:TEMP\env.prueba -Value "PUERTO_WEB=8080"
docker compose -p rocas_prueba --env-file $env:TEMP\env.prueba up -d --build
powershell -ExecutionPolicy Bypass -File scripts\prueba_humo.ps1 -Url http://localhost:8080
docker compose -p rocas_prueba --env-file $env:TEMP\env.prueba down -v   # borra solo esa copia
```

**Medir RNF-02**, el tiempo de segmentación. Requiere el modelo y un análisis calibrado con una foto Full HD real:

```powershell
$id = "<id del análisis>"
1..5 | ForEach-Object { (Measure-Command { curl.exe -s -o NUL -X POST "http://localhost/api/analisis/$id/segmentacion" }).TotalSeconds }
docker stats --no-stream        # memoria del backend
```

**Probar la API a mano.** Swagger está en http://localhost/api/docs: cada ruta tiene *Try it out* y *Execute*. Desde la terminal:

```powershell
curl.exe http://localhost/api/salud
curl.exe -F "nombre=prueba" -F "imagen=@C:\fotos\pila.jpg" http://localhost/api/analisis
Invoke-RestMethod -Method Put -Uri "http://localhost/api/analisis/<id>/calibracion" -ContentType "application/json" `
  -Body '{"inicio":{"x":0,"y":0},"fin":{"x":300,"y":400},"longitud_real_mm":250}'
curl.exe -X POST http://localhost/api/analisis/<id>/segmentacion
curl.exe http://localhost/api/analisis/<id>/resultados
curl.exe -o resultados.csv http://localhost/api/analisis/<id>/resultados.csv
curl.exe http://localhost/api/configuracion/rangos
```

### 9.4 Prueba manual en el navegador (aceptación)

Usa una foto real con un objeto de escala y marca cada casilla:

**Carga e historial**

- [ ] **HU-01:** subir un JPG funciona. Un PDF o TXT muestra "El archivo no es una imagen válida". Una foto de más de 20 MB es rechazada.
- [ ] **RF-12:** el análisis aparece en *Mis análisis*. La búsqueda y el filtro por estado funcionan.

**Calibración y exclusión**

- [ ] **HU-02:** trazar la línea sobre la regla, escribir su longitud y pulsar *Calibrar* muestra el factor mm/px. Antes de calibrar, *Continuar* está desactivado.
- [ ] **HU-03:** marcar, cerrar y guardar la región del objeto de escala. Al segmentar, no hay fragmentos dentro de ella.

**Segmentación y edición**

- [ ] **HU-04:** *Segmentar con IA* muestra los contornos. Sin modelo, aparece el aviso y el botón queda desactivado.
- [ ] **HU-05:** al borrar un fragmento (Supr), N y D50 cambian. Al dibujar uno nuevo, aparece y se recalcula.
- [ ] **HU-06:** unir dos rocas vecinas (Shift+clic y U) produce un solo contorno. Dividir uno (C y dos clics) produce dos.
- [ ] Ctrl+Z deshace la última acción. La rueda hace zoom, arrastrar mueve la imagen y *Ajustar a la pantalla* vuelve a la vista inicial.
- [ ] **HU-10:** al cerrar el navegador y reabrir el análisis está todo (escala, región y polígonos).

**Resultados y exportación**

- [ ] **HU-07:** los fragmentos están coloreados por rango y la leyenda muestra los colores y los conteos.
- [ ] **HU-08:** D20–D90, n, curva e histograma son visibles. Comparar con la hoja de cálculo (§4): la diferencia debe ser de 1 % o menos.
- [ ] **HU-09:** *Exportar CSV* descarga un archivo que se abre bien en Excel, con columnas separadas y comas decimales.
- [ ] **RF-11:** *Exportar PDF* → *Guardar como PDF* produce un informe legible, sin botones y con colores.
- [ ] **RNF-07:** la pantalla y el CSV muestran los supuestos.

**Configuración y compatibilidad**

- [ ] **RF-14:**
  1. En *Configuración*, cambiar a *Tamaño fijo*, ajustar límites, nombres y colores, y *Guardar*.
  2. Los resultados y el CSV usan los rangos nuevos.
  3. *Restablecer valores por defecto* vuelve a los 5 rangos.
- [ ] **RNF-05:** repetir el flujo en Chrome, Firefox y Edge con una pantalla de 1366×768 o más.

---

## 10. Trazabilidad: requisitos

| Req. | Dónde está implementado | Prueba automática | Prueba manual |
|---|---|---|---|
| RF-01 | `crear_analisis.py`, `inspector_pillow.py`, pantalla NuevoAnalisis | `test_api_analisis.py`, `validarArchivo.test.ts` | 9.4 HU-01 |
| RF-02 | `Analisis.calibrar`, `router_calibracion.py`, CalibrarExcluir | `test_calibracion.py`, `test_api_calibracion.py` | HU-02 |
| RF-03 | `Analisis.excluir_region` | `test_modelo.py`, `test_api_calibracion.py` | HU-03 |
| RF-04 | `segmentar_analisis.py`, `segmentador_yolo.py`, `contornos.py` | `test_segmentacion_y_edicion.py`, `test_conversion_contornos.py`, `test_segmentador_yolo_real.py` | HU-04 |
| RF-05 | `Analisis.reemplazar_fragmentos`, `operacionesPoligonos.ts`, EditorFragmentos | `test_edicion_fragmentos.py`, `operacionesPoligonos.test.ts`, `useEdicionFragmentos.test.ts` | HU-05, HU-06 |
| RF-06 | `configuracion.py` (`rangos`), LeyendaRangos | `test_configuracion_rangos.py`, `LeyendaRangos.test.tsx` | HU-07 |
| RF-07 | `granulometria.py` (`calcular`, `percentil_dx`, `indice_uniformidad_n`) | `test_granulometria.py` | HU-08 |
| RF-08 | `curva_granulometrica`, `histograma`, GraficoCurva y GraficoHistograma | `test_rangos_histograma.py`, `escalas.test.ts` | HU-08 |
| RF-09 | `exportacion_csv.py`, `GET /resultados.csv` | `test_api_configuracion_y_csv.py` | HU-09 |
| RF-10 | Repositorio PostgreSQL y `GET /analisis/{id}` | `test_repositorio_postgresql.py` | HU-10 |
| RF-11 | Resultados con `@media print` | — | 9.4 RF-11 |
| RF-12 | MisAnalisis, `GET /analisis` | `test_api_analisis.py` | 9.4 RF-12 |
| RF-14 | `configuracion.py`, `configurar_rangos.py`, `router_configuracion.py`, pantalla Configuracion | `test_configuracion_rangos.py`, `test_configurar_rangos.py`, `test_api_configuracion_y_csv.py`, `edicionRangos.test.ts` | 9.4 RF-14 |
| RNF-01 | `ia/scripts/evaluar_modelos.py` (ER de D50/D80) | — | Con 10 o más fotos delineadas a mano (`docs/ia.md`) |
| RNF-02 | Inferencia en CPU dentro del backend | `test_segmentador_yolo_real.py` (imprime el tiempo) | §9.3, medir RNF-02 |
| RNF-04 | Puerto `Segmentador` | `test_arquitectura.py` | Cambiar `best.pt` y reiniciar |
| RNF-06 | `docker-compose.yml` (`.env` opcional) | — | §9.3, sin `.env` |
| RNF-07 | `SUPUESTOS` en API, CSV y pantalla | `test_api_fragmentos.py`, `test_api_configuracion_y_csv.py` | 9.4 RNF-07 |

---

## 11. Solución de problemas

| Síntoma | Causa | Solución |
|---|---|---|
| `request returned Internal Server Error for API route...` o `error during connect` | El motor de Docker no está corriendo o se colgó | Abrir Docker Desktop y esperar *Engine running*. Si persiste: cerrar Docker, ejecutar `wsl --shutdown` y abrirlo de nuevo. Si sigue, actualizar Docker Desktop |
| `http://localhost` no carga | El puerto 80 está ocupado (IIS, Skype…) | Crear un `.env` con `PUERTO_WEB=8080` y abrir `http://localhost:8080` |
| *Segmentar con IA* desactivado / `503 MODELO_NO_DISPONIBLE` | Falta `backend/modelos/best.pt` | Ver §5 y `docker compose restart backend` |
| El modelo existe pero `modelo_disponible=false` | El archivo está corrupto o no es un modelo `-seg` | `docker compose logs backend` y buscar "No se pudo cargar el modelo" |
| La segmentación tarda mucho o da *timeout* | CPU lenta o imagen muy grande | nginx espera 180 s. Bajar `SEGMENTACION_IMGSZ` o reducir la foto |
| `409 ESCALA_NO_CALIBRADA` | Se intentó segmentar o calcular sin calibrar | Calibrar primero |
| `409 DATOS_INSUFICIENTES` | Hay menos de 3 fragmentos | Segmentar o dibujar más fragmentos |
| `422` al dibujar o editar | El fragmento cae en la región excluida, o tiene menos de 3 puntos | Dibujar fuera de la región |
| *Solo se pueden unir fragmentos que se tocan* | Los seleccionados están separados | Unir solo vecinos, o dibujar uno nuevo que los cubra |
| La lista de análisis aparece vacía | Se cambió entre modo local y nube | Es normal: cada modo tiene su propia base |
| `pip`: *requires a different Python: 3.11* | El `python` por defecto es 3.11 | `py -3.13 -m venv .venv` |
| `pytest`: `No module named boto3` / `httpx` | El entorno virtual no está activo | `.\.venv\Scripts\Activate.ps1` o `.\.venv\Scripts\python.exe -m pytest` |
| `vitest`: `ERR_REQUIRE_ESM` | Node 20.18 o anterior | Instalar Node 22 LTS, o usar `npx -y -p node@22 ...` (§9.2) |
| `vitest`: *Cannot find native binding* (rolldown) | Bug de npm con las dependencias opcionales en Windows | `npm install --no-save @rolldown/binding-win32-x64-msvc@1.2.12` |
| `Copy-Item` no se reconoce | Estás en CMD, no en PowerShell | Usar `copy origen destino` |
| La base de datos no arranca tras cambiar `POSTGRES_PASSWORD` | El volumen `pgdata` se creó con la clave anterior | Volver a la clave anterior, o `docker compose down -v` (borra los datos locales) |

---

## 12. Referencia rápida de comandos

```powershell
# --- Sistema ---
docker compose up --build                     # primera vez / tras cambios
docker compose up -d                          # en segundo plano
docker compose logs -f backend                # log del backend
docker compose restart backend                # recargar el modelo
docker compose down                           # detener (conserva datos)

# --- Modelo ---
Copy-Item C:\ruta\best.pt backend\modelos\best.pt
docker compose restart backend
curl.exe http://localhost/api/salud

# --- Pruebas backend ---
cd backend; .\.venv\Scripts\Activate.ps1
pytest; ruff check .

# --- Pruebas frontend ---
cd frontend
npm test; npm run build                                       # con Node 22
npx -y -p node@22 node node_modules/vitest/vitest.mjs run     # con Node antiguo

# --- Prueba de humo (sistema levantado, modo local) ---
powershell -ExecutionPolicy Bypass -File scripts\prueba_humo.ps1
```
