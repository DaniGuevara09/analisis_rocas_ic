import { describe, expect, it } from "vitest";

import { formatearFecha, formatearTamano } from "./formato";

describe("formato", () => {
  it("formatea la fecha como dd/mm/aaaa", () => {
    expect(formatearFecha("2026-03-07T12:00:00")).toBe("07/03/2026");
  });

  it("formatea el tamaño en MB y KB", () => {
    expect(formatearTamano(1_721_016)).toBe("1,6 MB");
    expect(formatearTamano(2048)).toBe("2 KB");
  });
});
