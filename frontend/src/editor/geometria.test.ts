import { describe, expect, it } from "vitest";

import { aImagen, aPantalla, aplanar, distancia, escalaAjuste, limitar } from "./geometria";

describe("escalaAjuste", () => {
  it("ajusta una imagen de 1600x1200 a un lienzo de 800x800 con escala 0.5", () => {
    expect(escalaAjuste(1600, 1200, 800, 800)).toBe(0.5);
  });

  it("usa el lado más restrictivo (alto)", () => {
    expect(escalaAjuste(1000, 2000, 1000, 500)).toBe(0.25);
  });

  it("amplía cuando la imagen es menor que el lienzo", () => {
    expect(escalaAjuste(400, 300, 800, 800)).toBe(2);
  });
});

describe("conversión pantalla ↔ imagen", () => {
  it("aImagen divide por la escala", () => {
    expect(aImagen({ x: 100, y: 50 }, 0.5)).toEqual({ x: 200, y: 100 });
  });

  it("aPantalla multiplica por la escala", () => {
    expect(aPantalla({ x: 200, y: 100 }, 0.5)).toEqual({ x: 100, y: 50 });
  });

  it("ida y vuelta devuelve el mismo punto", () => {
    const original = { x: 1234.5, y: 678.9 };
    const escala = 800 / 1600;
    const vuelta = aImagen(aPantalla(original, escala), escala);
    expect(vuelta.x).toBeCloseTo(original.x, 9);
    expect(vuelta.y).toBeCloseTo(original.y, 9);
  });

  it("vuelta y ida con una escala que no es potencia de dos", () => {
    const pantalla = { x: 321, y: 123 };
    const escala = 0.37;
    const vuelta = aPantalla(aImagen(pantalla, escala), escala);
    expect(vuelta.x).toBeCloseTo(pantalla.x, 9);
    expect(vuelta.y).toBeCloseTo(pantalla.y, 9);
  });
});

describe("distancia", () => {
  it("entre (0,0) y (300,400) es 500", () => {
    expect(distancia({ x: 0, y: 0 }, { x: 300, y: 400 })).toBe(500);
  });

  it("es simétrica y cero entre puntos iguales", () => {
    expect(distancia({ x: 3, y: 4 }, { x: 0, y: 0 })).toBe(5);
    expect(distancia({ x: 7, y: 7 }, { x: 7, y: 7 })).toBe(0);
  });
});

describe("limitar y aplanar", () => {
  it("limita un valor al rango", () => {
    expect(limitar(-5, 0, 10)).toBe(0);
    expect(limitar(15, 0, 10)).toBe(10);
    expect(limitar(5, 0, 10)).toBe(5);
  });

  it("aplana una lista de puntos", () => {
    expect(aplanar([{ x: 1, y: 2 }, { x: 3, y: 4 }])).toEqual([1, 2, 3, 4]);
  });
});
