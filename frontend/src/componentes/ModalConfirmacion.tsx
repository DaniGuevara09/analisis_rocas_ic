import { useEffect } from "react";

import { Boton } from "./Boton";
import "./ModalConfirmacion.css";

interface Props {
  titulo: string;
  mensaje: string;
  textoConfirmar?: string;
  textoCancelar?: string;
  onConfirmar: () => void;
  onCancelar: () => void;
}

export function ModalConfirmacion({
  titulo,
  mensaje,
  textoConfirmar = "Confirmar",
  textoCancelar = "Cancelar",
  onConfirmar,
  onCancelar,
}: Props) {
  useEffect(() => {
    const alPresionar = (evento: KeyboardEvent) => {
      if (evento.key === "Escape") {
        onCancelar();
      }
    };
    document.addEventListener("keydown", alPresionar);
    return () => document.removeEventListener("keydown", alPresionar);
  }, [onCancelar]);

  return (
    <div className="modal__fondo">
      <div className="modal" role="dialog" aria-modal="true" aria-labelledby="modal-titulo">
        <h2 id="modal-titulo" className="modal__titulo">
          {titulo}
        </h2>
        <p className="modal__mensaje">{mensaje}</p>
        <div className="modal__acciones">
          <Boton variante="secundario" onClick={onCancelar}>
            {textoCancelar}
          </Boton>
          <Boton variante="peligro" onClick={onConfirmar}>
            {textoConfirmar}
          </Boton>
        </div>
      </div>
    </div>
  );
}
