/** Conversión entre coordenadas de pantalla (lienzo) y de la imagen original. Funciones puras. */
import type { Punto } from "../api/tipos";

/** Escala (pantalla / imagen) para que la imagen quepa completa en el lienzo. */
export function escalaAjuste(
  anchoImg: number,
  altoImg: number,
  anchoLienzo: number,
  altoLienzo: number,
): number {
  return Math.min(anchoLienzo / anchoImg, altoLienzo / altoImg);
}

/** Pantalla → píxeles de la imagen original (lo que se envía a la API). */
export function aImagen(punto: Punto, escala: number): Punto {
  return { x: punto.x / escala, y: punto.y / escala };
}

/** Píxeles de la imagen original → pantalla. */
export function aPantalla(punto: Punto, escala: number): Punto {
  return { x: punto.x * escala, y: punto.y * escala };
}

export function distancia(a: Punto, b: Punto): number {
  return Math.hypot(b.x - a.x, b.y - a.y);
}

export function limitar(valor: number, minimo: number, maximo: number): number {
  return Math.min(Math.max(valor, minimo), maximo);
}

/** Lista de puntos → arreglo plano [x1, y1, x2, y2, ...] que usa Konva. */
export function aplanar(puntos: Punto[]): number[] {
  return puntos.flatMap((punto) => [punto.x, punto.y]);
}
