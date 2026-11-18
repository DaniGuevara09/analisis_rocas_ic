import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ModalConfirmacion } from "./ModalConfirmacion";

function montar() {
  const onConfirmar = vi.fn();
  const onCancelar = vi.fn();
  render(
    <ModalConfirmacion
      titulo="Eliminar análisis"
      mensaje="¿Seguro?"
      textoConfirmar="Eliminar"
      onConfirmar={onConfirmar}
      onCancelar={onCancelar}
    />,
  );
  return { onConfirmar, onCancelar };
}

describe("ModalConfirmacion", () => {
  it("muestra título y mensaje", () => {
    montar();
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByText("Eliminar análisis")).toBeInTheDocument();
    expect(screen.getByText("¿Seguro?")).toBeInTheDocument();
  });

  it("confirmar llama solo a onConfirmar", () => {
    const { onConfirmar, onCancelar } = montar();
    fireEvent.click(screen.getByRole("button", { name: "Eliminar" }));
    expect(onConfirmar).toHaveBeenCalledTimes(1);
    expect(onCancelar).not.toHaveBeenCalled();
  });

  it("cancelar llama solo a onCancelar", () => {
    const { onConfirmar, onCancelar } = montar();
    fireEvent.click(screen.getByRole("button", { name: "Cancelar" }));
    expect(onCancelar).toHaveBeenCalledTimes(1);
    expect(onConfirmar).not.toHaveBeenCalled();
  });

  it("Escape cancela", () => {
    const { onCancelar } = montar();
    fireEvent.keyDown(document, { key: "Escape" });
    expect(onCancelar).toHaveBeenCalledTimes(1);
  });
});
