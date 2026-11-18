# Dominio

## Entidades y objetos de valor

| Clase | Tipo | Atributos | Reglas |
|---|---|---|---|
| `Analisis` | Entidad raíz (agregado) | id (UUID), nombre, fecha_creacion, estado, imagen, calibracion?, region_excluida?, fragmentos | Toda modificación de sus partes pasa por sus métodos |
| `Imagen` | Objeto de valor | ruta, ancho_px, alto_px, formato (JPG/PNG) | Solo JPG o PNG; ancho y alto > 0, si no `ImagenNoValida` |
| `Calibracion` | Objeto de valor | inicio (Punto), fin (Punto), longitud_real_mm | `longitud_real_mm > 0`; los puntos no pueden coincidir; `factor_mm_por_px()` |
| `RegionExcluida` | Objeto de valor | poligono | Polígono válido (≥ 3 puntos) |
| `Fragmento` | Entidad | id, poligono, origen (MODELO/MANUAL) | `area_px()`, `diametro_equivalente_mm(factor)` |
| `Poligono` | Objeto de valor | puntos (≥ 3) | `area()` (fórmula del zapato), `contiene(punto)`, `centroide()` |
| `Punto` | Objeto de valor | x, y (float, px) | — |
| `ResultadoGranulometrico` | Objeto de valor | d20, d50, d60, d80, d90, indice_n, numero_fragmentos, curva | Solo lectura |
| `RangoTamano` | Objeto de valor | limite_inferior_mm, limite_superior_mm, color | Rangos sin solapamiento |

### Reglas del agregado `Analisis`

- **Nombre:** `Analisis.crear(nombre, imagen)` y `Analisis.renombrar(nombre)` recortan los espacios; un nombre vacío o de más de 150 caracteres lanza `DatosNoValidos`.
- **Puntos dentro de la imagen:** los dos puntos de `calibrar` y todos los vértices de `excluir_region` deben cumplir `0 ≤ x ≤ ancho_px` y `0 ≤ y ≤ alto_px` (los bordes son válidos; NaN no lo es). Si no, `CalibracionNoValida` (calibración) o `PoligonoNoValido` (región). Si falla, el agregado no cambia.

### Estados de `Analisis`

`IMAGEN_CARGADA` → `CALIBRADO` → `SEGMENTADO`

- Recalibrar un análisis segmentado se permite; el estado se mantiene en `SEGMENTADO` (los diámetros se recalculan con el nuevo factor).
- `segmentar` / `registrar_fragmentos` exige estado `CALIBRADO` o `SEGMENTADO`; si no, lanza `EscalaNoCalibrada`.

## Fórmulas (CalculadoraGranulometrica)

Todas son funciones puras y deben tener pruebas unitarias con valores calculados a mano.

1. **Factor de escala**
   `factor_mm_por_px = longitud_real_mm / distancia_px(inicio, fin)`

2. **Área del polígono (px²)** — fórmula del zapato (shoelace), valor absoluto.

3. **Área real**
   `area_mm2 = area_px * factor_mm_por_px²`

4. **Diámetro equivalente** (supuesto de esfericidad, RNF-07)
   `d_eq = sqrt(4 * area_mm2 / π)`

5. **Curva granulométrica P(x)** — porcentaje pasante acumulado.
   Peso de cada fragmento proporcional a su volumen de esfera equivalente: `w_i = d_i³`.
   Ordenar diámetros de menor a mayor; `P(d_k) = 100 · Σ_{i≤k} w_i / Σ w_i`.
   > Decisión provisional, pendiente de confirmar con el Ing. Wilder y el asesor de IA. Debe quedar aislada en una sola función (`ponderacion`) para poder cambiarla a ponderación por área o por número.

6. **Dx** (D20, D50, D60, D80, D90): tamaño para el cual P = x %, por **interpolación lineal** entre los dos puntos de la curva que lo encierran. Si x es menor que el primer punto de la curva, devolver el diámetro menor; si es mayor que el último, el mayor.

7. **Índice de uniformidad n (Rosin-Rammler)**
   `P(x) = 1 − exp(−(x / x_c)^n)`
   Linealización: `ln(−ln(1 − P)) = n·ln(x) − n·ln(x_c)`.
   Ajustar por mínimos cuadrados usando solo los puntos con `0 < P < 1` (P en fracción, no en %). `n` es la pendiente.
   Si hay menos de 2 puntos válidos, lanzar `DatosInsuficientes`.

   Consecuencia: `calcular` requiere **al menos 3 fragmentos**. Con menos de 2 puntos con 0 < P < 100 en la curva no hay ajuste de Rosin-Rammler y se lanza `DatosInsuficientes`.

8. **Fragmentos y región excluida** (el centroide del fragmento decide si está dentro):
   - `excluir_region(poligono)` fija la región y **elimina los fragmentos existentes** (de cualquier origen) cuyo centroide quede dentro.
   - `registrar_fragmentos(poligonos, origen)` **reemplaza todos** los fragmentos existentes por los nuevos; los que caigan en la región excluida se omiten.
   - `agregar_fragmento(poligono)` lanza `FragmentoEnRegionExcluida` si el centroide cae en la región excluida.

## Errores de dominio (`dominio/errores.py`)

| Excepción | Cuándo |
|---|---|
| `FormatoImagenNoValido` | Formato distinto de JPG/PNG |
| `ImagenNoValida` | Ancho o alto de la imagen ≤ 0 |
| `FragmentoEnRegionExcluida` | Se agrega a mano un fragmento cuyo centroide cae en la región excluida |
| `CalibracionNoValida` | Longitud ≤ 0, puntos coincidentes o puntos fuera de la imagen |
| `EscalaNoCalibrada` | Se intenta segmentar o calcular sin calibración |
| `PoligonoNoValido` | Menos de 3 puntos, área 0 o región excluida con vértices fuera de la imagen |
| `DatosInsuficientes` | No hay fragmentos suficientes para calcular (mínimo 3) |
| `AnalisisNoEncontrado` | (aplicación) el id no existe |
| `DatosNoValidos` | Nombre del análisis vacío o de más de 150 caracteres |
| `FragmentoNoEncontrado` | El id del fragmento no existe en el análisis |
