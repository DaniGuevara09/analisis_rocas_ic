import type { EstadoAnalisis } from "../api/tipos";
import "./EtiquetaEstado.css";

const TEXTOS: Record<EstadoAnalisis, string> = {
  IMAGEN_CARGADA: "Imagen cargada",
  CALIBRADO: "Calibrado",
  SEGMENTADO: "Segmentado",
};

export function EtiquetaEstado({ estado }: { estado: EstadoAnalisis }) {
  return <span className={`etiqueta-estado etiqueta-estado--${estado.toLowerCase()}`}>{TEXTOS[estado]}</span>;
}
