/** Longitud del objeto de referencia: unidades, objetos frecuentes y validación. */

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
