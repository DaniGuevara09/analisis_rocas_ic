import { describe, expect, it } from "vitest";

import { nombreDesdeArchivo, validarArchivo, validarNombre } from "./NuevoAnalisis";

const archivo = (nombre: string, tamano = 1000) =>
  new File([new Uint8Array(tamano)], nombre, { type: "application/octet-stream" });

describe("validarArchivo", () => {
  it.each(["foto.jpg", "foto.JPEG", "foto.png"])("acepta %s", (nombre) => {
    expect(validarArchivo(archivo(nombre))).toBe("");
  });

  it("rechaza otra extensión", () => {
    expect(validarArchivo(archivo("nota.txt"))).toContain("JPG o PNG");
  });

  it("rechaza más de 20 MB", () => {
    expect(validarArchivo(archivo("foto.jpg", 20 * 1024 * 1024 + 1))).toContain("20 MB");
  });
});

describe("validarNombre", () => {
  it("exige un nombre no vacío", () => {
    expect(validarNombre("")).not.toBe("");
    expect(validarNombre("   ")).not.toBe("");
  });

  it("limita la longitud a 150 caracteres", () => {
    expect(validarNombre("a".repeat(150))).toBe("");
    expect(validarNombre("a".repeat(151))).toContain("150");
  });

  it("acepta un nombre normal", () => {
    expect(validarNombre("Banco 3 – frente norte")).toBe("");
  });
});

describe("nombreDesdeArchivo", () => {
  it("quita la extensión y cambia guiones por espacios", () => {
    expect(nombreDesdeArchivo("banco_3-norte.JPG")).toBe("banco 3 norte");
  });
});
