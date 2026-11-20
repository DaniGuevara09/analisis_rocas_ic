import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { obtenerSalud, urlImagen } from "../../api/analisis";
import type { FragmentoSolicitud, Punto } from "../../api/tipos";
import { Boton } from "../../componentes/Boton";
import { Encabezado } from "../../componentes/Encabezado";
import { Icono, type NombreIcono } from "../../componentes/Icono";
import { IndicadorPasos } from "../../componentes/IndicadorPasos";
import { colorPorFragmento, LeyendaRangos } from "../../componentes/LeyendaRangos";
import { MensajeError } from "../../componentes/MensajeError";
import { ModalConfirmacion } from "../../componentes/ModalConfirmacion";
import { type Herramienta, LienzoFragmentos } from "../../editor/LienzoFragmentos";
import { cercaDe, contienePunto, dividirPoligono, unirPoligonos } from "../../editor/operacionesPoligonos";
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

/** Lista de verificación del operador; solo orienta la revisión, no se guarda. */
const REVISIONES = [
  { id: "sub", titulo: "Subsegmentación", detalle: "Fragmentos contiguos detectados como uno solo → Dividir." },
  { id: "omitidos", titulo: "Fragmentos no detectados", detalle: "Fragmentos visibles sin contorno → Dibujar." },
  { id: "falsos", titulo: "Falsos positivos", detalle: "Sombras, vacíos o finos marcados como fragmento → Eliminar." },
] as const;

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
  const [revision, setRevision] = useState<Set<string>>(new Set());

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

  const cerrarDibujo = useCallback(() => {
    const puntos = sinRepetidos(trazo);
    if (herramienta !== "dibujar" || puntos.length < 3 || ocupado) {
      return;
    }
    const nuevo: FragmentoSolicitud = { poligono: puntos, origen: "MANUAL" };
    void aplicar([...fragmentos.map(aSolicitud), nuevo]);
    setTrazo([]);
  }, [aplicar, fragmentos, herramienta, ocupado, trazo]);

  const dividir = (a: Punto, b: Punto) => {
    const medio = { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 };
    const objetivo = fragmentos.find((f) => contienePunto(f.poligono, medio));
    const piezas = objetivo ? dividirPoligono(objetivo.poligono, a, b) : null;
    setTrazo([]);
    if (!objetivo || !piezas) {
      setError("La línea debe cruzar un fragmento de lado a lado (su centro debe quedar dentro).");
      return;
    }
    const resto = fragmentos.filter((f) => f.id !== objetivo.id).map(aSolicitud);
    const nuevos = piezas.map((poligono): FragmentoSolicitud => ({ poligono, origen: "MANUAL" }));
    void aplicar([...resto, ...nuevos]);
  };

  const alClicImagen = (punto: Punto) => {
    if (ocupado) {
      return;
    }
    if (herramienta === "seleccionar") {
      setSeleccionados(new Set());
    } else if (herramienta === "dibujar") {
      setTrazo((t) => [...t, punto]);
    } else if (trazo.length === 0) {
      setTrazo([punto]);
    } else {
      dividir(trazo[0], punto);
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
        void edicion.deshacer();
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
  }, [borrarSeleccion, cerrarDibujo, edicion, unirSeleccion]);

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
  const revisados = REVISIONES.filter((r) => revision.has(r.id)).length;
  const alternarRevision = (idRevision: string) =>
    setRevision((actual) => {
      const nuevo = new Set(actual);
      if (nuevo.has(idRevision)) {
        nuevo.delete(idRevision);
      } else {
        nuevo.add(idRevision);
      }
      return nuevo;
    });

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
                mostrarContornos={mostrarContornos}
                etiquetaFragmento={etiquetaFragmento}
                onClicFragmento={alClicFragmento}
                onClicImagen={alClicImagen}
                onCerrarTrazo={cerrarDibujo}
              />
            )}

            <div className="editor__ayuda-lienzo" role="status">
              <span className="editor__chip-modo">{NOMBRES[herramienta]}</span>
              <span className="editor__ayuda-texto">
                {edicion.segmentando
                  ? "Segmentando la imagen con el modelo de IA... puede tardar unos segundos."
                  : AYUDAS[herramienta]}
              </span>
              {herramienta === "dibujar" && trazo.length > 0 && (
                <span className="editor__fila">
                  <Boton onClick={cerrarDibujo} disabled={sinRepetidos(trazo).length < 3}>
                    Terminar fragmento
                  </Boton>
                  <Boton variante="secundario" onClick={() => setTrazo([])}>
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
            </section>

            <section
              className={`editor__seccion${segmentado ? " editor__seccion--activa" : ""}`}
              aria-labelledby="titulo-control"
            >
              <div className="editor__cabecera">
                <span className={`editor__marca${segmentado ? " editor__marca--activa" : ""}`}>2</span>
                <h2 id="titulo-control" className="editor__subtitulo">
                  Control de calidad
                </h2>
                <span className="editor__ayuda cifra">
                  {revisados} / {REVISIONES.length}
                </span>
              </div>
              {REVISIONES.map((r) => (
                <label key={r.id} className="editor__revision">
                  <input type="checkbox" checked={revision.has(r.id)} onChange={() => alternarRevision(r.id)} />
                  <span>
                    <strong>{r.titulo}</strong>
                    <span className="editor__ayuda">{r.detalle}</span>
                  </span>
                </label>
              ))}
            </section>

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
