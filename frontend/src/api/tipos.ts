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

/** Fragmento que el editor envía en PUT /fragmentos; sin id si es nuevo. */
export interface FragmentoSolicitud {
  id?: string;
  poligono: Punto[];
  origen: OrigenFragmento;
}

export interface PuntoCurva {
  diametro_mm: number;
  pasante_pct: number;
}

export interface RangoTamano {
  indice: number;
  nombre: string;
  /** Color "#rrggbb" configurado para el rango (RF-14). */
  color: string;
  limite_inferior_mm: number;
  limite_superior_mm: number | null;
}

export interface ClaseHistograma {
  limite_inferior_mm: number;
  limite_superior_mm: number;
  numero_fragmentos: number;
  porcentaje_retenido: number;
}

export interface FragmentoMedido {
  id: string;
  diametro_equivalente_mm: number;
  indice_rango: number;
}

/** Respuesta de GET /analisis/{id}/resultados. */
export interface Resultados {
  d20: number;
  d50: number;
  d60: number;
  d80: number;
  d90: number;
  indice_n: number;
  numero_fragmentos: number;
  curva: PuntoCurva[];
  rangos: RangoTamano[];
  histograma: ClaseHistograma[];
  fragmentos: FragmentoMedido[];
  supuestos: string[];
}

export type ModoRangos = "RELATIVO" | "ABSOLUTO";

/** Configuración de rangos (RF-14): N cortes definen N + 1 rangos con nombre y color. */
export interface ConfiguracionRangos {
  modo: ModoRangos;
  cortes: number[];
  nombres: string[];
  colores: string[];
}

export interface Salud {
  estado: string;
  modelo_disponible: boolean;
}
