import { useState } from "react";

import type { ClaseHistograma } from "../api/tipos";
import { formatearNumero } from "../utilidades/formato";
import { escalaLineal, marcasLineales } from "./escalas";
import "./graficos.css";

const ANCHO = 640;
const ALTO = 320;
const MARGEN = { izquierda: 52, derecha: 20, arriba: 16, abajo: 44 };
const SEPARACION = 2;
const RADIO = 4;

interface Props {
  clases: ClaseHistograma[];
}

/** Barra con las esquinas superiores redondeadas, apoyada en la línea base. */
function barra(x: number, y: number, ancho: number, alto: number): string {
  const r = Math.min(RADIO, ancho / 2, alto);
  return `M${x},${y + alto} V${y + r} Q${x},${y} ${x + r},${y} H${x + ancho - r} Q${x + ancho},${y} ${x + ancho},${y + r} V${y + alto} Z`;
}

function intervalo(clase: ClaseHistograma): string {
  return `${formatearNumero(clase.limite_inferior_mm, 0)}–${formatearNumero(clase.limite_superior_mm, 0)} mm`;
}

/** Histograma: % retenido en masa por clase de tamaño, con el número de fragmentos al pasar el ratón. */
export function GraficoHistograma({ clases }: Props) {
  const [activa, setActiva] = useState<number | null>(null);
  const maximo = Math.max(...clases.map((c) => c.porcentaje_retenido));
  const marcas = marcasLineales(maximo);
  const y = escalaLineal([0, marcas[marcas.length - 1]], [ALTO - MARGEN.abajo, MARGEN.arriba]);
  const anchoUtil = ANCHO - MARGEN.izquierda - MARGEN.derecha;
  const anchoClase = anchoUtil / clases.length;
  const mostrarCada = Math.ceil(clases.length / 7);

  const clase = activa === null ? null : clases[activa];

  return (
    <figure className="grafico">
      <svg
        className="grafico__svg"
        viewBox={`0 0 ${ANCHO} ${ALTO}`}
        role="img"
        aria-label="Histograma: porcentaje retenido en masa por clase de tamaño"
      >
        {marcas.map((valor) => (
          <g key={`y-${valor}`}>
            <line className="grafico__rejilla" x1={MARGEN.izquierda} x2={ANCHO - MARGEN.derecha} y1={y(valor)} y2={y(valor)} />
            <text className="grafico__marca" x={MARGEN.izquierda - 8} y={y(valor)} textAnchor="end" dominantBaseline="middle">
              {formatearNumero(valor, 1)}
            </text>
          </g>
        ))}

        {clases.map((c, i) => {
          const x0 = MARGEN.izquierda + i * anchoClase + SEPARACION / 2;
          const alto = y(0) - y(c.porcentaje_retenido);
          return (
            <g key={i} onMouseEnter={() => setActiva(i)} onMouseLeave={() => setActiva(null)}>
              <rect className="grafico__zona" x={x0} y={MARGEN.arriba} width={anchoClase} height={y(0) - MARGEN.arriba} />
              {alto > 0 && (
                <path
                  className={`grafico__barra${activa === i ? " grafico__barra--activa" : ""}`}
                  d={barra(x0, y(c.porcentaje_retenido), anchoClase - SEPARACION, alto)}
                />
              )}
              {i % mostrarCada === 0 && (
                <text className="grafico__marca" x={x0} y={ALTO - MARGEN.abajo + 16} textAnchor="middle">
                  {formatearNumero(c.limite_inferior_mm, 0)}
                </text>
              )}
            </g>
          );
        })}
        <text className="grafico__marca" x={ANCHO - MARGEN.derecha} y={ALTO - MARGEN.abajo + 16} textAnchor="middle">
          {formatearNumero(clases[clases.length - 1].limite_superior_mm, 0)}
        </text>

        <line className="grafico__eje" x1={MARGEN.izquierda} x2={ANCHO - MARGEN.derecha} y1={y(0)} y2={y(0)} />
        <text className="grafico__titulo-eje" x={(ANCHO + MARGEN.izquierda) / 2} y={ALTO - 6} textAnchor="middle">
          Tamaño (mm)
        </text>
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
          <strong>{intervalo(clase)}</strong>
          <span>{formatearNumero(clase.porcentaje_retenido, 1)} % en masa</span>
          <span>{clase.numero_fragmentos} fragmentos</span>
        </div>
      )}
    </figure>
  );
}
