import type Konva from "konva";
import type { KonvaEventObject } from "konva/lib/Node";
import { useEffect, useMemo, useRef, useState } from "react";
import { Circle, Image as ImagenKonva, Layer, Line, Stage } from "react-konva";

import type { Fragmento, Punto } from "../api/tipos";
import { Icono } from "../componentes/Icono";
import { conAlfa, leerEstiloFragmentos } from "../tema/leerTokens";
import { aImagen, aPantalla, aplanar, escalaAjuste, limitar } from "./geometria";
import { useImagen } from "./useImagen";
import "./LienzoFragmentos.css";

export type Herramienta = "seleccionar" | "dibujar" | "dividir" | "pincel";

const ZOOM_MINIMO = 1;
const ZOOM_MAXIMO = 12;
const FACTOR_RUEDA = 1.15;
const FACTOR_BOTON = 1.5;

interface Props {
  urlImagen: string;
  anchoImg: number;
  altoImg: number;
  fragmentos: Fragmento[];
  /** Color del rango de tamaño de cada fragmento (si ya hay resultados). */
  colorPorId: Map<string, string>;
  seleccionados: Set<string>;
  regionExcluida: Punto[] | null;
  herramienta: Herramienta;
  /** Escala de grosor del pincel mágico (p. ej. 0.5 = fino, 1 = medio, 1.8 = grueso). */
  escalaPincel?: number;
  /** Vértices del fragmento que se dibuja o extremos de la línea de división (px de la imagen). */
  trazo: Punto[];
  mostrarContornos: boolean;
  /** Si no es null, cubre el lienzo con un aviso de espera (guardando, segmentando). */
  mensajeEspera?: string | null;
  /** Texto de la etiqueta flotante al pasar el ratón sobre un fragmento. */
  etiquetaFragmento: (id: string) => string;
  onClicFragmento: (id: string, aditivo: boolean) => void;
  onClicImagen: (punto: Punto) => void;
  onCerrarTrazo: () => void;
  onEditarPoligono?: (id: string, poligono: Punto[]) => void;
  onEliminarVertice?: (id: string, indice: number) => void;
  onAgregarVerticeBorde?: (id: string, punto: Punto) => void;
  onTerminarPincel?: (trazo: Punto[], radioPx: number) => void;
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

/** Lienzo del editor: zoom con la rueda o los botones, arrastre para moverse y coordenadas en px originales. */
export function LienzoFragmentos({
  urlImagen,
  anchoImg,
  altoImg,
  fragmentos,
  colorPorId,
  seleccionados,
  regionExcluida,
  herramienta,
  escalaPincel = 1,
  trazo,
  mostrarContornos,
  mensajeEspera = null,
  etiquetaFragmento,
  onClicFragmento,
  onClicImagen,
  onCerrarTrazo,
  onEditarPoligono,
  onEliminarVertice,
  onAgregarVerticeBorde,
  onTerminarPincel,
}: Props) {
  const contenedor = useRef<HTMLDivElement>(null);
  const [espacio, setEspacio] = useState({ ancho: 0, alto: 0 });
  const [vista, setVista] = useState<Vista>({ zoom: 1, x: 0, y: 0 });
  const [etiqueta, setEtiqueta] = useState<Etiqueta | null>(null);
  const [poligonoArrastrando, setPoligonoArrastrando] = useState<{ id: string; poligono: Punto[] } | null>(null);
  const [trazoPincel, setTrazoPincel] = useState<Punto[]>([]);
  const [cursorPincel, setCursorPincel] = useState<Punto | null>(null);
  const pintandoRef = useRef(false);
  const arrastradoRef = useRef(false);
  const clicsMismoPuntoRef = useRef<{ tiempo: number; x: number; y: number; cuenta: number }>({
    tiempo: 0,
    x: 0,
    y: 0,
    cuenta: 0,
  });
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
  const radioBasePx = Math.max(4, Math.min(anchoImg, altoImg) * 0.009);
  const radioPincelPx = Math.max(2, Math.round((radioBasePx * escalaPincel) / Math.sqrt(vista.zoom)));

  const posicionEnImagen = (stage: Konva.Stage | null): Punto | null => {
    const relativa = stage?.getRelativePointerPosition();
    if (!relativa) {
      return null;
    }
    const punto = aImagen(relativa, ajuste);
    return { x: limitar(punto.x, 0, anchoImg), y: limitar(punto.y, 0, altoImg) };
  };

  const iniciarPincel = (evento: KonvaEventObject<MouseEvent | TouchEvent>) => {
    if (herramienta !== "pincel" || mensajeEspera !== null) {
      return;
    }
    const punto = posicionEnImagen(evento.target.getStage());
    if (punto) {
      pintandoRef.current = true;
      setCursorPincel(punto);
      setTrazoPincel([punto]);
    }
  };

  const moverPincel = (evento: KonvaEventObject<MouseEvent | TouchEvent>) => {
    if (herramienta !== "pincel") {
      return;
    }
    const punto = posicionEnImagen(evento.target.getStage());
    if (!punto) {
      return;
    }
    setCursorPincel(punto);
    if (!pintandoRef.current) {
      return;
    }
    setTrazoPincel((actual) => {
      const ultimo = actual[actual.length - 1];
      if (ultimo && Math.hypot(punto.x - ultimo.x, punto.y - ultimo.y) < 2) {
        return actual;
      }
      return [...actual, punto];
    });
  };

  const finalizarPincel = () => {
    if (herramienta !== "pincel" || !pintandoRef.current) {
      return;
    }
    pintandoRef.current = false;
    setTrazoPincel((actual) => {
      if (actual.length > 0) {
        onTerminarPincel?.(actual, radioPincelPx);
      }
      return [];
    });
  };

  const alHacerClic = (evento: KonvaEventObject<MouseEvent | TouchEvent>) => {
    if (herramienta === "pincel") {
      return;
    }
    const stage = evento.target.getStage();
    const punto = posicionEnImagen(stage);
    if (!punto) {
      return;
    }
    if (editando) {
      const puntero = stage?.getPointerPosition();
      const ahora = performance.now();
      const previo = clicsMismoPuntoRef.current;
      const mismoSitio =
        puntero !== null &&
        puntero !== undefined &&
        ahora - previo.tiempo <= 550 &&
        Math.hypot(puntero.x - previo.x, puntero.y - previo.y) <= 14;
      const cuenta = mismoSitio ? previo.cuenta + 1 : 1;
      clicsMismoPuntoRef.current = {
        tiempo: ahora,
        x: puntero?.x ?? 0,
        y: puntero?.y ?? 0,
        cuenta,
      };
      if (cuenta >= 3) {
        clicsMismoPuntoRef.current.cuenta = 0;
        onCerrarTrazo();
        return;
      }
      if (cuenta === 2) {
        // Segundo clic rápido en el mismo punto: no agrega un vértice duplicado y espera el tercer clic.
        return;
      }
    }
    onClicImagen(punto);
  };

  /** Cambia el zoom manteniendo fijo el punto `ancla` (coordenadas de pantalla del lienzo). */
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

  const centro = { x: ancho / 2, y: alto / 2 };

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
    return colorPorId.get(id) || estilo.colorFragmento;
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
          onMouseDown={iniciarPincel}
          onMouseMove={moverPincel}
          onMouseUp={finalizarPincel}
          onMouseLeave={finalizarPincel}
          onTouchStart={iniciarPincel}
          onTouchMove={moverPincel}
          onTouchEnd={finalizarPincel}
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
                const color = colorDe(fragmento.id);
                const poligonoActual =
                  poligonoArrastrando?.id === fragmento.id ? poligonoArrastrando.poligono : fragmento.poligono;
                return (
                  <Line
                    key={fragmento.id}
                    points={aplanar(poligonoActual.map((p) => aPantalla(p, ajuste)))}
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

            {mostrarContornos &&
              !editando &&
              fragmentos
                .filter((f) => seleccionados.has(f.id))
                .map((fragmento) => {
                  const poligonoActual =
                    poligonoArrastrando?.id === fragmento.id ? poligonoArrastrando.poligono : fragmento.poligono;
                  return (
                    <Line
                      key={`borde-${fragmento.id}`}
                      points={aplanar(poligonoActual.map((p) => aPantalla(p, ajuste)))}
                      closed
                      fillEnabled={false}
                      stroke="rgba(0,0,0,0.001)"
                      strokeWidth={14 / vista.zoom}
                      listening={onAgregarVerticeBorde !== undefined && mensajeEspera === null}
                      onClick={(e: KonvaEventObject<MouseEvent>) => {
                        e.cancelBubble = true;
                        const punto = posicionEnImagen(e.target.getStage());
                        if (punto) {
                          onAgregarVerticeBorde?.(fragmento.id, punto);
                        }
                      }}
                      onTap={(e: KonvaEventObject<TouchEvent>) => {
                        e.cancelBubble = true;
                        const punto = posicionEnImagen(e.target.getStage());
                        if (punto) {
                          onAgregarVerticeBorde?.(fragmento.id, punto);
                        }
                      }}
                    />
                  );
                })}

            {mostrarContornos &&
              !editando &&
              fragmentos
                .filter((f) => seleccionados.has(f.id))
                .map((fragmento) => {
                  const color = colorDe(fragmento.id);
                  const poligonoActual =
                    poligonoArrastrando?.id === fragmento.id ? poligonoArrastrando.poligono : fragmento.poligono;
                  return poligonoActual.map((vertice, indice) => {
                    const p = aPantalla(vertice, ajuste);
                    const actualizarVertice = (posPantalla: Punto): Punto[] => {
                      const enImg = aImagen(posPantalla, ajuste);
                      const limitado = {
                        x: limitar(enImg.x, 0, anchoImg),
                        y: limitar(enImg.y, 0, altoImg),
                      };
                      return poligonoActual.map((pt, i) => (i === indice ? limitado : pt));
                    };
                    return (
                      <Circle
                        key={`vertice-${fragmento.id}-${indice}`}
                        x={p.x}
                        y={p.y}
                        radius={radio}
                        fill={estilo.colorVertice}
                        stroke={color}
                        strokeWidth={grosor}
                        draggable={onEditarPoligono !== undefined && mensajeEspera === null}
                        dragBoundFunc={(pos: Punto) => ({
                          x: limitar(pos.x, vista.x, vista.x + ancho * vista.zoom),
                          y: limitar(pos.y, vista.y, vista.y + alto * vista.zoom),
                        })}
                        onMouseDown={() => {
                          arrastradoRef.current = false;
                        }}
                        onClick={(e: KonvaEventObject<MouseEvent>) => {
                          e.cancelBubble = true;
                          if (!arrastradoRef.current) {
                            onEliminarVertice?.(fragmento.id, indice);
                          }
                        }}
                        onTap={(e: KonvaEventObject<TouchEvent>) => {
                          e.cancelBubble = true;
                          if (!arrastradoRef.current) {
                            onEliminarVertice?.(fragmento.id, indice);
                          }
                        }}
                        onDragStart={(e: KonvaEventObject<DragEvent>) => {
                          e.cancelBubble = true;
                          arrastradoRef.current = false;
                          setEtiqueta(null);
                        }}
                        onDragMove={(e: KonvaEventObject<DragEvent>) => {
                          e.cancelBubble = true;
                          arrastradoRef.current = true;
                          const nuevo = actualizarVertice({ x: e.target.x(), y: e.target.y() });
                          setPoligonoArrastrando({ id: fragmento.id, poligono: nuevo });
                        }}
                        onDragEnd={(e: KonvaEventObject<DragEvent>) => {
                          e.cancelBubble = true;
                          const nuevo = actualizarVertice({ x: e.target.x(), y: e.target.y() });
                          setPoligonoArrastrando(null);
                          if (arrastradoRef.current) {
                            onEditarPoligono?.(fragmento.id, nuevo);
                          }
                        }}
                      />
                    );
                  });
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

            {herramienta === "pincel" && cursorPincel && trazoPincel.length === 0 && (
              <Circle
                x={aPantalla(cursorPincel, ajuste).x}
                y={aPantalla(cursorPincel, ajuste).y}
                radius={radioPincelPx * ajuste}
                fill={conAlfa(estilo.colorDibujo, 0.22)}
                stroke={estilo.colorDibujo}
                strokeWidth={grosor}
                listening={false}
              />
            )}
            {trazoPincel.length === 1 && (
              <Circle
                x={aPantalla(trazoPincel[0], ajuste).x}
                y={aPantalla(trazoPincel[0], ajuste).y}
                radius={radioPincelPx * ajuste}
                fill={conAlfa(estilo.colorDibujo, 0.45)}
                stroke={estilo.colorDibujo}
                strokeWidth={grosor}
                listening={false}
              />
            )}
            {trazoPincel.length >= 2 && (
              <Line
                points={aplanar(trazoPincel.map((p) => aPantalla(p, ajuste)))}
                stroke={conAlfa(estilo.colorDibujo, 0.48)}
                strokeWidth={radioPincelPx * ajuste * 2}
                lineCap="round"
                lineJoin="round"
                listening={false}
              />
            )}
          </Layer>
        </Stage>
      )}

      {ajuste > 0 && (
        <div className="lienzo-fragmentos__zoom" role="group" aria-label="Zoom de la imagen">
          <button
            type="button"
            className="lienzo-fragmentos__boton-zoom"
            aria-label="Alejar"
            title="Alejar"
            disabled={vista.zoom <= ZOOM_MINIMO}
            onClick={() => aplicarZoom(centro, 1 / FACTOR_BOTON)}
          >
            <Icono nombre="alejar" />
          </button>
          <span className="lienzo-fragmentos__porcentaje cifra" aria-live="polite">
            {Math.round(vista.zoom * 100)} %
          </span>
          <button
            type="button"
            className="lienzo-fragmentos__boton-zoom"
            aria-label="Acercar"
            title="Acercar"
            disabled={vista.zoom >= ZOOM_MAXIMO}
            onClick={() => aplicarZoom(centro, FACTOR_BOTON)}
          >
            <Icono nombre="acercar" />
          </button>
          <span className="lienzo-fragmentos__separador" />
          <button
            type="button"
            className="lienzo-fragmentos__boton-zoom lienzo-fragmentos__boton-zoom--texto"
            title="Ver la imagen completa"
            disabled={vista.zoom === ZOOM_MINIMO}
            onClick={() => setVista({ zoom: 1, x: 0, y: 0 })}
          >
            <Icono nombre="ajustar" />
            Ajustar
          </button>
        </div>
      )}
      {mensajeEspera && (
        <div className="lienzo-fragmentos__espera" role="status" aria-live="polite">
          <span className="lienzo-fragmentos__indicador" aria-hidden="true" />
          {mensajeEspera}
        </div>
      )}
      {etiqueta && !editando && (
        <div className="lienzo-fragmentos__etiqueta" style={{ left: etiqueta.x, top: etiqueta.y }}>
          {etiqueta.texto}
        </div>
      )}
    </div>
  );
}
