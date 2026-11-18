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
