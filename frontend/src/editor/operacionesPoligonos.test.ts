import { describe, expect, it } from "vitest";

import type { Punto } from "../api/tipos";
import {
  areaPoligono,
  cercaDe,
  contienePunto,
  dividirPoligono,
  unirPoligonos,
} from "./operacionesPoligonos";

function cuadrado(x: number, y: number, lado: number): Punto[] {
  return [
    { x, y },
    { x: x + lado, y },
    { x: x + lado, y: y + lado },
    { x, y: y + lado },
  ];
}

describe("areaPoligono", () => {
  it("calcula el área de un cuadrado de 10x10 sin importar el sentido", () => {
    expect(areaPoligono(cuadrado(0, 0, 10))).toBeCloseTo(100);
    expect(areaPoligono([...cuadrado(0, 0, 10)].reverse())).toBeCloseTo(100);
  });
});

describe("unirPoligonos", () => {
  it("fusiona dos cuadrados que se solapan en un solo polígono", () => {
    const union = unirPoligonos([cuadrado(0, 0, 10), cuadrado(5, 0, 10)]);
    expect(union).not.toBeNull();
    expect(areaPoligono(union ?? [])).toBeCloseTo(150);
  });

  it("fusiona dos cuadrados que comparten un borde", () => {
    const union = unirPoligonos([cuadrado(0, 0, 10), cuadrado(10, 0, 10)]);
    expect(areaPoligono(union ?? [])).toBeCloseTo(200);
  });

  it("devuelve null si los fragmentos no se tocan", () => {
    expect(unirPoligonos([cuadrado(0, 0, 10), cuadrado(50, 50, 10)])).toBeNull();
  });

  it("devuelve null con menos de dos polígonos", () => {
    expect(unirPoligonos([cuadrado(0, 0, 10)])).toBeNull();
  });

  it("no repite el primer punto al final", () => {
    const union = unirPoligonos([cuadrado(0, 0, 10), cuadrado(5, 0, 10)]) ?? [];
    expect(union[0]).not.toEqual(union[union.length - 1]);
  });
});

describe("dividirPoligono", () => {
  it("una línea vertical parte un cuadrado en dos mitades", () => {
    const partes = dividirPoligono(cuadrado(0, 0, 10), { x: 5, y: -5 }, { x: 5, y: 15 });
    expect(partes).toHaveLength(2);
    const areas = (partes ?? []).map(areaPoligono).sort((a, b) => a - b);
    expect(areas[0]).toBeCloseTo(50);
    expect(areas[1]).toBeCloseTo(50);
  });

  it("la línea puede ser más corta que el polígono: se prolonga", () => {
    const partes = dividirPoligono(cuadrado(0, 0, 10), { x: 2, y: 4 }, { x: 2, y: 6 });
    const areas = (partes ?? []).map(areaPoligono).sort((a, b) => a - b);
    expect(areas[0]).toBeCloseTo(20);
    expect(areas[1]).toBeCloseTo(80);
  });

  it("devuelve null si la línea no cruza el polígono", () => {
    expect(dividirPoligono(cuadrado(0, 0, 10), { x: 20, y: 0 }, { x: 20, y: 10 })).toBeNull();
  });

  it("devuelve null si los dos puntos coinciden", () => {
    expect(dividirPoligono(cuadrado(0, 0, 10), { x: 5, y: 5 }, { x: 5, y: 5 })).toBeNull();
  });

  it("en un polígono en U una línea horizontal produce tres partes", () => {
    const u: Punto[] = [
      { x: 0, y: 0 },
      { x: 30, y: 0 },
      { x: 30, y: 30 },
      { x: 20, y: 30 },
      { x: 20, y: 10 },
      { x: 10, y: 10 },
      { x: 10, y: 30 },
      { x: 0, y: 30 },
    ];
    const partes = dividirPoligono(u, { x: -5, y: 20 }, { x: 35, y: 20 });
    expect(partes).toHaveLength(3);
    const total = (partes ?? []).reduce((suma, p) => suma + areaPoligono(p), 0);
    expect(total).toBeCloseTo(areaPoligono(u));
  });
});

describe("cercaDe", () => {
  it("detecta puntos dentro del radio", () => {
    expect(cercaDe({ x: 0, y: 0 }, { x: 3, y: 4 }, 5)).toBe(true);
    expect(cercaDe({ x: 0, y: 0 }, { x: 3, y: 4 }, 4.9)).toBe(false);
  });
});

describe("contienePunto", () => {
  it("distingue puntos interiores y exteriores", () => {
    expect(contienePunto(cuadrado(0, 0, 10), { x: 5, y: 5 })).toBe(true);
    expect(contienePunto(cuadrado(0, 0, 10), { x: 15, y: 5 })).toBe(false);
  });
});
