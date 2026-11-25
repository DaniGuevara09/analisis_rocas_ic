import "./IndicadorPasos.css";

export const PASOS = [
  "Carga de imagen",
  "Calibración de escala",
  "Segmentación y corrección",
  "Resultados",
] as const;

const ESTADOS = { hecho: "Completada", actual: "En curso", pendiente: "Pendiente" } as const;

interface Props {
  /** Índice (0 a 3) del paso actual. */
  actual: number;
}

export function IndicadorPasos({ actual }: Props) {
  return (
    <ol className="pasos" aria-label="Etapas del análisis">
      {PASOS.map((nombre, indice) => {
        const modificador = indice === actual ? "actual" : indice < actual ? "hecho" : "pendiente";
        return (
          <li
            key={nombre}
            className={`pasos__paso pasos__paso--${modificador}`}
            aria-current={indice === actual ? "step" : undefined}
          >
            <span className="pasos__barra" />
            <span className="pasos__estado">
              <span className="cifra">{String(indice + 1).padStart(2, "0")}</span> · {ESTADOS[modificador]}
            </span>
            <span className="pasos__nombre">{nombre}</span>
          </li>
        );
      })}
    </ol>
  );
}
