/** Texto explicativo de cada indicador (contenido fijo; los valores vienen de la API). */
export type ClaveIndicador = "d20" | "d50" | "d60" | "d80" | "d90" | "indice_n";

export interface Definicion {
  nombre: string;
  /** % pasante que define el indicador; null para el índice n (no es un punto de la curva). */
  pasante_pct: number | null;
  definicion: string;
  aplicacion: string;
}

export const DEFINICIONES: Record<ClaveIndicador, Definicion> = {
  d20: {
    nombre: "D20",
    pasante_pct: 20,
    definicion: "Tamaño de abertura por el cual pasa el 20 % en masa del material.",
    aplicacion:
      "Caracteriza la fracción fina; valores bajos pueden indicar sobrefragmentación y generación excesiva de finos.",
  },
  d50: {
    nombre: "D50",
    pasante_pct: 50,
    definicion: "Tamaño medio: abertura por la cual pasa el 50 % en masa del material.",
    aplicacion:
      "Parámetro de referencia para comparar voladuras y calibrar modelos de fragmentación (p. ej., Kuz-Ram).",
  },
  d60: {
    nombre: "D60",
    pasante_pct: 60,
    definicion: "Tamaño de abertura por el cual pasa el 60 % en masa del material.",
    aplicacion: "Se emplea en coeficientes de uniformidad (Cu = D60/D10) y de curvatura.",
  },
  d80: {
    nombre: "D80",
    pasante_pct: 80,
    definicion: "Tamaño de abertura por el cual pasa el 80 % en masa del material.",
    aplicacion:
      "Dato de diseño para dimensionar chancado y molienda (índice de Bond) y evaluar el desempeño de la voladura.",
  },
  d90: {
    nombre: "D90",
    pasante_pct: 90,
    definicion: "Tamaño de abertura por el cual pasa el 90 % en masa del material.",
    aplicacion: "Indicador de sobretamaño; se contrasta con la abertura de alimentación del chancador primario.",
  },
  indice_n: {
    nombre: "Índice n",
    pasante_pct: null,
    definicion:
      "Exponente de la función Rosin-Rammler; describe la pendiente de la curva y la dispersión de tamaños.",
    aplicacion:
      "Valores altos indican distribución uniforme; valores bajos, distribución amplia. En voladuras suele encontrarse entre 0,8 y 2,2.",
  },
};

export const ORDEN_INDICADORES: ClaveIndicador[] = ["d20", "d50", "d60", "d80", "d90", "indice_n"];
