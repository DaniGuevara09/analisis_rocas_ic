import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { RangoTamano } from "../api/tipos";
import { LeyendaRangos, textoRango } from "./LeyendaRangos";

const RANGOS: RangoTamano[] = [
  { indice: 0, limite_inferior_mm: 0, limite_superior_mm: 100 },
  { indice: 1, limite_inferior_mm: 100, limite_superior_mm: 250 },
  { indice: 2, limite_inferior_mm: 250, limite_superior_mm: 400 },
  { indice: 3, limite_inferior_mm: 400, limite_superior_mm: 600 },
  { indice: 4, limite_inferior_mm: 600, limite_superior_mm: null },
];

describe("textoRango", () => {
  it("describe el primero, uno intermedio y el último", () => {
    expect(textoRango(RANGOS[0])).toBe("< 100 mm");
    expect(textoRango(RANGOS[1])).toBe("100–250 mm");
    expect(textoRango(RANGOS[4])).toBe("≥ 600 mm");
  });
});

describe("LeyendaRangos", () => {
  it("muestra cada rango con su conteo de fragmentos", () => {
    render(
      <LeyendaRangos
        rangos={RANGOS}
        fragmentos={[
          { id: "a", diametro_equivalente_mm: 50, indice_rango: 0 },
          { id: "b", diametro_equivalente_mm: 60, indice_rango: 0 },
          { id: "c", diametro_equivalente_mm: 700, indice_rango: 4 },
        ]}
      />,
    );
    const items = screen.getAllByRole("listitem");
    expect(items).toHaveLength(5);
    expect(items[0]).toHaveTextContent("Finos");
    expect(items[0]).toHaveTextContent("2");
    expect(items[4]).toHaveTextContent("Sobretamaño");
    expect(items[4]).toHaveTextContent("1");
  });
});
