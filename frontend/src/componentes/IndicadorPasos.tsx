import "./IndicadorPasos.css";

export const PASOS = ["Cargar", "Calibrar y excluir", "Segmentar y editar", "Resultados"] as const;

interface Props {
  /** Índice (0 a 3) del paso actual. */
  actual: number;
}

export function IndicadorPasos({ actual }: Props) {
  return (
    <ol className="pasos" aria-label="Progreso del análisis">
      {PASOS.map((nombre, indice) => {
        const modificador = indice === actual ? "actual" : indice < actual ? "hecho" : "pendiente";
        return (
          <li
            key={nombre}
            className={`pasos__paso pasos__paso--${modificador}`}
            aria-current={indice === actual ? "step" : undefined}
          >
            <span className="pasos__numero">{indice + 1}</span>
            <span className="pasos__nombre">{nombre}</span>
          </li>
        );
      })}
    </ol>
  );
}
