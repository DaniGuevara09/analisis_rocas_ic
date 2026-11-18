import { ErrorApi } from "./errores";
import type { AnalisisDetalle, AnalisisResumen, Punto, RespuestaCalibracion } from "./tipos";

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
