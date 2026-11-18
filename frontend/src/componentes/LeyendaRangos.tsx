import type { FragmentoMedido, RangoTamano } from "../api/tipos";
import { formatearNumero } from "../utilidades/formato";
import "./LeyendaRangos.css";

const NOMBRES = ["Finos", "Pequeños", "Medianos", "Gruesos", "Sobretamaño"];

/** Texto del intervalo de un rango, p. ej. "< 120 mm", "120–340 mm" o "> 900 mm". */
export function textoRango(rango: RangoTamano): string {
  if (rango.limite_inferior_mm <= 0 && rango.limite_superior_mm !== null) {
    return `< ${formatearNumero(rango.limite_superior_mm, 0)} mm`;
  }
  if (rango.limite_superior_mm === null) {
    return `≥ ${formatearNumero(rango.limite_inferior_mm, 0)} mm`;
  }
  return `${formatearNumero(rango.limite_inferior_mm, 0)}–${formatearNumero(rango.limite_superior_mm, 0)} mm`;
}

const ETIQUETAS_DX = ["< D20", "D20–D50", "D50–D80", "D80–D90", "≥ D90"];

interface Props {
  rangos: RangoTamano[];
  fragmentos: FragmentoMedido[];
}

/** Leyenda de colores por rango de tamaño con el conteo de fragmentos de cada uno (RF-06). */
export function LeyendaRangos({ rangos, fragmentos }: Props) {
  return (
    <ul className="leyenda-rangos" aria-label="Rangos de tamaño">
      {rangos.map((rango) => {
        const cantidad = fragmentos.filter((f) => f.indice_rango === rango.indice).length;
        return (
          <li key={rango.indice} className="leyenda-rangos__item">
            <span className={`leyenda-rangos__muestra leyenda-rangos__muestra--${rango.indice}`} />
            <span className="leyenda-rangos__nombre">
              {NOMBRES[rango.indice] ?? `Rango ${rango.indice + 1}`}{" "}
              <span className="leyenda-rangos__dx">({ETIQUETAS_DX[rango.indice]})</span>
            </span>
            <span className="leyenda-rangos__intervalo">{textoRango(rango)}</span>
            <span className="leyenda-rangos__cantidad">{cantidad}</span>
          </li>
        );
      })}
    </ul>
  );
}
