import { describe, expect, it } from "vitest";

import { ErrorApi, MENSAJE_GENERICO, mensajeDeError, mensajePorCodigo } from "./errores";

describe("mensajePorCodigo", () => {
  it.each([
    "FORMATO_NO_VALIDO",
    "DATOS_NO_VALIDOS",
    "NO_ENCONTRADO",
    "ESCALA_NO_CALIBRADA",
    "DATOS_INSUFICIENTES",
    "ARCHIVO_DEMASIADO_GRANDE",
    "SIN_CONEXION",
  ])("traduce %s a un mensaje propio", (codigo) => {
    const mensaje = mensajePorCodigo(codigo);
    expect(mensaje).not.toBe(MENSAJE_GENERICO);
    expect(mensaje).not.toContain(codigo);
  });

  it("usa un mensaje genérico para un código desconocido", () => {
    expect(mensajePorCodigo("OTRO")).toBe(MENSAJE_GENERICO);
  });
});

describe("mensajeDeError", () => {
  it("traduce un ErrorApi por su código", () => {
    const error = new ErrorApi("FORMATO_NO_VALIDO", "El archivo no es una imagen", 415);
    expect(mensajeDeError(error)).toBe(mensajePorCodigo("FORMATO_NO_VALIDO"));
  });

  it("agrega el detalle del servidor en datos no válidos", () => {
    const error = new ErrorApi("DATOS_NO_VALIDOS", "El nombre no puede estar vacio", 422);
    expect(mensajeDeError(error)).toContain("El nombre no puede estar vacio");
  });

  it("usa el mensaje genérico para errores que no son de la API", () => {
    expect(mensajeDeError(new Error("x"))).toBe(MENSAJE_GENERICO);
  });

  it("ErrorApi conserva código, detalle y estado HTTP", () => {
    const error = new ErrorApi("NO_ENCONTRADO", "no existe", 404);
    expect([error.codigo, error.detalle, error.estadoHttp]).toEqual(["NO_ENCONTRADO", "no existe", 404]);
  });
});
