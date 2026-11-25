import type { KonvaEventObject } from "konva/lib/Node";
import { useEffect, useMemo, useRef, useState } from "react";
import { Circle, Image as ImagenKonva, Layer, Line, Stage } from "react-konva";

import type { Punto } from "../api/tipos";
import { Icono } from "../componentes/Icono";
import { leerEstiloTrazos } from "../tema/leerTokens";
import { aImagen, aPantalla, aplanar, escalaAjuste, limitar } from "./geometria";
import { useImagen } from "./useImagen";
import "./LienzoCalibracion.css";

const ZOOM_MINIMO = 1;
const ZOOM_MAXIMO = 12;
const FACTOR_RUEDA = 1.15;
const FACTOR_BOTON = 1.5;

interface Vista {
  zoom: number;
  x: number;
  y: number;
}

interface Props {
  urlImagen: string;
  anchoImg: number;
  altoImg: number;
  /** Extremos de la línea de calibración 1 (0, 1 o 2 puntos), en píxeles de la imagen original. */
  linea: Punto[];
  /** Extremos de la línea de calibración 2 opcional (0, 1 o 2 puntos), en píxeles de la imagen original. */
  lineaSecundaria?: Punto[];
  /** Vértices de la región excluida, en píxeles de la imagen original. */
  region: Punto[];
  regionCerrada: boolean;
  /** Si el lienzo debe reaccionar a los clics para agregar puntos. */
  aceptaClics: boolean;
  onClicImagen: (punto: Punto) => void;
  onMoverExtremo: (indice: number, punto: Punto) => void;
  onMoverExtremoSecundario?: (indice: number, punto: Punto) => void;
}

/** Lienzo Konva: la imagen se ajusta al espacio, pero todo punto se informa en píxeles originales. */
export function LienzoCalibracion({
  urlImagen,
  anchoImg,
  altoImg,
  linea,
  lineaSecundaria = [],
  region,
  regionCerrada,
  aceptaClics,
  onClicImagen,
  onMoverExtremo,
  onMoverExtremoSecundario,
}: Props) {
  const contenedor = useRef<HTMLDivElement>(null);
  const [espacio, setEspacio] = useState({ ancho: 0, alto: 0 });
  const [vista, setVista] = useState<Vista>({ zoom: 1, x: 0, y: 0 });
  const arrastrandoEscenarioRef = useRef(false);
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
  const grosor = estilo.grosor / vista.zoom;
  const radio = estilo.radioVertice / vista.zoom;
  const punteado = estilo.punteado.map((d) => d / vista.zoom);
  const centro = { x: ancho / 2, y: alto / 2 };

  const aplicarZoom = (ancla: Punto, factor: number) => {
    setVista((actual) => {
      const zoom = limitar(actual.zoom * factor, ZOOM_MINIMO, ZOOM_MAXIMO);
      if (zoom === ZOOM_MINIMO) {
        return { zoom, x: 0, y: 0 };
      }
      const enImagen = { x: (ancla.x - actual.x) / actual.zoom, y: (ancla.y - actual.y) / actual.zoom };
      return { zoom, x: ancla.x - enImagen.x * zoom, y: ancla.y - enImagen.y * zoom };
    });
  };

  const alGirarRueda = (evento: KonvaEventObject<WheelEvent>) => {
    evento.evt.preventDefault();
    const puntero = evento.target.getStage()?.getPointerPosition();
    if (puntero) {
      aplicarZoom(puntero, evento.evt.deltaY < 0 ? FACTOR_RUEDA : 1 / FACTOR_RUEDA);
    }
  };

  const alHacerClic = (evento: KonvaEventObject<MouseEvent | TouchEvent>) => {
    if (arrastrandoEscenarioRef.current) {
      arrastrandoEscenarioRef.current = false;
      return;
    }
    const relativa = evento.target.getStage()?.getRelativePointerPosition();
    if (aceptaClics && relativa) {
      const punto = aImagen(relativa, escala);
      onClicImagen({ x: limitar(punto.x, 0, anchoImg), y: limitar(punto.y, 0, altoImg) });
    }
  };

  return (
    <div ref={contenedor} className="lienzo">
      {escala > 0 && (
        <Stage
          width={ancho}
          height={alto}
          scaleX={vista.zoom}
          scaleY={vista.zoom}
          x={vista.x}
          y={vista.y}
          draggable={vista.zoom > ZOOM_MINIMO}
          onMouseDown={() => {
            arrastrandoEscenarioRef.current = false;
          }}
          onDragStart={(e) => {
            if (e.target === e.target.getStage()) {
              arrastrandoEscenarioRef.current = true;
            }
          }}
          onDragEnd={(e) => {
            if (e.target === e.target.getStage()) {
              setVista((v) => ({ ...v, x: e.target.x(), y: e.target.y() }));
            }
          }}
          onWheel={alGirarRueda}
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
                strokeWidth={grosor}
                dash={punteado}
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
                  radius={radio}
                  fill={estilo.colorVertice}
                  stroke={estilo.colorRegion}
                  strokeWidth={grosor}
                  listening={false}
                />
              );
            })}

            {linea.length === 2 && (
              <Line
                points={aplanar(linea.map((p) => aPantalla(p, escala)))}
                stroke={estilo.colorCalibracion}
                strokeWidth={grosor}
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
                  radius={radio}
                  fill={estilo.colorVertice}
                  stroke={estilo.colorCalibracion}
                  strokeWidth={grosor}
                  draggable
                  dragBoundFunc={(pos: Punto) => ({
                    x: limitar(pos.x, vista.x, vista.x + ancho * vista.zoom),
                    y: limitar(pos.y, vista.y, vista.y + alto * vista.zoom),
                  })}
                  onDragStart={(e: KonvaEventObject<DragEvent>) => {
                    e.cancelBubble = true;
                  }}
                  onDragMove={(e: KonvaEventObject<DragEvent>) => {
                    e.cancelBubble = true;
                    onMoverExtremo(indice, aImagen({ x: e.target.x(), y: e.target.y() }, escala));
                  }}
                  onDragEnd={(e: KonvaEventObject<DragEvent>) => {
                    e.cancelBubble = true;
                  }}
                />
              );
            })}

            {lineaSecundaria.length === 2 && (
              <Line
                points={aplanar(lineaSecundaria.map((p) => aPantalla(p, escala)))}
                stroke={estilo.colorCalibracionSecundaria}
                strokeWidth={grosor}
                listening={false}
              />
            )}
            {lineaSecundaria.map((extremo, indice) => {
              const p = aPantalla(extremo, escala);
              return (
                <Circle
                  key={`extremo-2-${indice}`}
                  x={p.x}
                  y={p.y}
                  radius={radio}
                  fill={estilo.colorVertice}
                  stroke={estilo.colorCalibracionSecundaria}
                  strokeWidth={grosor}
                  draggable={onMoverExtremoSecundario !== undefined}
                  dragBoundFunc={(pos: Punto) => ({
                    x: limitar(pos.x, vista.x, vista.x + ancho * vista.zoom),
                    y: limitar(pos.y, vista.y, vista.y + alto * vista.zoom),
                  })}
                  onDragStart={(e: KonvaEventObject<DragEvent>) => {
                    e.cancelBubble = true;
                  }}
                  onDragMove={(e: KonvaEventObject<DragEvent>) => {
                    e.cancelBubble = true;
                    onMoverExtremoSecundario?.(
                      indice,
                      aImagen({ x: e.target.x(), y: e.target.y() }, escala),
                    );
                  }}
                  onDragEnd={(e: KonvaEventObject<DragEvent>) => {
                    e.cancelBubble = true;
                  }}
                />
              );
            })}
          </Layer>
        </Stage>
      )}

      {escala > 0 && (
        <div className="lienzo__zoom" role="group" aria-label="Zoom de la imagen">
          <button
            type="button"
            className="lienzo__boton-zoom"
            aria-label="Alejar"
            title="Alejar"
            disabled={vista.zoom <= ZOOM_MINIMO}
            onClick={() => aplicarZoom(centro, 1 / FACTOR_BOTON)}
          >
            <Icono nombre="alejar" />
          </button>
          <span className="lienzo__porcentaje cifra" aria-live="polite">
            {Math.round(vista.zoom * 100)} %
          </span>
          <button
            type="button"
            className="lienzo__boton-zoom"
            aria-label="Acercar"
            title="Acercar"
            disabled={vista.zoom >= ZOOM_MAXIMO}
            onClick={() => aplicarZoom(centro, FACTOR_BOTON)}
          >
            <Icono nombre="acercar" />
          </button>
          <span className="lienzo__separador" />
          <button
            type="button"
            className="lienzo__boton-zoom"
            title="Ver la imagen completa"
            disabled={vista.zoom === ZOOM_MINIMO}
            onClick={() => setVista({ zoom: 1, x: 0, y: 0 })}
          >
            <Icono nombre="ajustar" />
            Ajustar
          </button>
        </div>
      )}
    </div>
  );
}
