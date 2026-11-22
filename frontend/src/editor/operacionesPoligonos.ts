/**
 * Operaciones geométricas del editor (unir, dividir). Funciones puras en píxeles de la imagen.
 * Solo transforman contornos: los diámetros y la granulometría los calcula la API.
 */
import polygonClipping, { type MultiPolygon, type Pair, type Polygon } from "polygon-clipping";

import type { Punto } from "../api/tipos";

/** Extensión de la línea de corte: mucho mayor que cualquier foto. */
const LARGO_CORTE = 1e6;
/** Pedazos más pequeños que esto (px²) se descartan como ruido numérico. */
const AREA_MINIMA_PX = 1;
/**
 * Área mínima de un fragmento (px²). La API rechaza los menores (son clics accidentales);
 * el editor usa el mismo valor para avisar antes de guardar.
 */
export const AREA_MINIMA_FRAGMENTO_PX2 = 1;

/** Indica si un contorno es demasiado pequeño para ser un fragmento. */
export function esDiminuto(puntos: Punto[]): boolean {
  return areaPoligono(puntos) < AREA_MINIMA_FRAGMENTO_PX2;
}

function redondear(valor: number): number {
  return Math.round(valor * 2) / 2;
}

function aAnillo(puntos: Punto[]): Pair[] {
  return puntos.map((p) => [redondear(p.x), redondear(p.y)]);
}

function desdeAnillo(anillo: Pair[]): Punto[] {
  const abierto = anillo.length > 1 && anillo[0][0] === anillo[anillo.length - 1][0]
    && anillo[0][1] === anillo[anillo.length - 1][1]
    ? anillo.slice(0, -1)
    : anillo;
  return abierto.map(([x, y]) => ({ x, y }));
}

/** Contornos exteriores de un resultado de polygon-clipping (los huecos se ignoran). */
function exteriores(resultado: MultiPolygon): Punto[][] {
  return resultado
    .map((poligono) => desdeAnillo(poligono[0]))
    .filter((puntos) => puntos.length >= 3 && areaPoligono(puntos) >= AREA_MINIMA_PX);
}

/** Área en px² (fórmula del zapato, valor absoluto). */
export function areaPoligono(puntos: Punto[]): number {
  let suma = 0;
  puntos.forEach((a, i) => {
    const b = puntos[(i + 1) % puntos.length];
    suma += a.x * b.y - b.x * a.y;
  });
  return Math.abs(suma) / 2;
}

export function cercaDe(a: Punto, b: Punto, radio: number): boolean {
  return Math.hypot(a.x - b.x, a.y - b.y) <= radio;
}

/** Une varios fragmentos. Devuelve null si el resultado no es una sola pieza (no se tocan). */
export function unirPoligonos(poligonos: Punto[][]): Punto[] | null {
  if (poligonos.length < 2) {
    return null;
  }
  const [primero, ...resto] = poligonos.map((p): Polygon => [aAnillo(p)]);
  const piezas = exteriores(polygonClipping.union(primero, ...resto));
  return piezas.length === 1 ? piezas[0] : null;
}

/** Semiplano a un lado de la recta a→b, como un polígono enorme. */
function semiplano(a: Punto, b: Punto, lado: 1 | -1): Polygon {
  const largo = Math.hypot(b.x - a.x, b.y - a.y);
  const dx = ((b.x - a.x) / largo) * LARGO_CORTE;
  const dy = ((b.y - a.y) / largo) * LARGO_CORTE;
  const nx = -dy * lado;
  const ny = dx * lado;
  return [
    [
      [a.x - dx, a.y - dy],
      [b.x + dx, b.y + dy],
      [b.x + dx + nx, b.y + dy + ny],
      [a.x - dx + nx, a.y - dy + ny],
    ],
  ];
}

/**
 * Divide un fragmento con la recta que pasa por a y b (se prolonga a ambos lados).
 * Devuelve las piezas (2 o más) o null si la recta no lo atraviesa.
 */
export function dividirPoligono(poligono: Punto[], a: Punto, b: Punto): Punto[][] | null {
  if (cercaDe(a, b, 0)) {
    return null;
  }
  const sujeto: Polygon = [aAnillo(poligono)];
  const piezas = [
    ...exteriores(polygonClipping.intersection(sujeto, semiplano(a, b, 1))),
    ...exteriores(polygonClipping.intersection(sujeto, semiplano(a, b, -1))),
  ];
  return piezas.length >= 2 ? piezas : null;
}

function unitario(desde: Punto, hasta: Punto): Punto {
  const largo = Math.hypot(hasta.x - desde.x, hasta.y - desde.y);
  return { x: (hasta.x - desde.x) / largo, y: (hasta.y - desde.y) / largo };
}

/**
 * Lado de una línea quebrada: la línea prolongada por sus dos extremos y cerrada con
 * dos puntos lejanos hacia un mismo lado. Es un polígono enorme cuyo borde es el trazo.
 */
function ladoDeTrazo(trazo: Punto[]): Polygon {
  const primero = trazo[0];
  const ultimo = trazo[trazo.length - 1];
  const u0 = unitario(trazo[1], primero);
  const un = unitario(trazo[trazo.length - 2], ultimo);
  const inicio = { x: primero.x + u0.x * LARGO_CORTE, y: primero.y + u0.y * LARGO_CORTE };
  const fin = { x: ultimo.x + un.x * LARGO_CORTE, y: ultimo.y + un.y * LARGO_CORTE };
  const cuerda = unitario(inicio, fin);
  const normal = { x: -cuerda.y * LARGO_CORTE, y: cuerda.x * LARGO_CORTE };
  const anillo: Pair[] = [
    [inicio.x, inicio.y],
    ...aAnillo(trazo),
    [fin.x, fin.y],
    [fin.x + normal.x, fin.y + normal.y],
    [inicio.x + normal.x, inicio.y + normal.y],
  ];
  return [anillo];
}

/**
 * Divide un fragmento con una línea quebrada de 2 o más puntos (los extremos se prolongan).
 * Sirve para cortes que siguen una grieta irregular. Devuelve las piezas (2 o más) o null
 * si el trazo no atraviesa el fragmento.
 */
export function dividirConTrazo(poligono: Punto[], trazo: Punto[]): Punto[][] | null {
  const puntos = trazo.filter((p, i) => i === 0 || !cercaDe(p, trazo[i - 1], 0));
  if (puntos.length < 2) {
    return null;
  }
  if (puntos.length === 2) {
    return dividirPoligono(poligono, puntos[0], puntos[1]);
  }
  const sujeto: Polygon = [aAnillo(poligono)];
  const lado = ladoDeTrazo(puntos);
  const piezas = [
    ...exteriores(polygonClipping.intersection(sujeto, lado)),
    ...exteriores(polygonClipping.difference(sujeto, lado)),
  ];
  return piezas.length >= 2 ? piezas : null;
}

/** Punto dentro del polígono (ray casting). */
export function contienePunto(poligono: Punto[], punto: Punto): boolean {
  let dentro = false;
  poligono.forEach((a, i) => {
    const b = poligono[(i + 1) % poligono.length];
    if (a.y > punto.y !== b.y > punto.y) {
      const xCruce = a.x + ((punto.y - a.y) * (b.x - a.x)) / (b.y - a.y);
      if (punto.x < xCruce) {
        dentro = !dentro;
      }
    }
  });
  return dentro;
}

/**
 * Inserta un nuevo vértice en el segmento del borde del polígono más cercano al punto dado.
 * El nuevo punto se proyecta exactamente sobre la arista seleccionada.
 */
export function insertarPuntoEnBorde(poligono: Punto[], clic: Punto): Punto[] {
  if (poligono.length < 2) {
    return [...poligono, clic];
  }
  let mejorIndice = 0;
  let mejorDistancia = Number.POSITIVE_INFINITY;
  let mejorPunto: Punto = clic;

  for (let i = 0; i < poligono.length; i++) {
    const a = poligono[i];
    const b = poligono[(i + 1) % poligono.length];
    const vx = b.x - a.x;
    const vy = b.y - a.y;
    const largo2 = vx * vx + vy * vy;
    const t =
      largo2 > 0
        ? Math.max(0, Math.min(1, ((clic.x - a.x) * vx + (clic.y - a.y) * vy) / largo2))
        : 0;
    const proyectado = { x: a.x + t * vx, y: a.y + t * vy };
    const distancia = Math.hypot(clic.x - proyectado.x, clic.y - proyectado.y);
    if (distancia < mejorDistancia) {
      mejorDistancia = distancia;
      mejorIndice = i;
      mejorPunto = proyectado;
    }
  }

  return [
    ...poligono.slice(0, mejorIndice + 1),
    mejorPunto,
    ...poligono.slice(mejorIndice + 1),
  ];
}

const LADOS_DISCO_PINCEL = 8;

function discoPincel(centro: Punto, radio: number): Punto[] {
  const puntos: Punto[] = [];
  for (let i = 0; i < LADOS_DISCO_PINCEL; i++) {
    const angulo = (2 * Math.PI * i) / LADOS_DISCO_PINCEL;
    puntos.push({
      x: redondear(centro.x + Math.cos(angulo) * radio),
      y: redondear(centro.y + Math.sin(angulo) * radio),
    });
  }
  return puntos;
}

/**
 * Construye una cinta cerrada (contorno exterior) alrededor de una polilínea sin depender de
 * sweep-line cuando hay muchos puntos, evitando errores numéricos de polygon-clipping.
 */
function cintaDeTrazo(trazo: Punto[], radio: number): Punto[] {
  if (trazo.length === 0) {
    return [];
  }
  if (trazo.length === 1) {
    return discoPincel(trazo[0], radio);
  }
  const izquierda: Punto[] = [];
  const derecha: Punto[] = [];

  for (let i = 0; i < trazo.length; i++) {
    const actual = trazo[i];
    const previo = i > 0 ? trazo[i - 1] :actual;
    const siguiente = i < trazo.length - 1 ? trazo[i + 1] : actual;
    const dx = siguiente.x - previo.x;
    const dy = siguiente.y - previo.y;
    const largo = Math.hypot(dx, dy) || 1;
    const nx = (-dy / largo) * radio;
    const ny = (dx / largo) * radio;
    izquierda.push({ x: redondear(actual.x + nx), y: redondear(actual.y + ny) });
    derecha.push({ x: redondear(actual.x - nx), y: redondear(actual.y - ny) });
  }

  const primero = trazo[0];
  const segundo = trazo[1];
  const angInicio = Math.atan2(primero.y - segundo.y, primero.x - segundo.x);
  const tapaInicio: Punto[] = [
    {
      x: redondear(primero.x + Math.cos(angInicio) * radio),
      y: redondear(primero.y + Math.sin(angInicio) * radio),
    },
  ];

  const ultimo = trazo[trazo.length - 1];
  const penultimo = trazo[trazo.length - 2];
  const angFin = Math.atan2(ultimo.y - penultimo.y, ultimo.x - penultimo.x);
  const tapaFin: Punto[] = [
    {
      x: redondear(ultimo.x + Math.cos(angFin) * radio),
      y: redondear(ultimo.y + Math.sin(angFin) * radio),
    },
  ];

  return [...izquierda, ...tapaFin, ...derecha.reverse(), ...tapaInicio];
}

/** Simplifica los puntos del trazo del pincel para que estén separados al menos `pasoMinimo` px. */
function simplificarTrazoPincel(trazo: Punto[], pasoMinimo: number): Punto[] {
  if (trazo.length <= 2) {
    return trazo;
  }
  const resultado: Punto[] = [trazo[0]];
  for (let i = 1; i < trazo.length - 1; i++) {
    const ultimo = resultado[resultado.length - 1];
    if (Math.hypot(trazo[i].x - ultimo.x, trazo[i].y - ultimo.y) >= pasoMinimo) {
      resultado.push(trazo[i]);
    }
  }
  const final = trazo[trazo.length - 1];
  if (!cercaDe(resultado[resultado.length - 1], final, 1)) {
    resultado.push(final);
  }
  return resultado;
}

/** Construye el polígono continuo barrido por un trazo de pincel con radio en píxeles.
 * Si el trazo forma un lazo que rodea una roca, devuelve el contorno relleno en lugar de una cinta hueca.
 */
export function poligonoDePincel(trazo: Punto[], radio: number): Punto[] {
  const r = Math.max(2, Math.round(radio));
  if (trazo.length === 0) {
    return [];
  }
  const simplificado = simplificarTrazoPincel(trazo, Math.max(4, r * 0.75));
  if (simplificado.length >= 5) {
    const xs = simplificado.map((p) => p.x);
    const ys = simplificado.map((p) => p.y);
    const diag = Math.hypot(Math.max(...xs) - Math.min(...xs), Math.max(...ys) - Math.min(...ys));
    const distCierre = Math.hypot(
      simplificado[simplificado.length - 1].x - simplificado[0].x,
      simplificado[simplificado.length - 1].y - simplificado[0].y,
    );
    const areaLazo = areaPoligono(simplificado);
    const perimetro = simplificado
      .slice(1)
      .reduce((s, p, i) => s + Math.hypot(p.x - simplificado[i].x, p.y - simplificado[i].y), 0);
    if (
      diag >= 12 &&
      distCierre <= Math.max(r * 3.5, diag * 0.5) &&
      areaLazo > Math.max(120, perimetro * r * 0.4)
    ) {
      return simplificado.map((p) => ({ x: redondear(p.x), y: redondear(p.y) }));
    }
  }
  return cintaDeTrazo(simplificado, r);
}

/** Indica si dos polígonos se solapan o se tocan (protegido contra errores de sweep-line). */
export function poligonosSeTocan(a: Punto[], b: Punto[]): boolean {
  if (a.length < 3 || b.length < 3) {
    return false;
  }
  try {
    const inter = exteriores(polygonClipping.intersection([aAnillo(a)], [aAnillo(b)]));
    return inter.length > 0;
  } catch {
    return a.some((p) => contienePunto(b, p)) || b.some((p) => contienePunto(a, p));
  }
}

/**
 * Indica si el usuario pintó intencionalmente dentro de un fragmento (el eje del trazo
 * entra en el polígono o el pincel cubre una fracción significativa del fragmento).
 */
export function trazoEntraEnPoligono(trazo: Punto[], poligono: Punto[], zonaPincel: Punto[]): boolean {
  if (poligono.length < 3 || trazo.length === 0) {
    return false;
  }
  if (trazo.some((p) => contienePunto(poligono, p))) {
    return true;
  }
  if (zonaPincel.length < 3) {
    return false;
  }
  try {
    const inter = exteriores(polygonClipping.intersection([aAnillo(poligono)], [aAnillo(zonaPincel)]));
    if (inter.length === 0) {
      return false;
    }
    const areaInter = inter.reduce((s, p) => s + areaPoligono(p), 0);
    const areaFrag = areaPoligono(poligono);
    return areaFrag > 0 && areaInter / areaFrag >= 0.3;
  } catch {
    return false;
  }
}

/**
 * Recorta un polígono nuevo restándole los fragmentos vecinos ya existentes uno por uno
 * de forma segura para que no invada ni fusione rocas adyacentes.
 */
export function recortarContraExistentes(nuevo: Punto[], existentes: Punto[][]): Punto[] | null {
  if (nuevo.length < 3) {
    return null;
  }
  let actual = nuevo;
  for (const vecino of existentes) {
    if (vecino.length < 3 || !poligonosSeTocan(actual, vecino)) {
      continue;
    }
    try {
      const piezas = exteriores(polygonClipping.difference([aAnillo(actual)], [aAnillo(vecino)]));
      if (piezas.length === 0) {
        return null;
      }
      actual = piezas.reduce((mayor, p) => (areaPoligono(p) > areaPoligono(mayor) ? p : mayor));
    } catch {
      // Si polygon-clipping falla por precisión numérica con un vecino, conserva el contorno actual.
    }
  }
  return actual;
}

/**
 * Une los polígonos tocados por el pincel mágico en una sola roca (uniendo de dos en dos
 * para evitar fallos de precisión en SweepLine).
 */
export function unirConPincel(poligonos: Punto[][], zonaPincel: Punto[]): Punto[] | null {
  if (poligonos.length === 0) {
    return null;
  }
  try {
    if (poligonos.length >= 2) {
      const directa = unirPoligonos(poligonos);
      if (directa) {
        return directa;
      }
    }
    let acumulado = zonaPincel;
    for (const pol of poligonos) {
      const piezas = exteriores(polygonClipping.union([aAnillo(acumulado)], [aAnillo(pol)]));
      if (piezas.length > 0) {
        acumulado = piezas.reduce((mayor, p) => (areaPoligono(p) > areaPoligono(mayor) ? p : mayor));
      }
    }
    return acumulado;
  } catch {
    return poligonos[0];
  }
}
