# Requisitos

Fuente: documento "Requerimientos funcionales y no funcionales" (corregido).

## Requisitos funcionales

| Código | Requisito | Prioridad |
|---|---|---|
| RF-01 | Cargar fotografías JPG/PNG del frente de voladura | Núcleo |
| RF-02 | Calibrar la escala trazando una línea sobre el objeto de referencia e ingresando su longitud real | Núcleo |
| RF-03 | Marcar la región del objeto de escala para excluirla del conteo | Núcleo |
| RF-04 | Segmentar automáticamente los fragmentos con el modelo YOLO | Núcleo |
| RF-05 | Editar: borrar contornos, dibujar fragmentos omitidos, unir y dividir regiones | Núcleo |
| RF-06 | Colorear fragmentos según rango de tamaño (rangos por defecto) | Núcleo |
| RF-07 | Calcular D20, D50, D60, D80, D90 e índice de uniformidad n | Núcleo |
| RF-08 | Generar curva granulométrica e histograma | Núcleo |
| RF-09 | Exportar resultados en CSV | Núcleo |
| RF-10 | Guardar y reanudar el análisis en curso | Núcleo |
| RF-11 | Exportar informe en PDF | Complementario |
| RF-12 | Historial de análisis | Complementario |
| RF-13 | Autenticación con roles usuario/administrador | Complementario |
| RF-14 | Configurar rangos de tamaño y colores | Complementario |

## Requisitos no funcionales

| Código | Categoría | Descripción |
|---|---|---|
| RNF-01 | Corrección funcional | Sobre ≥ 10 imágenes delineadas manualmente, D50 y D80 de la segmentación automática sin edición con error relativo ≤ 20 % frente al delineado manual |
| RNF-02 | Eficiencia de desempeño | Tiempo promedio desde que se solicita la segmentación de una imagen Full HD hasta ver las máscaras ≤ [X] s en el equipo de despliegue (por definir) |
| RNF-03 | Usabilidad | El operador completa un análisis sin asistencia tras una demostración ≤ 10 min; SUS ≥ 68 |
| RNF-04 | Mantenibilidad (modularidad) | El componente de segmentación se accede solo por una interfaz; cambiar el modelo no requiere cambios en otros componentes |
| RNF-05 | Portabilidad (adaptabilidad) | Funciona en las dos últimas versiones estables de Chrome, Firefox y Edge, escritorio ≥ 1366×768 con ratón |
| RNF-06 | Portabilidad (instalación) | Despliegue completo con `docker compose up`, sin pasos manuales |
| RNF-07 | Adecuación funcional (completitud) | Pantalla de resultados y CSV declaran supuestos: esfericidad, finos no visibles, superficie 2D |

## Historias de usuario

| ID | Historia | Criterio de aceptación | RF | Sprint |
|---|---|---|---|---|
| HU-01 | Cargar la foto de la pila | Acepta JPG y PNG; rechaza otros formatos con mensaje claro | RF-01 | 2 |
| HU-02 | Trazar una línea sobre el objeto de escala e indicar su longitud real | Muestra el factor mm/px; no permite segmentar sin calibración | RF-02 | 2 |
| HU-03 | Marcar la región del objeto de escala | La región no aparece en el conteo, las métricas ni la curva | RF-03 | 2 |
| HU-04 | Segmentación automática | Máscaras visibles dentro del tiempo de RNF-02 | RF-04 | 3 |
| HU-05 | Borrar contornos y dibujar fragmentos omitidos | Cada acción actualiza polígonos y recalcula métricas | RF-05 | 3 |
| HU-06 | Unir y dividir fragmentos | Unir fusiona; dividir separa con una línea; se recalcula | RF-05 | 3 |
| HU-07 | Fragmentos coloreados por rango | Colores por defecto con leyenda visible | RF-06 | 3 |
| HU-08 | Ver D20–D90, n, curva e histograma | Coinciden con cálculo independiente en hoja de cálculo (diferencia ≤ 1 %) | RF-07, RF-08 | 3 |
| HU-09 | Exportar CSV | Tamaño de cada fragmento y métricas | RF-09 | 4 |
| HU-10 | Guardar avance y reanudar | Al reabrir se restauran imagen, escala, región excluida y polígonos | RF-10 | 4 |
| HU-11 | Gestionar usuarios (complementaria) | Alta, baja y rol | RF-13 | 4* |
