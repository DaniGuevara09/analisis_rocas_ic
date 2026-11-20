import { type MouseEvent, useState } from "react";

import type { PuntoCurva } from "../api/tipos";
import { formatearMm, formatearNumero } from "../utilidades/formato";
import { dominioLog, escalaLineal, escalaLog, indiceMasCercano, marcasLog } from "./escalas";
import "./graficos.css";

const ANCHO = 640;
const ALTO = 320;
const MARGEN = { izquierda: 52, derecha: 20, arriba: 16, abajo: 44 };
const MARCAS_Y = [0, 20, 40, 60, 80, 100];

export interface Referencia {
  etiqueta: string;
  diametro_mm: number;
  pasante_pct: number;
}

interface Props {
  curva: PuntoCurva[];
  /** Curva de Rosin-Rammler ajustada (calculada en la API), en línea punteada. */
  curvaTeorica?: PuntoCurva[];
  /** Puntos a señalar con guías y etiqueta directa (p. ej. D50 y D80). */
  referencias: Referencia[];
}

/** Curva granulométrica: % pasante acumulado contra tamaño (eje x logarítmico). */
export function GraficoCurva({ curva, curvaTeorica = [], referencias }: Props) {
  const [activo, setActivo] = useState<number | null>(null);
  const diametros = curva.map((p) => p.diametro_mm);
  const dominio = dominioLog(Math.min(...diametros), Math.max(...diametros));
  const x = escalaLog(dominio, [MARGEN.izquierda, ANCHO - MARGEN.derecha]);
  const y = escalaLineal([0, 100], [ALTO - MARGEN.abajo, MARGEN.arriba]);

  const trazar = (puntos: PuntoCurva[]) =>
    puntos
      .map((p, i) => `${i === 0 ? "M" : "L"}${x(p.diametro_mm).toFixed(1)},${y(p.pasante_pct).toFixed(1)}`)
      .join(" ");
  const trazo = trazar(curva);

  const alMover = (evento: MouseEvent<SVGRectElement>) => {
    const caja = evento.currentTarget.ownerSVGElement?.getBoundingClientRect();
    if (!caja) {
      return;
    }
    const xSvg = ((evento.clientX - caja.left) / caja.width) * ANCHO;
    setActivo(indiceMasCercano(curva.map((p) => x(p.diametro_mm)), xSvg));
  };

  const punto = activo === null ? null : curva[activo];

  return (
    <figure className="grafico">
      <svg
        className="grafico__svg"
        viewBox={`0 0 ${ANCHO} ${ALTO}`}
        role="img"
        aria-label="Curva granulométrica: porcentaje pasante acumulado según el tamaño"
      >
        {MARCAS_Y.map((valor) => (
          <g key={`y-${valor}`}>
            <line className="grafico__rejilla" x1={MARGEN.izquierda} x2={ANCHO - MARGEN.derecha} y1={y(valor)} y2={y(valor)} />
            <text className="grafico__marca" x={MARGEN.izquierda - 8} y={y(valor)} textAnchor="end" dominantBaseline="middle">
              {valor}
            </text>
          </g>
        ))}
        {marcasLog(dominio).map((valor) => (
          <g key={`x-${valor}`}>
            <line className="grafico__rejilla" x1={x(valor)} x2={x(valor)} y1={MARGEN.arriba} y2={ALTO - MARGEN.abajo} />
            <text className="grafico__marca" x={x(valor)} y={ALTO - MARGEN.abajo + 16} textAnchor="middle">
              {formatearNumero(valor, 0)}
            </text>
          </g>
        ))}
        <line className="grafico__eje" x1={MARGEN.izquierda} x2={ANCHO - MARGEN.derecha} y1={y(0)} y2={y(0)} />
        <text className="grafico__titulo-eje" x={(ANCHO + MARGEN.izquierda) / 2} y={ALTO - 6} textAnchor="middle">
          Tamaño (mm, escala logarítmica)
        </text>
        <text
          className="grafico__titulo-eje"
          transform={`translate(14 ${(ALTO - MARGEN.abajo + MARGEN.arriba) / 2}) rotate(-90)`}
          textAnchor="middle"
        >
          % pasante
        </text>

        {referencias.map((r) => (
          <g key={r.etiqueta}>
            <line className="grafico__referencia" x1={x(r.diametro_mm)} x2={x(r.diametro_mm)} y1={y(0)} y2={y(r.pasante_pct)} />
            <line className="grafico__referencia" x1={MARGEN.izquierda} x2={x(r.diametro_mm)} y1={y(r.pasante_pct)} y2={y(r.pasante_pct)} />
            <text className="grafico__etiqueta" x={x(r.diametro_mm) + 6} y={y(r.pasante_pct) - 6}>
              {r.etiqueta} = {formatearMm(r.diametro_mm)}
            </text>
          </g>
        ))}

        {curvaTeorica.length > 1 && <path className="grafico__linea grafico__linea--teorica" d={trazar(curvaTeorica)} />}
        <path className="grafico__linea" d={trazo} />

        {punto && (
          <g>
            <line className="grafico__guia" x1={x(punto.diametro_mm)} x2={x(punto.diametro_mm)} y1={MARGEN.arriba} y2={y(0)} />
            <circle className="grafico__marcador" cx={x(punto.diametro_mm)} cy={y(punto.pasante_pct)} r={5} />
          </g>
        )}
        <rect
          className="grafico__zona"
          x={MARGEN.izquierda}
          y={MARGEN.arriba}
          width={ANCHO - MARGEN.izquierda - MARGEN.derecha}
          height={ALTO - MARGEN.arriba - MARGEN.abajo}
          onMouseMove={alMover}
          onMouseLeave={() => setActivo(null)}
        />
      </svg>
      {curvaTeorica.length > 1 && (
        <figcaption className="grafico__leyenda">
          <span className="grafico__serie">
            <span className="grafico__muestra" aria-hidden="true" />
            Medida (fragmentos)
          </span>
          <span className="grafico__serie">
            <span className="grafico__muestra grafico__muestra--teorica" aria-hidden="true" />
            Rosin-Rammler ajustada
          </span>
        </figcaption>
      )}
      {punto && (
        <div
          className="grafico__tooltip"
          style={{ left: `${(x(punto.diametro_mm) / ANCHO) * 100}%`, top: `${(y(punto.pasante_pct) / ALTO) * 100}%` }}
        >
          <strong>{formatearMm(punto.diametro_mm)}</strong>
          <span>{formatearNumero(punto.pasante_pct, 1)} % pasante</span>
        </div>
      )}
    </figure>
  );
}
