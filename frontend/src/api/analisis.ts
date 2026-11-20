import { ErrorApi } from "./errores";
import type {
  AnalisisDetalle,
  AnalisisResumen,
  ConfiguracionRangos,
  Fragmento,
  FragmentoSolicitud,
  Punto,
  RespuestaCalibracion,
  Resultados,
  Salud,
} from "./tipos";

const BASE = "/api";
const CODIGO_DESCONOCIDO = "ERROR_DESCONOCIDO";
const HTTP_DEMASIADO_GRANDE = 413;

function esCuerpoDeError(valor: unknown): valor is { codigo: string; detalle: string } {
  return (
    typeof valor === "object" &&
    valor !== null &&
    typeof (valor as Record<string, unknown>).codigo === "string" &&
    typeof (valor as Record<string, unknown>).detalle === "string"
  );
}

async function errorDeRespuesta(respuesta: Response): Promise<ErrorApi> {
  try {
    const cuerpo: unknown = await respuesta.json();
    if (esCuerpoDeError(cuerpo)) {
      return new ErrorApi(cuerpo.codigo, cuerpo.detalle, respuesta.status);
    }
  } catch {
    // El cuerpo no es JSON (por ejemplo, el 413 de nginx): se deduce del estado HTTP.
  }
  const codigo = respuesta.status === HTTP_DEMASIADO_GRANDE ? "ARCHIVO_DEMASIADO_GRANDE" : CODIGO_DESCONOCIDO;
  return new ErrorApi(codigo, respuesta.statusText, respuesta.status);
}

async function solicitar(ruta: string, init?: RequestInit): Promise<Response> {
  let respuesta: Response;
  try {
    respuesta = await fetch(`${BASE}${ruta}`, init);
  } catch {
    throw new ErrorApi("SIN_CONEXION", "Sin conexión con el servidor", 0);
  }
  if (!respuesta.ok) {
    throw await errorDeRespuesta(respuesta);
  }
  return respuesta;
}

function conJson(metodo: string, cuerpo: unknown): RequestInit {
  return {
    method: metodo,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(cuerpo),
  };
}

export async function listarAnalisis(): Promise<AnalisisResumen[]> {
  return (await (await solicitar("/analisis")).json()) as AnalisisResumen[];
}

export async function crearAnalisis(nombre: string, imagen: File): Promise<AnalisisResumen> {
  const formulario = new FormData();
  formulario.append("nombre", nombre);
  formulario.append("imagen", imagen);
  const respuesta = await solicitar("/analisis", { method: "POST", body: formulario });
  return (await respuesta.json()) as AnalisisResumen;
}

export async function obtenerAnalisis(id: string): Promise<AnalisisDetalle> {
  return (await (await solicitar(`/analisis/${id}`)).json()) as AnalisisDetalle;
}

export async function renombrarAnalisis(id: string, nombre: string): Promise<AnalisisResumen> {
  const respuesta = await solicitar(`/analisis/${id}`, conJson("PATCH", { nombre }));
  return (await respuesta.json()) as AnalisisResumen;
}

export async function eliminarAnalisis(id: string): Promise<void> {
  await solicitar(`/analisis/${id}`, { method: "DELETE" });
}

export function urlImagen(id: string): string {
  return `${BASE}/analisis/${id}/imagen`;
}

export async function calibrar(
  id: string,
  inicio: Punto,
  fin: Punto,
  longitudRealMm: number,
): Promise<RespuestaCalibracion> {
  const cuerpo = { inicio, fin, longitud_real_mm: longitudRealMm };
  const respuesta = await solicitar(`/analisis/${id}/calibracion`, conJson("PUT", cuerpo));
  return (await respuesta.json()) as RespuestaCalibracion;
}

export async function excluirRegion(id: string, poligono: Punto[]): Promise<AnalisisDetalle> {
  const respuesta = await solicitar(`/analisis/${id}/region-excluida`, conJson("PUT", { poligono }));
  return (await respuesta.json()) as AnalisisDetalle;
}

export async function quitarRegion(id: string): Promise<void> {
  await solicitar(`/analisis/${id}/region-excluida`, { method: "DELETE" });
}

/** Segmenta con el modelo; reemplaza todos los fragmentos (incluidos los editados). */
export async function segmentar(id: string): Promise<Fragmento[]> {
  const respuesta = await solicitar(`/analisis/${id}/segmentacion`, { method: "POST" });
  return (await respuesta.json()) as Fragmento[];
}

/** Guarda la lista completa de fragmentos editada. */
export async function guardarFragmentos(
  id: string,
  fragmentos: FragmentoSolicitud[],
): Promise<Fragmento[]> {
  const respuesta = await solicitar(`/analisis/${id}/fragmentos`, conJson("PUT", { fragmentos }));
  return (await respuesta.json()) as Fragmento[];
}

export async function obtenerResultados(id: string): Promise<Resultados> {
  return (await (await solicitar(`/analisis/${id}/resultados`)).json()) as Resultados;
}

/** URL de descarga del CSV de resultados (RF-09). */
export function urlCsv(id: string): string {
  return `${BASE}/analisis/${id}/resultados.csv`;
}

export async function obtenerSalud(): Promise<Salud> {
  return (await (await solicitar("/salud")).json()) as Salud;
}

export async function obtenerConfiguracionRangos(): Promise<ConfiguracionRangos> {
  return (await (await solicitar("/configuracion/rangos")).json()) as ConfiguracionRangos;
}

export async function guardarConfiguracionRangos(
  configuracion: ConfiguracionRangos,
): Promise<ConfiguracionRangos> {
  const respuesta = await solicitar("/configuracion/rangos", conJson("PUT", configuracion));
  return (await respuesta.json()) as ConfiguracionRangos;
}

export async function restablecerConfiguracionRangos(): Promise<ConfiguracionRangos> {
  const respuesta = await solicitar("/configuracion/rangos", { method: "DELETE" });
  return (await respuesta.json()) as ConfiguracionRangos;
}
