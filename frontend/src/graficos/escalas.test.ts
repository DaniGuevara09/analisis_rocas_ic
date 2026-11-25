import { describe, expect, it } from "vitest";

import {
  dominioLog,
  escalaLineal,
  escalaLog,
  indiceMasCercano,
  marcasLineales,
  marcasLog,
} from "./escalas";

describe("escalas", () => {
  it("escalaLineal mapea los extremos y el centro", () => {
    const x = escalaLineal([0, 100], [0, 500]);
    expect(x(0)).toBe(0);
    expect(x(50)).toBe(250);
    expect(x(100)).toBe(500);
  });

  it("escalaLog ubica cada década a la misma distancia", () => {
    const x = escalaLog([1, 100], [0, 200]);
    expect(x(1)).toBeCloseTo(0);
    expect(x(10)).toBeCloseTo(100);
    expect(x(100)).toBeCloseTo(200);
  });

  it("dominioLog redondea a décadas", () => {
    expect(dominioLog(37, 812)).toEqual([10, 1000]);
    expect(dominioLog(100, 100)).toEqual([100, 1000]);
  });

  it("marcasLog usa 1-2-5 por década", () => {
    expect(marcasLog([10, 1000])).toEqual([10, 20, 50, 100, 200, 500, 1000]);
  });

  it("marcasLineales cubre el máximo con pasos redondos", () => {
    expect(marcasLineales(43)).toEqual([0, 10, 20, 30, 40, 50]);
    expect(marcasLineales(100)).toEqual([0, 20, 40, 60, 80, 100]);
  });

  it("indiceMasCercano encuentra el valor más próximo", () => {
    expect(indiceMasCercano([1, 5, 9], 6)).toBe(1);
  });
});
