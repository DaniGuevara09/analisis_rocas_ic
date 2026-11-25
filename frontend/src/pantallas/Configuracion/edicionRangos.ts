/**
 * Edición del formulario de rangos (RF-14). Funciones puras: solo arman la configuración;
 * la validación definitiva la hace la API (dominio).
 */
import type { ConfiguracionRangos, ModoRangos } from "../../api/tipos";

export const MAXIMO_RANGOS = 8;
export const MINIMO_RANGOS = 2;

function redondear(valor: number): number {
  return Math.round(valor * 10) / 10;
}

/** Cortes iniciales cuando se cambia de modo, conservando la cantidad de rangos. */
export function cortesIniciales(modo: ModoRangos, cantidadCortes: number): number[] {
  return Array.from({ length: cantidadCortes }, (_, i) =>
    modo === "RELATIVO" ? redondear(((i + 1) * 100) / (cantidadCortes + 1)) : 50 * 2 ** i,
  );
}

export function cambiarModo(configuracion: ConfiguracionRangos, modo: ModoRangos): ConfiguracionRangos {
  if (modo === configuracion.modo) {
    return configuracion;
  }
  return { ...configuracion, modo, cortes: cortesIniciales(modo, configuracion.cortes.length) };
}

/** Agrega un rango al final (más grueso). Devuelve la misma configuración si no cabe otro. */
export function agregarRango(configuracion: ConfiguracionRangos, colorNuevo: string): ConfiguracionRangos {
  const { cortes, nombres, colores, modo } = configuracion;
  if (nombres.length >= MAXIMO_RANGOS) {
    return configuracion;
  }
  const ultimo = cortes[cortes.length - 1];
  const nuevoCorte = modo === "RELATIVO" ? redondear(ultimo + (100 - ultimo) / 2) : ultimo * 2;
  if (modo === "RELATIVO" && nuevoCorte >= 100) {
    return configuracion;
  }
  return {
    ...configuracion,
    cortes: [...cortes, nuevoCorte],
    nombres: [...nombres, `Rango ${nombres.length + 1}`],
    colores: [...colores, colorNuevo],
  };
}

/** Quita el rango `indice`; sus fragmentos pasan al rango siguiente (o al anterior si es el último). */
export function quitarRango(configuracion: ConfiguracionRangos, indice: number): ConfiguracionRangos {
  const { cortes, nombres, colores } = configuracion;
  if (nombres.length <= MINIMO_RANGOS) {
    return configuracion;
  }
  const corteQuitado = indice >= cortes.length ? cortes.length - 1 : indice;
  return {
    ...configuracion,
    cortes: cortes.filter((_, i) => i !== corteQuitado),
    nombres: nombres.filter((_, i) => i !== indice),
    colores: colores.filter((_, i) => i !== indice),
  };
}

export function cambiarEnLista<T>(lista: T[], indice: number, valor: T): T[] {
  return lista.map((actual, i) => (i === indice ? valor : actual));
}

/** Mensaje de ayuda inmediata para el formulario ("" si se ve bien). */
export function problemaDeConfiguracion(configuracion: ConfiguracionRangos): string {
  const { cortes, nombres, modo } = configuracion;
  if (cortes.some((c) => !Number.isFinite(c) || c <= 0)) {
    return "Todos los límites deben ser números mayores que cero.";
  }
  if (cortes.some((c, i) => i > 0 && c <= cortes[i - 1])) {
    return "Cada límite debe ser mayor que el anterior.";
  }
  if (modo === "RELATIVO" && cortes.some((c) => c >= 100)) {
    return "En modo relativo los límites son porcentajes entre 0 y 100.";
  }
  if (nombres.some((n) => !n.trim())) {
    return "Cada rango necesita un nombre.";
  }
  return "";
}
