# CLAUDE.md — Sistema de Análisis Granulométrico de Roca

Lee este archivo completo al iniciar cada sesión. Es la fuente de verdad sobre cómo se trabaja en este repositorio.

## 1. El proyecto

Aplicación web para que un operador de planta (ingeniero de minas) estime la distribución granulométrica de una pila de roca fragmentada a partir de una fotografía:
cargar foto → calibrar escala → excluir el objeto de escala → segmentar fragmentos con YOLOv11m-seg → corregir fragmentos → ver D20–D90, índice n, curva e histograma → exportar CSV.

Proyecto académico (UPTC, asignatura Trabajo de Campo). Equipo: Camilo Galindo (PO, backend), Daniela Guevara (SM, IA), Bibian Corredor (frontend, pruebas).

## 2. Documentación que debes consultar

| Archivo | Cuándo leerlo |
|---|---|
| `docs/arquitectura.md` | Siempre antes de crear archivos o módulos |
| `docs/dominio.md` | Al tocar entidades, reglas de negocio o el cálculo granulométrico |
| `docs/api.md` | Al crear o cambiar rutas de la API o el cliente del frontend |
| `docs/requisitos.md` | Para validar que la tarea cumple sus RF, RNF e historias de usuario |
| `docs/tareas/T-XXX.md` | La tarea que te asignaron. Haz solo lo que pide |

Si la documentación y la tarea se contradicen, **detente y pregunta** en el reporte. No elijas por tu cuenta.

## 3. Stack

- **Backend:** Python 3.12, FastAPI, SQLAlchemy 2 (estilo tipado), Alembic, Pydantic v2, pytest, ruff.
- **Frontend:** React 18 + TypeScript + Vite, Konva (react-konva) para el editor de polígonos.
- **Base de datos:** PostgreSQL 16.
- **Modelo de IA:** YOLOv11m-seg (`best.pt`) cargado con `ultralytics` dentro del backend.
- **Despliegue:** Docker Compose (`docker compose up` levanta todo, RNF-06).
- El equipo trabaja en **Windows**. Los comandos que documentes deben funcionar en PowerShell o dentro de Docker.

## 4. Reglas de arquitectura (no negociables)

Arquitectura hexagonal en tres capas dentro de `backend/app/`:

```
adaptadores/  →  aplicacion/  →  dominio/
```

1. `dominio/` **no importa nada** de FastAPI, SQLAlchemy, ultralytics, Pydantic, os ni del sistema de archivos. Solo librería estándar (y numpy si hace falta para cálculo).
2. `aplicacion/` define los **puertos** (clases abstractas `Protocol`/`ABC`) y los **casos de uso**. Depende solo de `dominio/`.
3. `adaptadores/` implementa los puertos (PostgreSQL, archivos, YOLO) y la API REST. Es la única capa que conoce frameworks.
4. Las dependencias siempre apuntan hacia adentro. Si necesitas que el dominio "llame" a algo externo, crea un puerto.
5. Nada de lógica de negocio en los routers de FastAPI ni en los componentes de React.
6. El frontend nunca calcula indicadores granulométricos: los pide a la API.

## 5. Convenciones

- Código, nombres de archivos, clases y funciones **en español sin tildes** (`calcular_diametro_equivalente`, `Analisis`, `RepositorioAnalisis`). Términos técnicos universales pueden quedar en inglés (`id`, `router`, `test`).
- Python: tipado completo, `ruff` sin errores, funciones cortas, docstrings breves en español.
- TypeScript: `strict: true`, componentes funcionales, sin `any`.
- Estilos del frontend: **solo** a través de las variables de `frontend/src/tema/tokens.css`. Prohibido escribir colores, fuentes o espaciados literales en componentes. (Los diseños finales vendrán de Stitch y se aplicarán cambiando solo ese archivo y los estilos de componentes).
- Unidades: milímetros (mm) para tamaños reales, píxeles (px) para la imagen. Nombra variables con su unidad: `longitud_mm`, `area_px`.

## 6. Pruebas

- Todo cálculo del dominio se escribe con **TDD**: primero la prueba, luego el código.
- `backend/tests/unit/` para dominio y casos de uso (con adaptadores falsos en memoria). No deben requerir base de datos ni red.
- `backend/tests/integracion/` para API y persistencia.
- Una tarea no está terminada si alguna prueba falla.

## 7. Flujo de trabajo por tarea

1. Lee la tarea `docs/tareas/T-XXX.md` y los documentos que cita.
2. Implementa **solo el alcance de la tarea**. Si ves algo fuera de alcance que debería hacerse, anótalo en el reporte, no lo hagas.
3. Ejecuta pruebas y linters.
4. Solo puedes usar git en modo lectura (`git status`, `git diff`, `git log`) para revisar tus cambios. Está prohibido cualquier comando que modifique el repositorio (add, commit, checkout, restore, reset, stash, branch, merge, rebase, push, pull). Camilo gestiona git personalmente.
5. Escribe el reporte en `docs/reportes/T-XXX.md` usando `docs/reportes/PLANTILLA.md`. Es obligatorio, incluso si la tarea quedó incompleta. En el reporte, sugiere los mensajes de commit (`feat: ...`, `test: ...`) para que Camilo los use.

## 8. Cuándo detenerte y preguntar

- La tarea es ambigua o contradice la documentación.
- Necesitas una decisión de diseño que no está documentada (nuevo endpoint, nueva tabla, nueva dependencia).
- Una prueba falla y la causa está fuera del alcance de la tarea.
- Tendrías que modificar código de otra capa de una forma que rompa las reglas de la sección 4.

En esos casos, deja el trabajo en un estado consistente, documenta la pregunta en la sección "Preguntas para el tech lead" del reporte y termina.

## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

Rules:
- For codebase questions, first run `graphify query "<question>"` when graphify-out/graph.json exists. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).
- El grafo sirve para navegar el código existente. Para reglas de negocio, contratos de la API y decisiones de diseño, la fuente de verdad sigue siendo docs/ (sección 2 de este archivo); si el grafo y docs/ no coinciden, manda docs/ y repórtalo.
