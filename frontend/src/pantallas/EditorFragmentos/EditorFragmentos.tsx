import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { urlImagen } from "../../api/analisis";
import type { FragmentoSolicitud, Punto } from "../../api/tipos";
import { Boton } from "../../componentes/Boton";
import { Encabezado } from "../../componentes/Encabezado";
import { EtiquetaEstado } from "../../componentes/EtiquetaEstado";
import { IndicadorPasos } from "../../componentes/IndicadorPasos";
import { LeyendaRangos } from "../../componentes/LeyendaRangos";
import { MensajeError } from "../../componentes/MensajeError";
import { ModalConfirmacion } from "../../componentes/ModalConfirmacion";
import { type Herramienta, LienzoFragmentos } from "../../editor/LienzoFragmentos";
import { cercaDe, contienePunto, dividirPoligono, unirPoligonos } from "../../editor/operacionesPoligonos";
import { formatearMm, formatearNumero } from "../../utilidades/formato";
import { aSolicitud, useEdicionFragmentos } from "./useEdicionFragmentos";
import "./EditorFragmentos.css";

const AYUDAS: Record<Herramienta, string> = {
  seleccionar:
    "Haga clic en un fragmento para seleccionarlo (Shift + clic para varios). Rueda del ratón: zoom; arrastre: mover.",
  dibujar:
    "Haga clic alrededor de la roca omitida. Para terminar, haga clic en el primer punto, doble clic o Enter.",
  dividir: "Trace una línea con dos clics sobre el fragmento que quiere separar.",
};

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

  const ocupado = edicion.estadoGuardado === "guardando" || edicion.segmentando;

  const rangoPorId = useMemo(
    () => new Map((resultados?.fragmentos ?? []).map((f) => [f.id, f.indice_rango])),
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
    guardado: "Cambios guardados",
    guardando: "Guardando...",
    error: "No se guardó el último cambio",
  }[edicion.estadoGuardado];

  return (
    <div className="editor">
      <Encabezado />
      <main className="editor__contenido">
        <IndicadorPasos actual={2} />
        <MensajeError mensaje={edicion.error} />

        <div className="editor__cuerpo">
          <section className="editor__lienzo" aria-label="Fragmentos sobre la imagen">
            {detalle && (
              <LienzoFragmentos
                urlImagen={urlImagen(id)}
                anchoImg={detalle.imagen.ancho_px}
                altoImg={detalle.imagen.alto_px}
                fragmentos={fragmentos}
                rangoPorId={rangoPorId}
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
            {edicion.segmentando && (
              <p className="editor__aviso" role="status">
                Segmentando la imagen con el modelo de IA... puede tardar unos segundos.
              </p>
            )}
          </section>

          <aside className="editor__panel">
            <div className="editor__encabezado-panel">
              <h1 className="editor__nombre">{detalle?.nombre ?? "Cargando..."}</h1>
              {detalle && <EtiquetaEstado estado={fragmentos.length > 0 ? "SEGMENTADO" : detalle.estado} />}
            </div>

            <section className="editor__seccion">
              <h2 className="editor__subtitulo">1. Segmentación automática</h2>
              <Boton onClick={pedirSegmentacion} disabled={!detalle || ocupado}>
                {edicion.segmentando ? "Segmentando..." : fragmentos.length > 0 ? "Volver a segmentar" : "Segmentar con IA"}
              </Boton>
            </section>

            <section className="editor__seccion">
              <h2 className="editor__subtitulo">2. Revisión y corrección</h2>
              <div className="editor__herramientas" role="group" aria-label="Herramienta">
                {(
                  [
                    ["seleccionar", "Seleccionar", "V"],
                    ["dibujar", "Dibujar", "D"],
                    ["dividir", "Dividir", "C"],
                  ] as const
                ).map(([valor, texto, tecla]) => (
                  <button
                    key={valor}
                    type="button"
                    className={`editor__herramienta${herramienta === valor ? " editor__herramienta--activa" : ""}`}
                    aria-pressed={herramienta === valor}
                    onClick={() => elegirHerramienta(valor)}
                    title={`Atajo: ${tecla}`}
                  >
                    {texto}
                  </button>
                ))}
              </div>
              <p className="editor__ayuda">{AYUDAS[herramienta]}</p>

              <div className="editor__fila">
                <Boton
                  variante="secundario"
                  onClick={unirSeleccion}
                  disabled={ocupado || seleccionados.size < 2}
                  title="Atajo: U"
                >
                  Unir ({seleccionados.size})
                </Boton>
                <Boton
                  variante="peligro"
                  onClick={borrarSeleccion}
                  disabled={ocupado || seleccionados.size === 0}
                  title="Atajo: Supr"
                >
                  Borrar
                </Boton>
                <Boton
                  variante="secundario"
                  onClick={() => void edicion.deshacer()}
                  disabled={ocupado || !edicion.puedeDeshacer}
                  title="Atajo: Ctrl + Z"
                >
                  Deshacer
                </Boton>
              </div>
              {herramienta === "dibujar" && trazo.length > 0 && (
                <div className="editor__fila">
                  <Boton onClick={cerrarDibujo} disabled={sinRepetidos(trazo).length < 3}>
                    Terminar fragmento
                  </Boton>
                  <Boton variante="secundario" onClick={() => setTrazo([])}>
                    Cancelar
                  </Boton>
                </div>
              )}
              <label className="editor__casilla">
                <input
                  type="checkbox"
                  checked={mostrarContornos}
                  onChange={(e) => setMostrarContornos(e.target.checked)}
                />
                Mostrar contornos
              </label>
              <p className={`editor__guardado editor__guardado--${edicion.estadoGuardado}`} role="status">
                {textoGuardado}
              </p>
            </section>

            <section className="editor__seccion" aria-live="polite">
              <h2 className="editor__subtitulo">Métricas en vivo</h2>
              <dl className="editor__metricas">
                <div>
                  <dt>Fragmentos</dt>
                  <dd>{fragmentos.length}</dd>
                </div>
                <div>
                  <dt>D50</dt>
                  <dd>{resultados ? formatearMm(resultados.d50) : "—"}</dd>
                </div>
                <div>
                  <dt>D80</dt>
                  <dd>{resultados ? formatearMm(resultados.d80) : "—"}</dd>
                </div>
                <div>
                  <dt>Índice n</dt>
                  <dd>{resultados ? formatearNumero(resultados.indice_n, 2) : "—"}</dd>
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
              <Boton onClick={() => navigate(`/analisis/${id}/resultados`)} disabled={!resultados || ocupado}>
                Ver resultados
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
