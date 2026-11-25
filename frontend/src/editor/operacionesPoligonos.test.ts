import { describe, expect, it } from "vitest";

import type { Punto } from "../api/tipos";
import {
  AREA_MINIMA_FRAGMENTO_PX2,
  areaPoligono,
  cercaDe,
  contienePunto,
  dividirConTrazo,
  dividirPoligono,
  esDiminuto,
  insertarPuntoEnBorde,
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

describe("esDiminuto", () => {
  it("marca como diminutos los contornos de menos de 1 px²", () => {
    expect(esDiminuto(cuadrado(0, 0, 0.5))).toBe(true); // 0.25 px²
    expect(esDiminuto(cuadrado(0, 0, 1))).toBe(false); // 1 px²
    expect(AREA_MINIMA_FRAGMENTO_PX2).toBe(1);
  });
});

describe("dividirConTrazo (línea quebrada)", () => {
  it("un corte en L separa una esquina del cuadrado", () => {
    // Entra por arriba en x = 4, baja hasta y = 4 y sale por la derecha.
    const trazo = [
      { x: 4, y: -2 },
      { x: 4, y: 4 },
      { x: 12, y: 4 },
    ];
    const partes = dividirConTrazo(cuadrado(0, 0, 10), trazo);
    expect(partes).toHaveLength(2);
    const areas = (partes ?? []).map(areaPoligono).sort((a, b) => a - b);
    expect(areas[0]).toBeCloseTo(24); // 6 × 4
    expect(areas[1]).toBeCloseTo(76);
  });

  it("con dos puntos equivale al corte recto", () => {
    const partes = dividirConTrazo(cuadrado(0, 0, 10), [
      { x: 5, y: -5 },
      { x: 5, y: 15 },
    ]);
    const areas = (partes ?? []).map(areaPoligono).sort((a, b) => a - b);
    expect(areas).toHaveLength(2);
    expect(areas[0]).toBeCloseTo(50);
  });

  it("las piezas suman el área original", () => {
    const trazo = [
      { x: -1, y: 2 },
      { x: 3, y: 6 },
      { x: 7, y: 3 },
      { x: 11, y: 8 },
    ];
    const partes = dividirConTrazo(cuadrado(0, 0, 10), trazo) ?? [];
    expect(partes.length).toBeGreaterThanOrEqual(2);
    expect(partes.map(areaPoligono).reduce((a, b) => a + b, 0)).toBeCloseTo(100);
  });

  it("devuelve null si el trazo no atraviesa el fragmento", () => {
    expect(
      dividirConTrazo(cuadrado(0, 0, 10), [
        { x: 20, y: 0 },
        { x: 25, y: 5 },
        { x: 20, y: 10 },
      ]),
    ).toBeNull();
    expect(dividirConTrazo(cuadrado(0, 0, 10), [{ x: 1, y: 1 }])).toBeNull();
  });
});

describe("insertarPuntoEnBorde", () => {
  it("inserta un punto proyectado en la arista más cercana", () => {
    const base = cuadrado(0, 0, 10);
    // Clic cerca del borde superior (0,0)-(10,0) en x=5, y=0.5
    const resultado = insertarPuntoEnBorde(base, { x: 5, y: 0.5 });
    expect(resultado).toHaveLength(5);
    expect(resultado[1]).toEqual({ x: 5, y: 0 });
  });
});
