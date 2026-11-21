import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { obtenerSalud, urlImagen } from "../../api/analisis";
import type { Fragmento, FragmentoSolicitud, Punto } from "../../api/tipos";
import { Boton } from "../../componentes/Boton";
import { Encabezado } from "../../componentes/Encabezado";
import { Icono, type NombreIcono } from "../../componentes/Icono";
import { IndicadorPasos } from "../../componentes/IndicadorPasos";
import { colorPorFragmento, LeyendaRangos } from "../../componentes/LeyendaRangos";
import { MensajeError } from "../../componentes/MensajeError";
import { ModalConfirmacion } from "../../componentes/ModalConfirmacion";
import { type Herramienta, LienzoFragmentos } from "../../editor/LienzoFragmentos";
import {
  AREA_MINIMA_FRAGMENTO_PX2,
  cercaDe,
  contienePunto,
  dividirConTrazo,
  esDiminuto,
  insertarPuntoEnBorde,
  unirPoligonos,
} from "../../editor/operacionesPoligonos";
import { formatearMm, formatearNumero } from "../../utilidades/formato";
import { aSolicitud, useEdicionFragmentos } from "./useEdicionFragmentos";
import "./EditorFragmentos.css";

const AYUDAS: Record<Herramienta, string> = {
  seleccionar:
    "Arrastre un punto para moverlo, tóquelo para eliminarlo o haga clic en el borde para agregar un punto. Pulse Guardar (Ctrl + S) al finalizar.",
  dibujar:
    "Digitalice el contorno de un fragmento no detectado. Termine con triple clic rápido, Enter o el botón Terminar fragmento.",
  dividir:
    "Corte libre: haga clic a lo largo de la grieta, de borde a borde del fragmento, y termine con triple clic rápido, Enter o el botón Cortar.",
};

const NOMBRES: Record<Herramienta, string> = {
  seleccionar: "Seleccionar",
  dibujar: "Dibujar",
  dividir: "Dividir",
};

const HERRAMIENTAS: { valor: Herramienta; texto: string; tecla: string; icono: NombreIcono }[] = [
  { valor: "seleccionar", texto: NOMBRES.seleccionar, tecla: "V", icono: "cursor" },
  { valor: "dibujar", texto: NOMBRES.dibujar, tecla: "D", icono: "lapiz" },
  { valor: "dividir", texto: NOMBRES.dividir, tecla: "C", icono: "tijeras" },
];

/** Quita los vértices repetidos consecutivos (el doble clic agrega el mismo punto dos veces). */
function sinRepetidos(puntos: Punto[]): Punto[] {
  return puntos.filter((p, i) => i === 0 || !cercaDe(p, puntos[i - 1], 0.5));
}

export function EditorFragmentos() {
  const { id = "" } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const edicion = useEdicionFragmentos(id);
  const { detalle, fragmentos, resultados, aplicar, editarLocal, guardarPendientes, cambiosPendientes, setError } =
    edicion;

  const [herramienta, setHerramienta] = useState<Herramienta>("seleccionar");
  const [seleccionados, setSeleccionados] = useState<Set<string>>(new Set());
  const [trazo, setTrazo] = useState<Punto[]>([]);
  const [puntosDeshechos, setPuntosDeshechos] = useState<Punto[]>([]);
  const [mostrarContornos, setMostrarContornos] = useState(true);
  const [confirmarSegmentar, setConfirmarSegmentar] = useState(false);

  const limpiarTrazo = useCallback(() => {
    setTrazo([]);
    setPuntosDeshechos([]);
  }, []);

  const ocupado = edicion.estadoGuardado === "guardando" || edicion.segmentando;

  // null = aún no se sabe; el editor avisa si no hay modelo instalado en backend/modelos.
  const [modeloDisponible, setModeloDisponible] = useState<boolean | null>(null);
  useEffect(() => {
    obtenerSalud()
      .then((salud) => setModeloDisponible(salud.modelo_disponible))
      .catch(() => setModeloDisponible(null));
  }, []);

  const colorPorId = useMemo(
    () => colorPorFragmento(resultados?.rangos ?? [], resultados?.fragmentos ?? []),
    [resultados],
  );
  const diametroPorId = useMemo(
    () => new Map(fragmentos.map((f) => [f.id, f.diametro_equivalente_mm])),
    [fragmentos],
  );

  const elegirHerramienta = (nueva: Herramienta) => {
    if (cambiosPendientes) {
      void guardarPendientes();
    }
    setHerramienta(nueva);
    limpiarTrazo();
    if (nueva !== "seleccionar") {
      setSeleccionados(new Set());
    }
  };

  const borrarSeleccion = useCallback(() => {
    if (seleccionados.size === 0 || ocupado) {
      return;
    }
    void aplicar(fragmentos.filter((f) => !seleccionados.has(f.id)).map(aSolicitud));
    setSeleccionados(new Set());
  }, [aplicar, fragmentos, ocupado, seleccionados]);

  const unirSeleccion = useCallback(() => {
    if (seleccionados.size < 2 || ocupado) {
      return;
    }
    const elegidos = fragmentos.filter((f) => seleccionados.has(f.id));
    const union = unirPoligonos(elegidos.map((f) => f.poligono));
    if (!union) {
      setError("Solo se pueden unir fragmentos que se tocan o se solapan.");
      return;
    }
    const resto = fragmentos.filter((f) => !seleccionados.has(f.id)).map(aSolicitud);
    void aplicar([...resto, { poligono: union, origen: "MANUAL" }]);
    setSeleccionados(new Set());
  }, [aplicar, fragmentos, ocupado, seleccionados, setError]);

  const dividir = useCallback(
    (corte: Punto[]) => {
      limpiarTrazo();
      // Prueba los fragmentos que toca el trazo hasta encontrar uno que quede cortado.
      const medios = corte.slice(1).map((b, i) => ({ x: (corte[i].x + b.x) / 2, y: (corte[i].y + b.y) / 2 }));
      const toca = (poligono: Punto[]) => [...corte, ...medios].some((p) => contienePunto(poligono, p));
      let objetivo: Fragmento | null = null;
      let piezas: Punto[][] | null = null;
      for (const candidato of fragmentos.filter((f) => toca(f.poligono))) {
        const resultado = dividirConTrazo(candidato.poligono, corte);
        const validas = resultado?.filter((p) => !esDiminuto(p)) ?? [];
        if (validas.length >= 2) {
          objetivo = candidato;
          piezas = validas;
          break;
        }
      }
      if (!objetivo || !piezas) {
        setError("El corte debe atravesar un fragmento de un borde a otro.");
        return;
      }
      const resto = fragmentos.filter((f) => f.id !== objetivo.id).map(aSolicitud);
      const nuevos = piezas.map((poligono): FragmentoSolicitud => ({ poligono, origen: "MANUAL" }));
      void aplicar([...resto, ...nuevos]);
    },
    [aplicar, fragmentos, limpiarTrazo, setError],
  );

  const cerrarDibujo = useCallback(() => {
    const puntos = sinRepetidos(trazo);
    if (herramienta === "dividir") {
      if (puntos.length >= 2 && !ocupado) {
        dividir(puntos);
      }
      return;
    }
    if (herramienta !== "dibujar" || puntos.length < 3 || ocupado) {
      return;
    }
    if (esDiminuto(puntos)) {
      limpiarTrazo();
      setError(
        `El contorno es demasiado pequeño (mínimo ${AREA_MINIMA_FRAGMENTO_PX2} px²). Haga clic alrededor de todo el borde del fragmento.`,
      );
      return;
    }
    const nuevo: FragmentoSolicitud = { poligono: puntos, origen: "MANUAL" };
    void aplicar([...fragmentos.map(aSolicitud), nuevo]);
    limpiarTrazo();
  }, [aplicar, dividir, fragmentos, herramienta, limpiarTrazo, ocupado, trazo, setError]);

  /** Quita el último punto marcado (clic equivocado al trazar) y lo guarda para poder rehacerlo con Ctrl + Y. */
  const quitarUltimoPunto = useCallback(() => {
    setTrazo((actual) => {
      if (actual.length === 0) {
        return actual;
      }
      const ultimo = actual[actual.length - 1];
      setPuntosDeshechos((deshechos) => [...deshechos, ultimo]);
      return actual.slice(0, -1);
    });
  }, []);

  /** Vuelve a colocar el último punto quitado con Ctrl + Z. */
  const rehacerPunto = useCallback(() => {
    setPuntosDeshechos((deshechos) => {
      if (deshechos.length === 0) {
        return deshechos;
      }
      const recuperado = deshechos[deshechos.length - 1];
      setTrazo((actual) => [...actual, recuperado]);
      return deshechos.slice(0, -1);
    });
  }, []);

  // Fragmentos diminutos guardados antes de existir la regla de área mínima.
  const diminutos = useMemo(() => fragmentos.filter((f) => esDiminuto(f.poligono)), [fragmentos]);
  const eliminarDiminutos = () => {
    if (ocupado) {
      return;
    }
    void aplicar(fragmentos.filter((f) => !esDiminuto(f.poligono)).map(aSolicitud));
  };

  const alClicImagen = (punto: Punto) => {
    if (ocupado) {
      return;
    }
    if (herramienta === "seleccionar") {
      setSeleccionados(new Set());
    } else {
      setPuntosDeshechos([]);
      setTrazo((t) => [...t, punto]);
    }
  };

  const alClicFragmento = (fragmentoId: string, aditivo: boolean) => {
    setSeleccionados((actual) => {
      if (!aditivo) {
        return actual.has(fragmentoId) && actual.size === 1 ? new Set() : new Set([fragmentoId]);
      }
      const nuevo = new Set(actual);
      if (nuevo.has(fragmentoId)) {
        nuevo.delete(fragmentoId);
      } else {
        nuevo.add(fragmentoId);
      }
      return nuevo;
    });
  };

  const editarPoligono = useCallback(
    (fragmentoId: string, nuevoPoligono: Punto[]) => {
      if (edicion.segmentando) {
        return;
      }
      if (esDiminuto(nuevoPoligono)) {
        setError(`El contorno es demasiado pequeño (mínimo ${AREA_MINIMA_FRAGMENTO_PX2} px²).`);
        return;
      }
      editarLocal(
        fragmentos.map((f) =>
          f.id === fragmentoId ? { ...f, poligono: nuevoPoligono, origen: "MANUAL" } : f,
        ),
      );
    },
    [edicion.segmentando, editarLocal, fragmentos, setError],
  );

  const eliminarVertice = useCallback(
    (fragmentoId: string, indice: number) => {
      if (edicion.segmentando) {
        return;
      }
      const objetivo = fragmentos.find((f) => f.id === fragmentoId);
      if (!objetivo) {
        return;
      }
      if (objetivo.poligono.length <= 3) {
        setError("Un fragmento debe conservar al menos 3 puntos.");
        return;
      }
      const nuevoPoligono = objetivo.poligono.filter((_, i) => i !== indice);
      if (esDiminuto(nuevoPoligono)) {
        setError(`El contorno resultante sería demasiado pequeño (mínimo ${AREA_MINIMA_FRAGMENTO_PX2} px²).`);
        return;
      }
      editarLocal(
        fragmentos.map((f) =>
          f.id === fragmentoId ? { ...f, poligono: nuevoPoligono, origen: "MANUAL" } : f,
        ),
      );
    },
    [edicion.segmentando, editarLocal, fragmentos, setError],
  );

  const agregarVerticeBorde = useCallback(
    (fragmentoId: string, punto: Punto) => {
      if (edicion.segmentando) {
        return;
      }
      const objetivo = fragmentos.find((f) => f.id === fragmentoId);
      if (!objetivo) {
        return;
      }
      const nuevoPoligono = insertarPuntoEnBorde(objetivo.poligono, punto);
      editarLocal(
        fragmentos.map((f) =>
          f.id === fragmentoId ? { ...f, poligono: nuevoPoligono, origen: "MANUAL" } : f,
        ),
      );
    },
    [edicion.segmentando, editarLocal, fragmentos],
  );

  // Atajos de teclado (ignorados mientras se escribe en un campo).
  useEffect(() => {
    const alPresionar = (evento: KeyboardEvent) => {
      if (evento.target instanceof HTMLInputElement || evento.target instanceof HTMLTextAreaElement) {
        return;
      }
      const tecla = evento.key.toLowerCase();
      if ((evento.ctrlKey || evento.metaKey) && tecla === "s") {
        evento.preventDefault();
        void guardarPendientes();
      } else if ((evento.ctrlKey || evento.metaKey) && (tecla === "y" || (evento.shiftKey && tecla === "z"))) {
        evento.preventDefault();
        if (puntosDeshechos.length > 0) {
          rehacerPunto();
        } else {
          void edicion.rehacer();
        }
      } else if ((evento.ctrlKey || evento.metaKey) && tecla === "z") {
        evento.preventDefault();
        if (trazo.length > 0) {
          quitarUltimoPunto();
        } else {
          void edicion.deshacer();
        }
      } else if (tecla === "backspace" && trazo.length > 0) {
        evento.preventDefault();
        quitarUltimoPunto();
      } else if (tecla === "delete" || tecla === "backspace") {
        borrarSeleccion();
      } else if (tecla === "escape") {
        if (cambiosPendientes) {
          void guardarPendientes();
        }
        limpiarTrazo();
        setSeleccionados(new Set());
      } else if (tecla === "enter") {
        if (herramienta === "seleccionar" && cambiosPendientes) {
          void guardarPendientes();
        } else {
          cerrarDibujo();
        }
      } else if (tecla === "u") {
        unirSeleccion();
      } else if (tecla === "v") {
        elegirHerramienta("seleccionar");
      } else if (tecla === "d") {
        elegirHerramienta("dibujar");
      } else if (tecla === "c") {
        elegirHerramienta("dividir");
      }
    };
    document.addEventListener("keydown", alPresionar);
    return () => document.removeEventListener("keydown", alPresionar);
  }, [
    borrarSeleccion,
    cerrarDibujo,
    edicion,
    limpiarTrazo,
    puntosDeshechos.length,
    quitarUltimoPunto,
    rehacerPunto,
    trazo.length,
    unirSeleccion,
  ]);

  const pedirSegmentacion = () => {
    if (fragmentos.length > 0) {
      setConfirmarSegmentar(true);
    } else {
      void edicion.segmentarAutomatico();
    }
  };

  const etiquetaFragmento = (fragmentoId: string) => {
    const diametro = diametroPorId.get(fragmentoId);
    return diametro == null ? "Fragmento" : `Diámetro equivalente: ${formatearMm(diametro)}`;
  };

  const textoGuardado = {
    guardado: "Guardado",
    guardando: "Guardando...",
    pendiente: "Sin guardar",
    error: "No se guardó el último cambio",
  }[edicion.estadoGuardado];

  const segmentado = fragmentos.length > 0;
  const guardando = edicion.estadoGuardado === "guardando";
  const mensajeEspera = edicion.segmentando
    ? "Segmentando la imagen con el modelo de IA..."
    : guardando
      ? "Guardando el cambio y recalculando tamaños..."
      : null;
  const ayudaHerramienta = AYUDAS[herramienta];
  const minimoPuntos = herramienta === "dibujar" ? 3 : 2;

  return (
    <div className="editor">
      <Encabezado />
      <main className="editor__contenido">
        <IndicadorPasos actual={2} />
        <MensajeError mensaje={edicion.error} />

        <div className="editor__cuerpo">
          <section className="editor__lienzo" aria-label="Fragmentos sobre la imagen">
            <div className="editor__barra" role="toolbar" aria-label="Herramientas de edición">
              {HERRAMIENTAS.map(({ valor, texto, tecla, icono }) => (
                <button
                  key={valor}
                  type="button"
                  className={`editor__herramienta${herramienta === valor ? " editor__herramienta--activa" : ""}`}
                  aria-pressed={herramienta === valor}
                  onClick={() => elegirHerramienta(valor)}
                  title={`${texto} (${tecla})`}
                >
                  <Icono nombre={icono} />
                  {texto}
                  <kbd className="editor__tecla">{tecla}</kbd>
                </button>
              ))}
              <span className="editor__separador" />
              <button
                type="button"
                className="editor__herramienta"
                onClick={unirSeleccion}
                disabled={ocupado || seleccionados.size < 2}
                title="Unir fragmentos seleccionados (U)"
              >
                <Icono nombre="unir" />
                Unir{seleccionados.size >= 2 ? ` (${seleccionados.size})` : ""}
                <kbd className="editor__tecla">U</kbd>
              </button>
              <button
                type="button"
                className="editor__herramienta editor__herramienta--peligro"
                onClick={borrarSeleccion}
                disabled={ocupado || seleccionados.size === 0}
                title="Eliminar fragmentos seleccionados (Supr)"
              >
                <Icono nombre="papelera" />
                Eliminar
                <kbd className="editor__tecla">Supr</kbd>
              </button>
              <button
                type="button"
                className="editor__herramienta"
                onClick={() => (trazo.length > 0 ? quitarUltimoPunto() : void edicion.deshacer())}
                disabled={ocupado || (trazo.length === 0 && !edicion.puedeDeshacer)}
                title="Deshacer (Ctrl + Z)"
              >
                <Icono nombre="deshacer" />
                Deshacer
                <kbd className="editor__tecla">Ctrl Z</kbd>
              </button>
              <button
                type="button"
                className="editor__herramienta"
                onClick={() => (puntosDeshechos.length > 0 ? rehacerPunto() : void edicion.rehacer())}
                disabled={ocupado || (puntosDeshechos.length === 0 && !edicion.puedeRehacer)}
                title="Rehacer (Ctrl + Y)"
              >
                <Icono nombre="rehacer" />
                Rehacer
                <kbd className="editor__tecla">Ctrl Y</kbd>
              </button>
              <button
                type="button"
                className={`editor__herramienta${cambiosPendientes ? " editor__herramienta--activa" : ""}`}
                onClick={() => void guardarPendientes()}
                disabled={ocupado || !cambiosPendientes}
                title="Guardar cambios y actualizar indicadores (Ctrl + S)"
              >
                <Icono nombre="hecho" />
                Guardar
                <kbd className="editor__tecla">Ctrl S</kbd>
              </button>
              <label className="editor__casilla">
                <input
                  type="checkbox"
                  checked={mostrarContornos}
                  onChange={(e) => setMostrarContornos(e.target.checked)}
                />
                Contornos
              </label>
            </div>

            {detalle && (
              <LienzoFragmentos
                urlImagen={urlImagen(id)}
                anchoImg={detalle.imagen.ancho_px}
                altoImg={detalle.imagen.alto_px}
                fragmentos={fragmentos}
                colorPorId={colorPorId}
                seleccionados={seleccionados}
                regionExcluida={detalle.region_excluida?.poligono ?? null}
                herramienta={herramienta}
                trazo={trazo}
                mensajeEspera={mensajeEspera}
                mostrarContornos={mostrarContornos}
                etiquetaFragmento={etiquetaFragmento}
                onClicFragmento={alClicFragmento}
                onClicImagen={alClicImagen}
                onCerrarTrazo={cerrarDibujo}
                onEditarPoligono={editarPoligono}
                onEliminarVertice={eliminarVertice}
                onAgregarVerticeBorde={agregarVerticeBorde}
              />
            )}

            <div className="editor__ayuda-lienzo" role="status">
              <span className="editor__chip-modo">{NOMBRES[herramienta]}</span>
              <span className="editor__ayuda-texto">{mensajeEspera ?? ayudaHerramienta}</span>
              {cambiosPendientes && trazo.length === 0 && (
                <span className="editor__fila">
                  <Boton onClick={() => void guardarPendientes()} disabled={ocupado}>
                    Guardar cambios
                  </Boton>
                </span>
              )}
              {(trazo.length > 0 || puntosDeshechos.length > 0) && (
                <span className="editor__fila">
                  {(herramienta === "dibujar" || herramienta === "dividir") && (
                    <Boton onClick={cerrarDibujo} disabled={ocupado || sinRepetidos(trazo).length < minimoPuntos}>
                      {herramienta === "dibujar" ? "Terminar fragmento" : "Cortar"}
                    </Boton>
                  )}
                  {trazo.length > 0 && (
                    <Boton variante="secundario" onClick={quitarUltimoPunto} title="Quitar el último punto (Retroceso o Ctrl + Z)">
                      <Icono nombre="deshacer" />
                      Quitar punto
                    </Boton>
                  )}
                  {puntosDeshechos.length > 0 && (
                    <Boton variante="secundario" onClick={rehacerPunto} title="Restaurar el último punto quitado (Ctrl + Y)">
                      <Icono nombre="rehacer" />
                      Rehacer punto
                    </Boton>
                  )}
                  <Boton variante="secundario" onClick={limpiarTrazo} title="Cancelar el trazo (Esc)">
                    Cancelar
                  </Boton>
                </span>
              )}
            </div>
          </section>

          <aside className="editor__panel">
            <section className="editor__seccion" aria-labelledby="titulo-segmentacion">
              <div className="editor__cabecera">
                <span className={`editor__marca${segmentado ? " editor__marca--hecha" : " editor__marca--activa"}`}>
                  {segmentado ? <Icono nombre="hecho" /> : "1"}
                </span>
                <h2 id="titulo-segmentacion" className="editor__subtitulo">
                  Segmentación automática
                </h2>
                <Boton
                  variante={segmentado ? "secundario" : "primario"}
                  onClick={pedirSegmentacion}
                  disabled={!detalle || ocupado || modeloDisponible === false}
                >
                  {edicion.segmentando ? "Segmentando..." : segmentado ? "Reprocesar" : "Segmentar con IA"}
                </Boton>
              </div>
              {modeloDisponible === false ? (
                <p className="editor__aviso" role="status">
                  Modelo de IA no instalado. Copie <code>best.pt</code> en <code>backend/modelos/</code> y reinicie el
                  backend. Mientras tanto puede dibujar los fragmentos a mano.
                </p>
              ) : (
                <p className="editor__ayuda">
                  YOLOv11m-seg ·{" "}
                  {segmentado ? (
                    <>
                      <span className="cifra">{fragmentos.length}</span> fragmentos
                    </>
                  ) : (
                    "sin procesar"
                  )}
                </p>
              )}
              {detalle?.calibracion && (
                <p className="editor__ayuda">
                  Escala{" "}
                  <span className="cifra">{formatearNumero(detalle.calibracion.factor_mm_por_px, 4)} mm/px</span>{" "}
                  (objeto de {formatearMm(detalle.calibracion.longitud_real_mm)})
                </p>
              )}
              {detalle?.region_excluida && (
                <p className="editor__ayuda">
                  Región excluida activa (contorno punteado): no se cuentan los fragmentos cuyo centro cae dentro.
                </p>
              )}
              {segmentado && (
                <p className="editor__ayuda">
                  Revise el resultado: <strong>Dividir</strong> los fragmentos unidos, <strong>Dibujar</strong> los no
                  detectados y <strong>Eliminar</strong> sombras o huecos marcados como roca.
                </p>
              )}
            </section>

            {diminutos.length > 0 && (
              <section className="editor__seccion" aria-label="Fragmentos diminutos">
                <p className="editor__aviso" role="status">
                  Hay {diminutos.length} {diminutos.length === 1 ? "fragmento" : "fragmentos"} de menos de{" "}
                  {AREA_MINIMA_FRAGMENTO_PX2} px², probablemente clics accidentales. Distorsionan el histograma y el
                  ajuste, y no se pueden guardar otros cambios mientras existan.
                </p>
                <Boton variante="secundario" onClick={eliminarDiminutos} disabled={ocupado}>
                  Eliminar {diminutos.length === 1 ? "fragmento diminuto" : "fragmentos diminutos"}
                </Boton>
              </section>
            )}

            <section className="editor__seccion" aria-labelledby="titulo-indicadores" aria-live="polite">
              <div className="editor__cabecera">
                <h2 id="titulo-indicadores" className="editor__subtitulo">
                  Indicadores preliminares
                </h2>
                <span className={`editor__guardado editor__guardado--${edicion.estadoGuardado}`} role="status">
                  {textoGuardado}
                </span>
              </div>
              <dl className="editor__metricas">
                <div>
                  <dt>N</dt>
                  <dd className="cifra">{fragmentos.length}</dd>
                </div>
                <div>
                  <dt>D50 (mm)</dt>
                  <dd className="cifra">{resultados ? formatearNumero(resultados.d50, 0) : "—"}</dd>
                </div>
                <div>
                  <dt>D80 (mm)</dt>
                  <dd className="cifra">{resultados ? formatearNumero(resultados.d80, 0) : "—"}</dd>
                </div>
                <div>
                  <dt>n</dt>
                  <dd className="cifra">{resultados ? formatearNumero(resultados.indice_n, 2) : "—"}</dd>
                </div>
              </dl>
              {resultados ? (
                <LeyendaRangos rangos={resultados.rangos} fragmentos={resultados.fragmentos} />
              ) : (
                <p className="editor__ayuda">Se necesitan al menos 3 fragmentos para calcular.</p>
              )}
            </section>

            <div className="editor__fila">
              <Boton
                variante="secundario"
                onClick={() => {
                  void guardarPendientes().then((ok) => {
                    if (ok) {
                      navigate(`/analisis/${id}/calibracion`);
                    }
                  });
                }}
              >
                <Icono nombre="anterior" />
                Recalibrar
              </Boton>
              <Boton
                className="editor__continuar"
                onClick={() => {
                  void guardarPendientes().then((ok) => {
                    if (ok) {
                      navigate(`/analisis/${id}/resultados`);
                    }
                  });
                }}
                disabled={!resultados || ocupado}
              >
                Ver resultados
                <Icono nombre="siguiente" />
              </Boton>
            </div>
          </aside>
        </div>
      </main>

      {confirmarSegmentar && (
        <ModalConfirmacion
          titulo="Volver a segmentar"
          mensaje={`Se reemplazarán los ${fragmentos.length} fragmentos actuales, incluidos los que corrigió a mano. Podrá deshacerlo con "Deshacer".`}
          textoConfirmar="Segmentar"
          onConfirmar={() => {
            setConfirmarSegmentar(false);
            void edicion.segmentarAutomatico();
          }}
          onCancelar={() => setConfirmarSegmentar(false)}
        />
      )}
    </div>
  );
}
