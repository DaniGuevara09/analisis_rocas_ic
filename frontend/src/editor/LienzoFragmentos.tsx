import type Konva from "konva";
import type { KonvaEventObject } from "konva/lib/Node";
import { useEffect, useMemo, useRef, useState } from "react";
import { Circle, Image as ImagenKonva, Layer, Line, Stage } from "react-konva";

import type { Fragmento, Punto } from "../api/tipos";
import { conAlfa, leerEstiloFragmentos } from "../tema/leerTokens";
import { aImagen, aPantalla, aplanar, escalaAjuste, limitar } from "./geometria";
import { useImagen } from "./useImagen";
import "./LienzoFragmentos.css";

export type Herramienta = "seleccionar" | "dibujar" | "dividir";

const ZOOM_MINIMO = 1;
const ZOOM_MAXIMO = 12;
const FACTOR_RUEDA = 1.15;

interface Props {
  urlImagen: string;
  anchoImg: number;
  altoImg: number;
  fragmentos: Fragmento[];
  /** Índice de rango de tamaño por id (si ya hay resultados). */
  rangoPorId: Map<string, number>;
  seleccionados: Set<string>;
  regionExcluida: Punto[] | null;
  herramienta: Herramienta;
  /** Vértices del fragmento que se dibuja o extremos de la línea de división (px de la imagen). */
  trazo: Punto[];
  mostrarContornos: boolean;
  /** Texto de la etiqueta flotante al pasar el ratón sobre un fragmento. */
  etiquetaFragmento: (id: string) => string;
  onClicFragmento: (id: string, aditivo: boolean) => void;
  onClicImagen: (punto: Punto) => void;
  onCerrarTrazo: () => void;
}

interface Vista {
  zoom: number;
  x: number;
  y: number;
}

interface Etiqueta {
  texto: string;
  x: number;
  y: number;
}

/** Lienzo del editor: zoom con la rueda, arrastre para moverse y coordenadas en px originales. */
export function LienzoFragmentos({
  urlImagen,
  anchoImg,
  altoImg,
  fragmentos,
  rangoPorId,
  seleccionados,
  regionExcluida,
  herramienta,
  trazo,
  mostrarContornos,
  etiquetaFragmento,
  onClicFragmento,
  onClicImagen,
  onCerrarTrazo,
}: Props) {
  const contenedor = useRef<HTMLDivElement>(null);
  const [espacio, setEspacio] = useState({ ancho: 0, alto: 0 });
  const [vista, setVista] = useState<Vista>({ zoom: 1, x: 0, y: 0 });
  const [etiqueta, setEtiqueta] = useState<Etiqueta | null>(null);
  const imagen = useImagen(urlImagen);
  const estilo = useMemo(() => leerEstiloFragmentos(), []);

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

  const ajuste = espacio.ancho > 0 ? escalaAjuste(anchoImg, altoImg, espacio.ancho, espacio.alto) : 0;
  const ancho = anchoImg * ajuste;
  const alto = altoImg * ajuste;
  const editando = herramienta !== "seleccionar";

  const posicionEnImagen = (stage: Konva.Stage | null): Punto | null => {
    const relativa = stage?.getRelativePointerPosition();
    if (!relativa) {
      return null;
    }
    const punto = aImagen(relativa, ajuste);
    return { x: limitar(punto.x, 0, anchoImg), y: limitar(punto.y, 0, altoImg) };
  };

  const alHacerClic = (evento: KonvaEventObject<MouseEvent | TouchEvent>) => {
    const punto = posicionEnImagen(evento.target.getStage());
    if (punto) {
      onClicImagen(punto);
    }
  };

  const alGirarRueda = (evento: KonvaEventObject<WheelEvent>) => {
    evento.evt.preventDefault();
    const stage = evento.target.getStage();
    const puntero = stage?.getPointerPosition();
    if (!stage || !puntero) {
      return;
    }
    const factor = evento.evt.deltaY < 0 ? FACTOR_RUEDA : 1 / FACTOR_RUEDA;
    const zoom = limitar(vista.zoom * factor, ZOOM_MINIMO, ZOOM_MAXIMO);
    const ancla = { x: (puntero.x - vista.x) / vista.zoom, y: (puntero.y - vista.y) / vista.zoom };
    setVista(
      zoom === ZOOM_MINIMO
        ? { zoom, x: 0, y: 0 }
        : { zoom, x: puntero.x - ancla.x * zoom, y: puntero.y - ancla.y * zoom },
    );
  };

  const moverEtiqueta = (id: string, evento: KonvaEventObject<MouseEvent>) => {
    const caja = contenedor.current?.getBoundingClientRect();
    if (caja) {
      setEtiqueta({
        texto: etiquetaFragmento(id),
        x: evento.evt.clientX - caja.left,
        y: evento.evt.clientY - caja.top,
      });
    }
  };

  const colorDe = (id: string): string => {
    const rango = rangoPorId.get(id);
    return rango === undefined ? estilo.colorFragmento : estilo.coloresRango[rango] ?? estilo.colorFragmento;
  };

  const grosor = estilo.grosor / vista.zoom;
  const radio = estilo.radioVertice / vista.zoom;
  const clases = ["lienzo-fragmentos__escenario", editando ? "lienzo-fragmentos__escenario--trazo" : ""]
    .filter(Boolean)
    .join(" ");

  return (
    <div ref={contenedor} className="lienzo-fragmentos">
      {ajuste > 0 && (
        <Stage
          width={ancho}
          height={alto}
          scaleX={vista.zoom}
          scaleY={vista.zoom}
          x={vista.x}
          y={vista.y}
          draggable={!editando && vista.zoom > ZOOM_MINIMO}
          onDragEnd={(e) => {
            if (e.target === e.target.getStage()) {
              setVista((v) => ({ ...v, x: e.target.x(), y: e.target.y() }));
            }
          }}
          onWheel={alGirarRueda}
          onClick={alHacerClic}
          onTap={alHacerClic}
          onDblClick={() => editando && onCerrarTrazo()}
          className={clases}
        >
          <Layer>
            {imagen && <ImagenKonva image={imagen} width={ancho} height={alto} listening={false} />}

            {regionExcluida && (
              <Line
                points={aplanar(regionExcluida.map((p) => aPantalla(p, ajuste)))}
                closed
                stroke={estilo.colorDivision}
                strokeWidth={grosor}
                dash={estilo.punteado.map((d) => d / vista.zoom)}
                listening={false}
              />
            )}

            {mostrarContornos &&
              fragmentos.map((fragmento) => {
                const seleccionado = seleccionados.has(fragmento.id);
                const color = seleccionado ? estilo.colorSeleccionado : colorDe(fragmento.id);
                return (
                  <Line
                    key={fragmento.id}
                    points={aplanar(fragmento.poligono.map((p) => aPantalla(p, ajuste)))}
                    closed
                    stroke={color}
                    strokeWidth={seleccionado ? grosor * 2 : grosor}
                    fill={conAlfa(color, seleccionado ? estilo.alfaSeleccionado : estilo.alfaRelleno)}
                    listening={!editando}
                    onClick={(e) => {
                      e.cancelBubble = true;
                      onClicFragmento(fragmento.id, e.evt.shiftKey || e.evt.ctrlKey || e.evt.metaKey);
                    }}
                    onTap={(e) => {
                      e.cancelBubble = true;
                      onClicFragmento(fragmento.id, true);
                    }}
                    onMouseMove={(e) => moverEtiqueta(fragmento.id, e)}
                    onMouseLeave={() => setEtiqueta(null)}
                  />
                );
              })}

            {trazo.length > 0 && (
              <Line
                points={aplanar(trazo.map((p) => aPantalla(p, ajuste)))}
                stroke={herramienta === "dividir" ? estilo.colorDivision : estilo.colorDibujo}
                strokeWidth={grosor * 1.5}
                dash={herramienta === "dividir" ? estilo.punteado.map((d) => d / vista.zoom) : undefined}
                listening={false}
              />
            )}
            {trazo.map((vertice, indice) => {
              const p = aPantalla(vertice, ajuste);
              const esPrimero = indice === 0 && herramienta === "dibujar" && trazo.length >= 3;
              return (
                <Circle
                  key={`trazo-${indice}`}
                  x={p.x}
                  y={p.y}
                  radius={esPrimero ? radio * 1.6 : radio}
                  fill={estilo.colorVertice}
                  stroke={herramienta === "dividir" ? estilo.colorDivision : estilo.colorDibujo}
                  strokeWidth={grosor}
                  listening={esPrimero}
                  onClick={(e) => {
                    e.cancelBubble = true;
                    onCerrarTrazo();
                  }}
                />
              );
            })}
          </Layer>
        </Stage>
      )}

      {vista.zoom > ZOOM_MINIMO && (
        <button
          type="button"
          className="lienzo-fragmentos__ajustar"
          onClick={() => setVista({ zoom: 1, x: 0, y: 0 })}
        >
          Ajustar a la pantalla
        </button>
      )}
      {etiqueta && !editando && (
        <div className="lienzo-fragmentos__etiqueta" style={{ left: etiqueta.x, top: etiqueta.y }}>
          {etiqueta.texto}
        </div>
      )}
    </div>
  );
}
