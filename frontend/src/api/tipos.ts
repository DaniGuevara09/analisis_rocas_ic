/** Tipos exactamente según los esquemas de docs/api.md. Coordenadas en píxeles de la imagen original. */
export interface Punto {
  x: number;
  y: number;
}

export type EstadoAnalisis = "IMAGEN_CARGADA" | "CALIBRADO" | "SEGMENTADO";
export type FormatoImagen = "JPG" | "PNG";
export type OrigenFragmento = "MODELO" | "MANUAL";

export interface AnalisisResumen {
  id: string;
  nombre: string;
  fecha_creacion: string;
  estado: EstadoAnalisis;
  numero_fragmentos: number;
}

export interface ImagenAnalisis {
  url: string;
  ancho_px: number;
  alto_px: number;
  formato: FormatoImagen;
}

export interface Calibracion {
  inicio: Punto;
  fin: Punto;
  longitud_real_mm: number;
  factor_mm_por_px: number;
}

export interface RegionExcluida {
  poligono: Punto[];
}

export interface Fragmento {
  id: string;
  poligono: Punto[];
  origen: OrigenFragmento;
  diametro_equivalente_mm: number | null;
}

export interface AnalisisDetalle extends AnalisisResumen {
  imagen: ImagenAnalisis;
  calibracion: Calibracion | null;
  region_excluida: RegionExcluida | null;
  fragmentos: Fragmento[];
}

export interface RespuestaCalibracion {
  factor_mm_por_px: number;
  estado: EstadoAnalisis;
}
