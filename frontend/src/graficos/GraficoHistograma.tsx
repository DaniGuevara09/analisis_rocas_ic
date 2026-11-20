import { useState } from "react";

import type { ClaseHistograma, RangoTamano } from "../api/tipos";
import { textoRango } from "../componentes/LeyendaRangos";
import { formatearNumero } from "../utilidades/formato";
import { escalaLineal, marcasLineales } from "./escalas";
import "./graficos.css";

const ANCHO = 640;
const ALTO = 320;
const MARGEN = { izquierda: 52, derecha: 20, arriba: 16, abajo: 58 };
const SEPARACION = 12;
const RADIO = 4;

interface Props {
  /** Una clase por rango de tamaño, en el mismo orden que `rangos`. */
  clases: ClaseHistograma[];
  rangos: RangoTamano[];
}

/** Barra con las esquinas superiores redondeadas, apoyada en la línea base. */
function barra(x: number, y: number, ancho: number, alto: number): string {
  const r = Math.min(RADIO, ancho / 2, alto);
  return `M${x},${y + alto} V${y + r} Q${x},${y} ${x + r},${y} H${x + ancho - r} Q${x + ancho},${y} ${x + ancho},${y + r} V${y + alto} Z`;
}

/**
 * Histograma: % retenido en masa por rango de tamaño. Las barras son los mismos rangos y
 * colores de la leyenda; al pasar el ratón se ve el número de fragmentos.
 */
export function GraficoHistograma({ clases, rangos }: Props) {
  const [activa, setActiva] = useState<number | null>(null);
  const maximo = Math.max(...clases.map((c) => c.porcentaje_retenido));
  const marcas = marcasLineales(maximo);
  const y = escalaLineal([0, marcas[marcas.length - 1]], [ALTO - MARGEN.abajo, MARGEN.arriba]);
  const anchoClase = (ANCHO - MARGEN.izquierda - MARGEN.derecha) / clases.length;

  const clase = activa === null ? null : clases[activa];

  return (
    <figure className="grafico">
      <svg
        className="grafico__svg"
        viewBox={`0 0 ${ANCHO} ${ALTO}`}
        role="img"
        aria-label="Histograma: porcentaje retenido en masa por rango de tamaño"
      >
        {marcas.map((valor) => (
          <g key={`y-${valor}`}>
            <line className="grafico__rejilla" x1={MARGEN.izquierda} x2={ANCHO - MARGEN.derecha} y1={y(valor)} y2={y(valor)} />
            <text className="grafico__marca" x={MARGEN.izquierda - 8} y={y(valor)} textAnchor="end" dominantBaseline="middle">
              {formatearNumero(valor, 0)}
            </text>
          </g>
        ))}

        {clases.map((c, i) => {
          const rango = rangos[i];
          const x0 = MARGEN.izquierda + i * anchoClase;
          const centro = x0 + anchoClase / 2;
          const alto = y(0) - y(c.porcentaje_retenido);
          return (
            <g key={i} onMouseEnter={() => setActiva(i)} onMouseLeave={() => setActiva(null)}>
              <rect className="grafico__zona" x={x0} y={MARGEN.arriba} width={anchoClase} height={y(0) - MARGEN.arriba} />
              {alto > 0 && (
                <path
                  className={`grafico__barra grafico__barra--rango${activa === i ? " grafico__barra--activa" : ""}`}
                  style={rango ? { fill: rango.color } : undefined}
                  d={barra(x0 + SEPARACION / 2, y(c.porcentaje_retenido), anchoClase - SEPARACION, alto)}
                />
              )}
              <text className="grafico__etiqueta" x={centro} y={y(c.porcentaje_retenido) - 6} textAnchor="middle">
                {formatearNumero(c.porcentaje_retenido, 0)} %
              </text>
              <text className="grafico__marca grafico__marca--fuerte" x={centro} y={ALTO - MARGEN.abajo + 16} textAnchor="middle">
                {rango?.nombre ?? ""}
              </text>
              <text className="grafico__marca" x={centro} y={ALTO - MARGEN.abajo + 31} textAnchor="middle">
                {rango ? textoRango(rango) : ""}
              </text>
            </g>
          );
        })}

        <line className="grafico__eje" x1={MARGEN.izquierda} x2={ANCHO - MARGEN.derecha} y1={y(0)} y2={y(0)} />
        <text
          className="grafico__titulo-eje"
          transform={`translate(14 ${(ALTO - MARGEN.abajo + MARGEN.arriba) / 2}) rotate(-90)`}
          textAnchor="middle"
        >
          % retenido (masa)
        </text>
      </svg>
      {clase !== null && activa !== null && (
        <div
          className="grafico__tooltip"
          style={{
            left: `${((MARGEN.izquierda + (activa + 0.5) * anchoClase) / ANCHO) * 100}%`,
            top: `${(y(clase.porcentaje_retenido) / ALTO) * 100}%`,
          }}
        >
          <strong>{rangos[activa] ? `${rangos[activa].nombre} · ${textoRango(rangos[activa])}` : ""}</strong>
          <span>{formatearNumero(clase.porcentaje_retenido, 1)} % en masa</span>
          <span>{clase.numero_fragmentos} fragmentos</span>
        </div>
      )}
    </figure>
  );
}
