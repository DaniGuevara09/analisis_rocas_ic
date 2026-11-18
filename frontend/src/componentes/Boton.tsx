import type { ButtonHTMLAttributes } from "react";

import "./Boton.css";

export type VarianteBoton = "primario" | "secundario" | "peligro";

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variante?: VarianteBoton;
}

export function Boton({ variante = "primario", type = "button", className, ...resto }: Props) {
  const clases = ["boton", `boton--${variante}`, className].filter(Boolean).join(" ");
  return <button type={type} className={clases} {...resto} />;
}
