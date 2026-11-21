/** Longitud del objeto de referencia: unidades, objetos frecuentes y validación. */
import type { Punto } from "../../api/tipos";

export type Unidad = "mm" | "cm" | "m";

export const MM_POR_UNIDAD: Record<Unidad, number> = { mm: 1, cm: 10, m: 1000 };

export const UNIDADES: Unidad[] = ["mm", "cm", "m"];

export interface ObjetoReferencia {
  nombre: string;
  valor: number;
  unidad: Unidad;
}

/** Objetos de referencia habituales en campo; el operador puede escribir cualquier otro valor. */
export const OBJETOS_REFERENCIA: ObjetoReferencia[] = [
  { nombre: "Regla 30 cm", valor: 30, unidad: "cm" },
  { nombre: "Regla 50 cm", valor: 50, unidad: "cm" },
  { nombre: "Flexómetro 1 m", valor: 1, unidad: "m" },
  { nombre: "Mira 2 m", valor: 2, unidad: "m" },
];

/** Rango habitual de un objeto de referencia en una foto de pila (mm). */
const MINIMO_HABITUAL_MM = 50;
const MAXIMO_HABITUAL_MM = 3000;

/** Convierte el texto del campo a mm; null si no es un número mayor que cero. */
export function aMilimetros(texto: string, unidad: Unidad): number | null {
  const valor = Number(texto.replace(",", "."));
  if (!texto.trim() || !Number.isFinite(valor) || valor <= 0) {
    return null;
  }
  return valor * MM_POR_UNIDAD[unidad];
}

/** Distancia en píxeles de una línea de 2 puntos; null si está incompleta o mide 0. */
export function distanciaLineaPx(linea: Punto[]): number | null {
  if (linea.length !== 2) {
    return null;
  }
  const d = Math.hypot(linea[1].x - linea[0].x, linea[1].y - linea[0].y);
  return d > 0 ? d : null;
}

/**
 * Calcula la longitud efectiva en mm para la línea 1 de modo que el factor resultante
 * (longitud / d1Px) sea el promedio de los factores de los dos objetos de referencia.
 */
export function calcularLongitudEfectivaMm(
  d1Px: number,
  l1Mm: number,
  d2Px?: number | null,
  l2Mm?: number | null,
): number {
  if (d2Px != null && d2Px > 0 && l2Mm != null && l2Mm > 0 && d1Px > 0) {
    const f1 = l1Mm / d1Px;
    const f2 = l2Mm / d2Px;
    const factorPromedio = (f1 + f2) / 2;
    return factorPromedio * d1Px;
  }
  return l1Mm;
}

/** Aviso (no bloquea) si la longitud es poco habitual: suele ser un error de unidad. */
export function avisoLongitud(longitudMm: number | null): string {
  if (longitudMm === null) {
    return "";
  }
  if (longitudMm < MINIMO_HABITUAL_MM || longitudMm > MAXIMO_HABITUAL_MM) {
    return "Valor poco habitual para un objeto de referencia. Verifique la medida y la unidad: un error aquí escala todos los tamaños.";
  }
  return "";
}
