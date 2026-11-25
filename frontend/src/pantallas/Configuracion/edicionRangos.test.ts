import { describe, expect, it } from "vitest";

import type { ConfiguracionRangos } from "../../api/tipos";
import {
  agregarRango,
  cambiarModo,
  cortesIniciales,
  problemaDeConfiguracion,
  quitarRango,
} from "./edicionRangos";

const BASE: ConfiguracionRangos = {
  modo: "RELATIVO",
  cortes: [20, 50, 80, 90],
  nombres: ["A", "B", "C", "D", "E"],
  colores: ["#000001", "#000002", "#000003", "#000004", "#000005"],
};

describe("edicionRangos", () => {
  it("agregar en modo relativo pone el corte a mitad de camino hacia 100", () => {
    const nueva = agregarRango(BASE, "#ffffff");
    expect(nueva.cortes).toEqual([20, 50, 80, 90, 95]);
    expect(nueva.nombres).toHaveLength(6);
    expect(nueva.colores[5]).toBe("#ffffff");
  });

  it("agregar en modo absoluto duplica el último corte", () => {
    const absoluta = { ...BASE, modo: "ABSOLUTO" as const, cortes: [50, 100, 200, 400] };
    expect(agregarRango(absoluta, "#ffffff").cortes).toEqual([50, 100, 200, 400, 800]);
  });

  it("no pasa de 8 rangos", () => {
    let config = BASE;
    for (let i = 0; i < 10; i++) {
      config = agregarRango(config, "#ffffff");
    }
    expect(config.nombres).toHaveLength(8);
  });

  it("quitar un rango intermedio elimina su límite superior", () => {
    const nueva = quitarRango(BASE, 1);
    expect(nueva.cortes).toEqual([20, 80, 90]);
    expect(nueva.nombres).toEqual(["A", "C", "D", "E"]);
  });

  it("quitar el último rango elimina el último límite", () => {
    expect(quitarRango(BASE, 4).cortes).toEqual([20, 50, 80]);
  });

  it("no deja menos de 2 rangos", () => {
    const dos = { ...BASE, cortes: [50], nombres: ["A", "B"], colores: ["#000001", "#000002"] };
    expect(quitarRango(dos, 0)).toBe(dos);
  });

  it("cambiar de modo recalcula los cortes y conserva nombres y colores", () => {
    const absoluta = cambiarModo(BASE, "ABSOLUTO");
    expect(absoluta.cortes).toEqual([50, 100, 200, 400]);
    expect(absoluta.nombres).toEqual(BASE.nombres);
    expect(cortesIniciales("RELATIVO", 3)).toEqual([25, 50, 75]);
  });

  it("detecta problemas comunes del formulario", () => {
    expect(problemaDeConfiguracion(BASE)).toBe("");
    expect(problemaDeConfiguracion({ ...BASE, cortes: [20, 10, 80, 90] })).toMatch(/mayor/);
    expect(problemaDeConfiguracion({ ...BASE, cortes: [20, 50, 80, 120] })).toMatch(/100/);
    expect(problemaDeConfiguracion({ ...BASE, nombres: ["A", " ", "C", "D", "E"] })).toMatch(/nombre/);
  });
});
