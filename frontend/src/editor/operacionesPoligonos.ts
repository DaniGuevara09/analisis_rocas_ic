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

function aAnillo(puntos: Punto[]): Pair[] {
  return puntos.map((p) => [p.x, p.y]);
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
