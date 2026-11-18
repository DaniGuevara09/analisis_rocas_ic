/** Lee los tokens de `tokens.css` en tiempo de ejecución (para los trazos de Konva). */
export function leerToken(nombre: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(nombre).trim();
}

export function leerNumero(nombre: string): number {
  return Number.parseFloat(leerToken(nombre));
}

export function leerLista(nombre: string): number[] {
  return leerToken(nombre)
    .split(/\s+/)
    .map(Number)
    .filter((valor) => Number.isFinite(valor));
}

export interface EstiloTrazos {
  colorCalibracion: string;
  colorRegion: string;
  rellenoRegion: string;
  colorVertice: string;
  grosor: number;
  radioVertice: number;
  punteado: number[];
}

export function leerEstiloTrazos(): EstiloTrazos {
  return {
    colorCalibracion: leerToken("--color-trazo-calibracion"),
    colorRegion: leerToken("--color-trazo-region"),
    rellenoRegion: leerToken("--color-relleno-region"),
    colorVertice: leerToken("--color-vertice"),
    grosor: leerNumero("--trazo-grosor"),
    radioVertice: leerNumero("--vertice-radio"),
    punteado: leerLista("--trazo-punteado"),
  };
}

/** "#rrggbb" + alfa → "rgba(r, g, b, alfa)" (para rellenos semitransparentes de Konva). */
export function conAlfa(hex: string, alfa: number): string {
  const limpio = hex.replace("#", "");
  const r = Number.parseInt(limpio.slice(0, 2), 16);
  const g = Number.parseInt(limpio.slice(2, 4), 16);
  const b = Number.parseInt(limpio.slice(4, 6), 16);
  return `rgba(${r}, ${g}, ${b}, ${alfa})`;
}

export const NUMERO_RANGOS = 5;

export interface EstiloFragmentos {
  colorFragmento: string;
  colorSeleccionado: string;
  colorDivision: string;
  colorDibujo: string;
  colorVertice: string;
  alfaRelleno: number;
  alfaSeleccionado: number;
  coloresRango: string[];
  grosor: number;
  radioVertice: number;
  punteado: number[];
}

export function leerEstiloFragmentos(): EstiloFragmentos {
  return {
    colorFragmento: leerToken("--color-fragmento"),
    colorSeleccionado: leerToken("--color-fragmento-seleccionado"),
    colorDivision: leerToken("--color-trazo-division"),
    colorDibujo: leerToken("--color-trazo-dibujo"),
    colorVertice: leerToken("--color-vertice"),
    alfaRelleno: leerNumero("--alfa-relleno-fragmento"),
    alfaSeleccionado: leerNumero("--alfa-relleno-seleccionado"),
    coloresRango: Array.from({ length: NUMERO_RANGOS }, (_, i) => leerToken(`--color-rango-${i}`)),
    grosor: leerNumero("--trazo-grosor"),
    radioVertice: leerNumero("--vertice-radio"),
    punteado: leerLista("--trazo-punteado"),
  };
}
