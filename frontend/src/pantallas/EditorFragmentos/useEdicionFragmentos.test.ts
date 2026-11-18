import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as api from "../../api/analisis";
import type { AnalisisDetalle, Fragmento, Resultados } from "../../api/tipos";
import { aSolicitud, useEdicionFragmentos } from "./useEdicionFragmentos";

vi.mock("../../api/analisis");

function fragmento(id: string): Fragmento {
  return {
    id,
    poligono: [
      { x: 0, y: 0 },
      { x: 10, y: 0 },
      { x: 10, y: 10 },
    ],
    origen: "MODELO",
    diametro_equivalente_mm: 5,
  };
}

const DETALLE = {
  id: "x",
  nombre: "pila",
  fecha_creacion: "2026-01-01T00:00:00Z",
  estado: "SEGMENTADO",
  numero_fragmentos: 3,
  imagen: { url: "/i", ancho_px: 100, alto_px: 100, formato: "JPG" },
  calibracion: null,
  region_excluida: null,
  fragmentos: [fragmento("a"), fragmento("b"), fragmento("c")],
} satisfies AnalisisDetalle;

const RESULTADOS = { d50: 10 } as Resultados;

describe("useEdicionFragmentos", () => {
  beforeEach(() => {
    vi.mocked(api.obtenerAnalisis).mockResolvedValue(DETALLE);
    vi.mocked(api.obtenerResultados).mockResolvedValue(RESULTADOS);
  });

  it("carga los fragmentos y pide los resultados", async () => {
    const { result } = renderHook(() => useEdicionFragmentos("x"));
    await waitFor(() => expect(result.current.resultados).toBe(RESULTADOS));
    expect(result.current.fragmentos).toHaveLength(3);
  });

  it("guarda una edición, refresca y permite deshacerla", async () => {
    vi.mocked(api.guardarFragmentos).mockImplementation(async (_id, lista) =>
      lista.map((f) => ({ ...fragmento(f.id ?? "nuevo"), poligono: f.poligono })),
    );
    const { result } = renderHook(() => useEdicionFragmentos("x"));
    await waitFor(() => expect(result.current.fragmentos).toHaveLength(3));

    await act(async () => {
      await result.current.aplicar(DETALLE.fragmentos.slice(0, 2).map(aSolicitud));
    });
    expect(result.current.fragmentos).toHaveLength(2);
    expect(result.current.puedeDeshacer).toBe(true);
    // Con menos de 3 fragmentos no se piden resultados.
    expect(result.current.resultados).toBeNull();

    await act(async () => {
      await result.current.deshacer();
    });
    expect(result.current.fragmentos).toHaveLength(3);
    expect(result.current.puedeDeshacer).toBe(false);
  });

  it("si falla el guardado conserva la lista y muestra el error", async () => {
    vi.mocked(api.guardarFragmentos).mockRejectedValue(new Error("x"));
    const { result } = renderHook(() => useEdicionFragmentos("x"));
    await waitFor(() => expect(result.current.fragmentos).toHaveLength(3));
    await act(async () => {
      await result.current.aplicar([]);
    });
    expect(result.current.fragmentos).toHaveLength(3);
    expect(result.current.estadoGuardado).toBe("error");
    expect(result.current.error).not.toBe("");
  });
});
