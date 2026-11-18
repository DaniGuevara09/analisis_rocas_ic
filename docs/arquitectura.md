# Arquitectura

Fuente: documento "Diseño del sistema y arquitectura" (hito 3). Este archivo es su resumen operativo.

## Decisiones

| Decisión | Elección | Motivo | Requisito |
|---|---|---|---|
| Estilo | Monolito modular con arquitectura hexagonal | Dominio acotado, equipo de 3; aísla el modelo de IA detrás de un puerto | RNF-04 |
| Segmentación | Petición HTTP síncrona | La inferencia en CPU tarda segundos; no se justifica cola de trabajos | RNF-02 |
| API | REST con JSON (documentada con OpenAPI por FastAPI) | Formato nativo del navegador | RNF-05 |
| Backend | Python + FastAPI | ultralytics (YOLO) es Python: inferencia en el mismo proceso | RNF-02, RNF-04 |
| Frontend | React + TypeScript + Konva | Edición de polígonos sobre canvas | RF-05 |
| Base de datos | PostgreSQL; imágenes en disco, la BD guarda la ruta | Modelo relacional; no inflar la BD con archivos | RF-10 |
| Despliegue | Docker Compose | Un solo comando | RNF-06 |
| Nube (ADR-11) | PostgreSQL en Neon + imágenes en bucket privado de Cloudflare R2 (API S3), elegido por variables de entorno; local sigue siendo el valor por defecto | Producción sin servidor propio; desarrollo y pruebas 100 % locales sin cambiar el puerto `AlmacenImagenes` | RNF-06 |

## Estructura del repositorio

```
analisis_rocas/
├── CLAUDE.md
├── docker-compose.yml
├── .env.example
├── docs/
├── backend/
│   ├── Dockerfile
│   ├── pyproject.toml
│   ├── entrypoint.sh             # alembic upgrade head + uvicorn
│   ├── alembic/                  # migraciones
│   ├── modelos/                  # best.pt (no se versiona, ver .gitignore)
│   ├── app/
│   │   ├── main.py               # composición: crea la app y conecta adaptadores con casos de uso
│   │   ├── config.py             # configuración por variables de entorno
│   │   ├── dominio/              # Capa 1 — sin dependencias externas
│   │   │   ├── modelo.py         # Analisis, Calibracion, RegionExcluida, Fragmento, Poligono, Punto...
│   │   │   ├── granulometria.py  # CalculadoraGranulometrica (funciones puras)
│   │   │   └── errores.py        # excepciones de dominio
│   │   ├── aplicacion/           # Capa 2
│   │   │   ├── puertos.py        # Segmentador, RepositorioAnalisis, AlmacenImagenes, InspectorImagenes
│   │   │   └── casos_de_uso/     # un módulo por caso de uso
│   │   └── adaptadores/          # Capa 3
│   │       ├── entrada/api/      # routers FastAPI, esquemas Pydantic, manejo de errores
│   │       └── salida/
│   │           ├── persistencia/ # SQLAlchemy: tablas y RepositorioPostgreSQL
│   │           ├── almacenamiento/ # AlmacenArchivosLocal, AlmacenImagenesS3, InspectorImagenesPillow
│   │           └── segmentacion/ # SegmentadorYOLO
│   └── tests/
│       ├── unit/
│       └── integracion/
└── frontend/
    ├── Dockerfile
    ├── nginx.conf                # sirve el build y redirige /api al backend
    └── src/
        ├── tema/tokens.css       # ÚNICO lugar con colores, tipografía y espaciado
        ├── api/                  # cliente HTTP tipado según docs/api.md
        ├── componentes/          # piezas reutilizables (botón, indicador de pasos, tabla...)
        ├── editor/               # editor de polígonos con Konva
        ├── graficos/             # curva, histograma y vista de fragmentos en SVG
        └── pantallas/            # MisAnalisis, NuevoAnalisis, CalibrarExcluir, EditorFragmentos, Resultados
```

## Puertos (capa de aplicación)

```python
class Segmentador(Protocol):
    def segmentar(self, imagen: bytes) -> list[Poligono]: ...      # polígonos en píxeles

class RepositorioAnalisis(Protocol):
    def guardar(self, analisis: Analisis) -> None: ...
    def obtener(self, id: UUID) -> Analisis | None: ...
    def listar(self) -> list[Analisis]: ...
    def eliminar(self, id: UUID) -> None: ...

class AlmacenImagenes(Protocol):
    def guardar(self, contenido: bytes, extension: str) -> str: ...  # devuelve ruta relativa (local) o clave del objeto (S3)
    def leer(self, ruta: str) -> bytes: ...
    def eliminar(self, ruta: str) -> None: ...

class InspectorImagenes(Protocol):
    def inspeccionar(self, contenido: bytes) -> tuple[str, int, int]: ...  # (formato "JPG"|"PNG", ancho_px, alto_px)
```

`InspectorImagenes` existe porque detectar formato y dimensiones requiere Pillow, que no puede estar en dominio ni aplicación. El formato se detecta por el contenido del archivo, no por la extensión ni el content-type; si no es JPG ni PNG, el adaptador (`InspectorImagenesPillow`) lanza `FormatoImagenNoValido`.

Los casos de uso reciben los puertos por constructor (inyección de dependencias). `main.py` es el único lugar donde se instancian los adaptadores reales. En las pruebas unitarias se usan implementaciones en memoria.

## Despliegue (vista física)

| Contenedor | Contenido | Puerto | Expuesto |
|---|---|---|---|
| frontend | Nginx con el build de React; `/api` → backend | 80 | Sí |
| backend | FastAPI + Uvicorn; carga `best.pt` al iniciar | 8000 | No |
| db | PostgreSQL 16 | 5432 | No |

Volúmenes: `imagenes` (fotografías) y `pgdata` (datos de PostgreSQL).

En desarrollo se permite exponer 8000 y 5432 en `localhost` mediante un `docker-compose.override.yml`.

### Almacén de imágenes por configuración

`ALMACEN_IMAGENES` (`local` por defecto, o `s3`) decide qué adaptador de `AlmacenImagenes` crea `crear_almacen(config)` en `main.py`. `imagen_ruta` guarda indistintamente la ruta relativa local o la clave S3 (`imagenes/<uuid>.<ext>`); el esquema de la BD no cambia.

| Adaptador | Puerto | Almacenamiento |
|---|---|---|
| `AlmacenArchivosLocal` | `AlmacenImagenes` | Carpeta `RUTA_IMAGENES` (volumen `imagenes`) |
| `AlmacenImagenesS3` | `AlmacenImagenes` | Bucket privado S3/R2 con boto3; cliente inyectado (`crear_cliente_s3`) |

### Segmentador por configuración

`crear_segmentador(config)` en `main.py` crea `SegmentadorYOLO` si existe el archivo `RUTA_MODELO`; si no existe o no carga, crea `SegmentadorNoDisponible` y la app **arranca igual**: solo `POST /segmentacion` responde `503 MODELO_NO_DISPONIBLE` (RNF-06: los pesos no se versionan).

| Adaptador | Puerto | Detalle |
|---|---|---|
| `SegmentadorYOLO` | `Segmentador` | ultralytics, carga el modelo una vez; `imgsz=640`, `conf=0.25`, `iou=0.5`, `max_det=1000`, `retina_masks=False`. `import ultralytics` diferido |
| `SegmentadorNoDisponible` | `Segmentador` | Lanza `ModeloNoDisponible` (error de aplicación) |
| `contornos.poligonos_desde_contornos` | — | Función pura: recorta a la imagen, simplifica con Douglas-Peucker (1 px, implementación propia sin OpenCV) y descarta contornos de menos de 3 puntos, colineales o de área < 20 px² |

Dependencias: el extra `[yolo]` de `pyproject.toml` (`ultralytics`). El Dockerfile instala antes `torch` solo CPU y `libgl1`/`libglib2.0-0` para OpenCV. Para desarrollar fuera de Docker no hace falta: `pip install -e ".[dev]"` no trae torch y las pruebas del modelo real se saltan.

Con `s3` son obligatorias `S3_ENDPOINT_URL`, `S3_BUCKET`, `S3_ACCESS_KEY_ID` y `S3_SECRET_ACCESS_KEY` (`S3_REGION=auto` para R2); si falta alguna, la app no arranca y el error no imprime valores.

## Despliegue en la nube

Se usa `.env.nube.example` como plantilla (`DATABASE_URL` de Neon con la cadena **directa**, no la "pooled"). Con ese `.env`, `docker compose up` sigue levantando el contenedor `db`, pero no se usa; la aplicación habla con Neon y R2. El bucket es privado: `GET /api/analisis/{id}/imagen` sigue sirviendo los bytes desde el backend (sin URLs prefirmadas), por lo que `docs/api.md` no cambia.
