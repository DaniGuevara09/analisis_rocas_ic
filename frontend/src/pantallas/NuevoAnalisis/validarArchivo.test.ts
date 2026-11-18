import { describe, expect, it } from "vitest";

import { validarArchivo } from "./NuevoAnalisis";

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
