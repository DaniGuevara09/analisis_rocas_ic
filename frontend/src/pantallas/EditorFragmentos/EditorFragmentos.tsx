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
  unirPoligonos,
} from "../../editor/operacionesPoligonos";
import { formatearMm, formatearNumero } from "../../utilidades/formato";
import { aSolicitud, useEdicionFragmentos } from "./useEdicionFragmentos";
import "./EditorFragmentos.css";

const AYUDAS: Record<Herramienta, string> = {
  seleccionar:
    "Clic sobre un fragmento para ver su tamaño; Shift + clic para seleccionar varios y luego Unir o Eliminar. Rueda del ratón o botones: zoom; arrastre: desplazar.",
  dibujar:
    "Digitalice el contorno de un fragmento no detectado. Cierre el polígono sobre el primer vértice, con doble clic o con Enter.",
  dividir: "Corrige subsegmentación: trace con dos clics una línea de corte que atraviese el fragmento de borde a borde.",
};

type ModoDivision = "recta" | "quebrada";

const AYUDA_QUEBRADA =
  "Corte libre: haga clic a lo largo de la grieta, de borde a borde del fragmento, y termine con doble clic o Enter.";

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
  const { detalle, fragmentos, resultados, aplicar, setError } = edicion;

  const [herramienta, setHerramienta] = useState<Herramienta>("seleccionar");
  const [seleccionados, setSeleccionados] = useState<Set<string>>(new Set());
  const [trazo, setTrazo] = useState<Punto[]>([]);
  const [mostrarContornos, setMostrarContornos] = useState(true);
  const [confirmarSegmentar, setConfirmarSegmentar] = useState(false);
  const [modoDivision, setModoDivision] = useState<ModoDivision>("recta");

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
    setHerramienta(nueva);
    setTrazo([]);
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
      setTrazo([]);
      // Prueba los fragmentos que toca el trazo hasta encontrar uno que quede cortado.
      const medios = corte.slice(1).map((b, i) => ({ x: (corte[i].x + b.x) / 2, y: (corte[i].y + b.y) / 2 }));
      const toca = (poligono: Punto[]) => [...corte, ...medios].some((p) => contienePunto(poligono, p));
      let objetivo: Fragmento | null = null;
      let piezas: Punto[][] | null = null;
      for (const candidato of fragmentos.filter((f) => toca(f.poligono))) {
        piezas = dividirConTrazo(candidato.poligono, corte);
        if (piezas) {
          objetivo = candidato;
          break;
        }
      }
      if (!objetivo || !piezas) {
        setError("El corte debe atravesar un fragmento de un borde a otro.");
        return;
      }
      if (piezas.some(esDiminuto)) {
        setError(`Una de las partes quedaría con menos de ${AREA_MINIMA_FRAGMENTO_PX2} px². Trace el corte más al centro.`);
        return;
      }
      const resto = fragmentos.filter((f) => f.id !== objetivo.id).map(aSolicitud);
      const nuevos = piezas.map((poligono): FragmentoSolicitud => ({ poligono, origen: "MANUAL" }));
      void aplicar([...resto, ...nuevos]);
    },
    [aplicar, fragmentos, setError],
  );

  const cerrarDibujo = useCallback(() => {
    const puntos = sinRepetidos(trazo);
    if (herramienta === "dividir" && modoDivision === "quebrada") {
      if (puntos.length >= 2 && !ocupado) {
        dividir(puntos);
      }
      return;
    }
    if (herramienta !== "dibujar" || puntos.length < 3 || ocupado) {
      return;
    }
    if (esDiminuto(puntos)) {
      setTrazo([]);
      setError(
        `El contorno es demasiado pequeño (mínimo ${AREA_MINIMA_FRAGMENTO_PX2} px²). Haga clic alrededor de todo el borde del fragmento.`,
      );
      return;
    }
    const nuevo: FragmentoSolicitud = { poligono: puntos, origen: "MANUAL" };
    void aplicar([...fragmentos.map(aSolicitud), nuevo]);
    setTrazo([]);
  }, [aplicar, dividir, fragmentos, herramienta, modoDivision, ocupado, trazo, setError]);

  /** Quita el último punto marcado (clic equivocado al trazar). */
  const quitarUltimoPunto = useCallback(() => setTrazo((t) => t.slice(0, -1)), []);

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
    } else if (herramienta === "dibujar" || modoDivision === "quebrada") {
      setTrazo((t) => [...t, punto]);
    } else if (trazo.length === 0) {
      setTrazo([punto]);
    } else {
      dividir([trazo[0], punto]);
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

  // Atajos de teclado (ignorados mientras se escribe en un campo).
  useEffect(() => {
    const alPresionar = (evento: KeyboardEvent) => {
      if (evento.target instanceof HTMLInputElement || evento.target instanceof HTMLTextAreaElement) {
        return;
      }
      const tecla = evento.key.toLowerCase();
      if ((evento.ctrlKey || evento.metaKey) && tecla === "z") {
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
        setTrazo([]);
        setSeleccionados(new Set());
      } else if (tecla === "enter") {
        cerrarDibujo();
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
  }, [borrarSeleccion, cerrarDibujo, edicion, quitarUltimoPunto, trazo.length, unirSeleccion]);

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
    error: "No se guardó el último cambio",
  }[edicion.estadoGuardado];

  const segmentado = fragmentos.length > 0;
  const guardando = edicion.estadoGuardado === "guardando";
  const mensajeEspera = edicion.segmentando
    ? "Segmentando la imagen con el modelo de IA..."
    : guardando
      ? "Guardando el cambio y recalculando tamaños..."
      : null;
  const ayudaHerramienta = herramienta === "dividir" && modoDivision === "quebrada" ? AYUDA_QUEBRADA : AYUDAS[herramienta];
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
                onClick={() => void edicion.deshacer()}
                disabled={ocupado || !edicion.puedeDeshacer}
                title="Deshacer (Ctrl + Z)"
              >
                <Icono nombre="deshacer" />
                Deshacer
                <kbd className="editor__tecla">Ctrl Z</kbd>
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
              />
            )}

            <div className="editor__ayuda-lienzo" role="status">
              <span className="editor__chip-modo">{NOMBRES[herramienta]}</span>
              <span className="editor__ayuda-texto">{mensajeEspera ?? ayudaHerramienta}</span>
              {herramienta === "dividir" && (
                <span className="editor__opciones" role="radiogroup" aria-label="Tipo de corte">
                  {(
                    [
                      ["recta", "Línea recta"],
                      ["quebrada", "Corte libre"],
                    ] as const
                  ).map(([valor, texto]) => (
                    <button
                      key={valor}
                      type="button"
                      role="radio"
                      aria-checked={modoDivision === valor}
                      className={`editor__opcion${modoDivision === valor ? " editor__opcion--activa" : ""}`}
                      onClick={() => {
                        setModoDivision(valor);
                        setTrazo([]);
                      }}
                    >
                      {texto}
                    </button>
                  ))}
                </span>
              )}
              {trazo.length > 0 && (
                <span className="editor__fila">
                  {(herramienta === "dibujar" || modoDivision === "quebrada") && (
                    <Boton onClick={cerrarDibujo} disabled={ocupado || sinRepetidos(trazo).length < minimoPuntos}>
                      {herramienta === "dibujar" ? "Terminar fragmento" : "Cortar"}
                    </Boton>
                  )}
                  <Boton variante="secundario" onClick={quitarUltimoPunto} title="Quitar el último punto (Retroceso o Ctrl + Z)">
                    <Icono nombre="deshacer" />
                    Quitar punto
                  </Boton>
                  <Boton variante="secundario" onClick={() => setTrazo([])} title="Cancelar el trazo (Esc)">
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
                <div className="editor__escala">
                  <span className="editor__ayuda">
                    Escala{" "}
                    <span className="cifra">{formatearNumero(detalle.calibracion.factor_mm_por_px, 4)} mm/px</span>{" "}
                    (objeto de {formatearMm(detalle.calibracion.longitud_real_mm)})
                  </span>
                  <Boton variante="secundario" onClick={() => navigate(`/analisis/${id}/calibracion`)}>
                    Recalibrar
                  </Boton>
                </div>
              )}
              <p className="editor__ayuda">
                {detalle?.region_excluida
                  ? "Región excluida activa (contorno punteado): no se cuentan los fragmentos cuyo centro cae dentro."
                  : "Sin región excluida. Si el objeto de referencia aparece entre las rocas, exclúyalo en Calibración para que no se cuente como fragmento."}
              </p>
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
              <Boton variante="secundario" onClick={() => navigate(`/analisis/${id}/calibracion`)}>
                Atrás
              </Boton>
              <Boton
                className="editor__continuar"
                onClick={() => navigate(`/analisis/${id}/resultados`)}
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
