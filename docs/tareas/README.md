# Tareas

Cada tarea la redacta el tech lead, la implementa Claude Code y se cierra con un reporte en `docs/reportes/`.

## Hito 4 — Primera iteración (Sprint 2)

| ID | Tarea | Depende de | Estado |
|---|---|---|---|
| T-001 | Estructura del repositorio, Docker Compose y esqueletos de backend y frontend | — | Asignada |
| T-002 | Dominio: entidades y cálculo granulométrico con pruebas unitarias (TDD) | T-001 | Pendiente |
| T-003 | Persistencia (SQLAlchemy + Alembic) y CRUD de análisis con carga de imagen | T-002 | Pendiente |
| T-004 | Calibración y región excluida (casos de uso + API) | T-003 | Pendiente |
| T-005 | Frontend: lista de análisis, carga y calibración (estructura de los wireframes, sin diseño final) | T-004 | Pendiente |
| T-006 | Almacenamiento de imágenes en Cloudflare R2 y BD en Neon por configuración | T-003 | Asignada |

## Sprint 3

| ID | Tarea | Depende de | Estado |
|---|---|---|---|
| T-007 | Segmentación automática con YOLOv11m-seg (adaptador, caso de uso, API, Docker) | T-004 | Implementada, pendiente de revisión |
| T-008 | Editor de fragmentos (borrar, dibujar, unir, dividir), resultados (Dx, n, curva, histograma, rangos) e informe PDF | T-007 | Implementada, pendiente de revisión |

Pendiente: exportación CSV (HU-09, Sprint 4).
