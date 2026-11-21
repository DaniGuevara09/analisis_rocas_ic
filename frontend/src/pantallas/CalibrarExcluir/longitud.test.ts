import { describe, expect, it } from "vitest";

import { aMilimetros, avisoLongitud, calcularLongitudEfectivaMm, distanciaLineaPx } from "./longitud";

describe("aMilimetros", () => {
  it("convierte cm y m a mm", () => {
    expect(aMilimetros("30", "cm")).toBe(300);
    expect(aMilimetros("1,5", "m")).toBe(1500);
    expect(aMilimetros("250", "mm")).toBe(250);
  });

  it("rechaza vacío, cero, negativos y texto", () => {
    expect(aMilimetros("", "mm")).toBeNull();
    expect(aMilimetros("0", "cm")).toBeNull();
    expect(aMilimetros("-3", "m")).toBeNull();
    expect(aMilimetros("abc", "mm")).toBeNull();
  });
});

describe("avisoLongitud", () => {
  it("avisa si el objeto parece demasiado chico o grande", () => {
    expect(avisoLongitud(5)).not.toBe("");
    expect(avisoLongitud(10000)).not.toBe("");
  });

  it("no avisa en valores habituales ni sin valor", () => {
    expect(avisoLongitud(300)).toBe("");
    expect(avisoLongitud(null)).toBe("");
  });
});

describe("distanciaLineaPx y calcularLongitudEfectivaMm", () => {
  it("calcula la distancia de una línea de 2 puntos", () => {
    expect(distanciaLineaPx([{ x: 0, y: 0 }])).toBeNull();
    expect(
      distanciaLineaPx([
        { x: 0, y: 0 },
        { x: 300, y: 400 },
      ]),
    ).toBe(500);
  });

  it("promedia el factor de escala cuando hay dos objetos de referencia", () => {
    // Objeto 1: 100 px = 200 mm -> f1 = 2.0 mm/px
    // Objeto 2: 200 px = 600 mm -> f2 = 3.0 mm/px
    // Factor promedio = 2.5 mm/px -> Longitud efectiva para d1 (100 px) = 250 mm
    expect(calcularLongitudEfectivaMm(100, 200, 200, 600)).toBeCloseTo(250);
    expect(calcularLongitudEfectivaMm(100, 200, null, null)).toBe(200);
  });
});
