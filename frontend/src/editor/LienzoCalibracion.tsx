import type { KonvaEventObject } from "konva/lib/Node";
import { useEffect, useMemo, useRef, useState } from "react";
import { Circle, Image as ImagenKonva, Layer, Line, Stage } from "react-konva";

import type { Punto } from "../api/tipos";
import { leerEstiloTrazos } from "../tema/leerTokens";
import { aImagen, aPantalla, aplanar, escalaAjuste, limitar } from "./geometria";
import { useImagen } from "./useImagen";
import "./LienzoCalibracion.css";

interface Props {
  urlImagen: string;
  anchoImg: number;
  altoImg: number;
  /** Extremos de la línea de calibración (0, 1 o 2 puntos), en píxeles de la imagen original. */
  linea: Punto[];
  /** Vértices de la región excluida, en píxeles de la imagen original. */
  region: Punto[];
  regionCerrada: boolean;
  /** Si el lienzo debe reaccionar a los clics para agregar puntos. */
  aceptaClics: boolean;
  onClicImagen: (punto: Punto) => void;
  onMoverExtremo: (indice: number, punto: Punto) => void;
}

/** Lienzo Konva: la imagen se ajusta al espacio, pero todo punto se informa en píxeles originales. */
export function LienzoCalibracion({
  urlImagen,
  anchoImg,
  altoImg,
  linea,
  region,
  regionCerrada,
  aceptaClics,
  onClicImagen,
  onMoverExtremo,
}: Props) {
  const contenedor = useRef<HTMLDivElement>(null);
  const [espacio, setEspacio] = useState({ ancho: 0, alto: 0 });
  const imagen = useImagen(urlImagen);
  const estilo = useMemo(() => leerEstiloTrazos(), []);

  useEffect(() => {
    const elemento = contenedor.current;
    if (!elemento) {
      return;
    }
    const medir = () => setEspacio({ ancho: elemento.clientWidth, alto: elemento.clientHeight });
    medir();
    const observador = new ResizeObserver(medir);
    observador.observe(elemento);
    return () => observador.disconnect();
  }, []);

  const escala = espacio.ancho > 0 ? escalaAjuste(anchoImg, altoImg, espacio.ancho, espacio.alto) : 0;
  const ancho = anchoImg * escala;
  const alto = altoImg * escala;

  const alHacerClic = (evento: KonvaEventObject<MouseEvent | TouchEvent>) => {
    const posicion = evento.target.getStage()?.getPointerPosition();
    if (aceptaClics && posicion) {
      onClicImagen(aImagen(posicion, escala));
    }
  };

  return (
    <div ref={contenedor} className="lienzo">
      {escala > 0 && (
        <Stage
          width={ancho}
          height={alto}
          onClick={alHacerClic}
          onTap={alHacerClic}
          className={aceptaClics ? "lienzo__escenario lienzo__escenario--activo" : "lienzo__escenario"}
        >
          <Layer>
            {imagen && <ImagenKonva image={imagen} width={ancho} height={alto} listening={false} />}

            {region.length > 0 && (
              <Line
                points={aplanar(region.map((p) => aPantalla(p, escala)))}
                closed={regionCerrada}
                stroke={estilo.colorRegion}
                strokeWidth={estilo.grosor}
                dash={estilo.punteado}
                fill={regionCerrada ? estilo.rellenoRegion : undefined}
                listening={false}
              />
            )}
            {region.map((vertice, indice) => {
              const p = aPantalla(vertice, escala);
              return (
                <Circle
                  key={`region-${indice}`}
                  x={p.x}
                  y={p.y}
                  radius={estilo.radioVertice}
                  fill={estilo.colorVertice}
                  stroke={estilo.colorRegion}
                  strokeWidth={estilo.grosor}
                  listening={false}
                />
              );
            })}

            {linea.length === 2 && (
              <Line
                points={aplanar(linea.map((p) => aPantalla(p, escala)))}
                stroke={estilo.colorCalibracion}
                strokeWidth={estilo.grosor}
                listening={false}
              />
            )}
            {linea.map((extremo, indice) => {
              const p = aPantalla(extremo, escala);
              return (
                <Circle
                  key={`extremo-${indice}`}
                  x={p.x}
                  y={p.y}
                  radius={estilo.radioVertice}
                  fill={estilo.colorVertice}
                  stroke={estilo.colorCalibracion}
                  strokeWidth={estilo.grosor}
                  draggable
                  dragBoundFunc={(pos) => ({
                    x: limitar(pos.x, 0, ancho),
                    y: limitar(pos.y, 0, alto),
                  })}
                  onDragMove={(e) =>
                    onMoverExtremo(indice, aImagen({ x: e.target.x(), y: e.target.y() }, escala))
                  }
                />
              );
            })}
          </Layer>
        </Stage>
      )}
    </div>
  );
}
