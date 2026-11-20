import { describe, expect, it } from "vitest";

import { aMilimetros, avisoLongitud } from "./longitud";

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
