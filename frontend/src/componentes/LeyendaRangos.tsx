import type { FragmentoMedido, RangoTamano } from "../api/tipos";
import { formatearNumero } from "../utilidades/formato";
import "./LeyendaRangos.css";

/** Texto del intervalo de un rango, p. ej. "< 120 mm", "120–340 mm" o "≥ 900 mm". */
export function textoRango(rango: RangoTamano): string {
  if (rango.limite_inferior_mm <= 0 && rango.limite_superior_mm !== null) {
    return `< ${formatearNumero(rango.limite_superior_mm, 0)} mm`;
  }
  if (rango.limite_superior_mm === null) {
    return `≥ ${formatearNumero(rango.limite_inferior_mm, 0)} mm`;
  }
  return `${formatearNumero(rango.limite_inferior_mm, 0)}–${formatearNumero(rango.limite_superior_mm, 0)} mm`;
}

/** Color de cada fragmento según su rango (para el lienzo y la vista de resultados). */
export function colorPorFragmento(rangos: RangoTamano[], fragmentos: FragmentoMedido[]): Map<string, string> {
  return new Map(fragmentos.map((f) => [f.id, rangos[f.indice_rango]?.color ?? ""]));
}

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
            <span className="leyenda-rangos__muestra" style={{ background: rango.color }} />
            <span className="leyenda-rangos__nombre">{rango.nombre}</span>
            <span className="leyenda-rangos__intervalo">{textoRango(rango)}</span>
            <span className="leyenda-rangos__cantidad">{cantidad}</span>
          </li>
        );
      })}
    </ul>
  );
}
