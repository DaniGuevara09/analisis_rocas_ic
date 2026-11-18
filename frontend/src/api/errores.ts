/** Error devuelto por la API con el formato `{codigo, detalle}` de docs/api.md. */
export class ErrorApi extends Error {
  readonly codigo: string;
  readonly detalle: string;
  readonly estadoHttp: number;

  constructor(codigo: string, detalle: string, estadoHttp: number) {
    super(detalle);
    this.name = "ErrorApi";
    this.codigo = codigo;
    this.detalle = detalle;
    this.estadoHttp = estadoHttp;
  }
}

const MENSAJES: Record<string, string> = {
  FORMATO_NO_VALIDO: "El archivo no es una imagen válida. Use una fotografía JPG o PNG.",
  DATOS_NO_VALIDOS: "Algunos datos no son válidos. Revíselos e intente de nuevo.",
  NO_ENCONTRADO: "El análisis no existe o fue eliminado.",
  ESCALA_NO_CALIBRADA: "Calibre la escala antes de continuar.",
  DATOS_INSUFICIENTES: "No hay suficientes fragmentos para calcular.",
  MODELO_NO_DISPONIBLE:
    "La segmentación automática no está disponible (falta el modelo en el servidor). Puede dibujar los fragmentos a mano.",
  ARCHIVO_DEMASIADO_GRANDE: "La imagen supera el tamaño máximo de 20 MB.",
  SIN_CONEXION: "No se pudo conectar con el servidor. Verifique su conexión e intente de nuevo.",
};

export const MENSAJE_GENERICO = "Ocurrió un error inesperado. Intente de nuevo.";

/** Único lugar que traduce un código de la API a un mensaje en español para el operador. */
export function mensajePorCodigo(codigo: string): string {
  return MENSAJES[codigo] ?? MENSAJE_GENERICO;
}

/** Mensaje para cualquier error capturado; en datos no válidos agrega el detalle del servidor. */
export function mensajeDeError(error: unknown): string {
  if (!(error instanceof ErrorApi)) {
    return MENSAJE_GENERICO;
  }
  const base = mensajePorCodigo(error.codigo);
  if (error.codigo === "DATOS_NO_VALIDOS" && error.detalle) {
    return `${base} (${error.detalle})`;
  }
  return base;
}
