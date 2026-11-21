import { useCallback, useEffect, useRef, useState } from "react";

import { guardarFragmentos, obtenerAnalisis, obtenerResultados, segmentar } from "../../api/analisis";
import { ErrorApi, mensajeDeError } from "../../api/errores";
import type { AnalisisDetalle, Fragmento, FragmentoSolicitud, Resultados } from "../../api/tipos";

/** Máximo de pasos que se pueden deshacer. */
const LIMITE_HISTORIAL = 50;

export type EstadoGuardado = "guardado" | "guardando" | "pendiente" | "error";

export function aSolicitud(fragmento: Fragmento): FragmentoSolicitud {
  return { id: fragmento.id, poligono: fragmento.poligono, origen: fragmento.origen };
}

/**
 * Estado del editor: cada cambio mayor se guarda en la API (PUT /fragmentos) y luego se piden los
 * resultados para refrescar métricas y colores. Los ajustes de vértices de contorno se acumulan
 * localmente y se guardan al finalizar la edición.
 */
export function useEdicionFragmentos(id: string) {
  const [detalle, setDetalle] = useState<AnalisisDetalle | null>(null);
  const [fragmentos, setFragmentos] = useState<Fragmento[]>([]);
  const [resultados, setResultados] = useState<Resultados | null>(null);
  const [historial, setHistorial] = useState<Fragmento[][]>([]);
  const [futuro, setFuturo] = useState<Fragmento[][]>([]);
  const [cambiosPendientes, setCambiosPendientes] = useState(false);
  const [estadoGuardado, setEstadoGuardado] = useState<EstadoGuardado>("guardado");
  const [segmentando, setSegmentando] = useState(false);
  const [error, setError] = useState("");
  const vigente = useRef(0);

  const refrescarResultados = useCallback(
    async (lista: Fragmento[]) => {
      const turno = ++vigente.current;
      if (lista.length < 3) {
        setResultados(null);
        return;
      }
      try {
        const nuevos = await obtenerResultados(id);
        if (turno === vigente.current) {
          setResultados(nuevos);
        }
      } catch (e) {
        if (turno === vigente.current) {
          setResultados(null);
          if (!(e instanceof ErrorApi && e.codigo === "DATOS_INSUFICIENTES")) {
            setError(mensajeDeError(e));
          }
        }
      }
    },
    [id],
  );

  useEffect(() => {
    obtenerAnalisis(id)
      .then((datos) => {
        setDetalle(datos);
        setFragmentos(datos.fragmentos);
        void refrescarResultados(datos.fragmentos);
      })
      .catch((e: unknown) => setError(mensajeDeError(e)));
  }, [id, refrescarResultados]);

  const persistir = useCallback(
    async (lista: FragmentoSolicitud[], anterior: Fragmento[] | null): Promise<boolean> => {
      setEstadoGuardado("guardando");
      setError("");
      try {
        const guardados = await guardarFragmentos(id, lista);
        if (anterior) {
          setHistorial((h) => [...h, anterior].slice(-LIMITE_HISTORIAL));
        }
        setFragmentos(guardados);
        setEstadoGuardado("guardado");
        await refrescarResultados(guardados);
        return true;
      } catch (e) {
        setEstadoGuardado("error");
        setError(mensajeDeError(e));
        return false;
      }
    },
    [id, refrescarResultados],
  );

  /** Aplica una edición (borrar, dibujar, unir, dividir) y la guarda. */
  const aplicar = useCallback(
    async (lista: FragmentoSolicitud[]) => {
      const ok = await persistir(lista, fragmentos);
      if (ok) {
        setFuturo([]);
        setCambiosPendientes(false);
      }
      return ok;
    },
    [persistir, fragmentos],
  );

  /** Actualiza los fragmentos localmente al instante (mover/agregar/quitar vértices) sin llamar aún al servidor. */
  const editarLocal = useCallback(
    (nuevos: Fragmento[]) => {
      setError("");
      setHistorial((h) => [...h, fragmentos].slice(-LIMITE_HISTORIAL));
      setFuturo([]);
      setFragmentos(nuevos);
      setCambiosPendientes(true);
      setEstadoGuardado("pendiente");
    },
    [fragmentos],
  );

  /** Envía al servidor los cambios de contorno acumulados localmente. */
  const guardarPendientes = useCallback(async (): Promise<boolean> => {
    if (!cambiosPendientes) {
      return true;
    }
    const ok = await persistir(fragmentos.map(aSolicitud), null);
    if (ok) {
      setCambiosPendientes(false);
    }
    return ok;
  }, [cambiosPendientes, fragmentos, persistir]);

  const deshacer = useCallback(async () => {
    const anterior = historial[historial.length - 1];
    if (!anterior) {
      return;
    }
    const actual = fragmentos;
    if (cambiosPendientes) {
      setHistorial((h) => h.slice(0, -1));
      setFuturo((f) => [...f, actual].slice(-LIMITE_HISTORIAL));
      setFragmentos(anterior);
      setEstadoGuardado("pendiente");
      return;
    }
    if (await persistir(anterior.map(aSolicitud), null)) {
      setHistorial((h) => h.slice(0, -1));
      setFuturo((f) => [...f, actual].slice(-LIMITE_HISTORIAL));
    }
  }, [cambiosPendientes, fragmentos, historial, persistir]);

  const rehacer = useCallback(async () => {
    const siguiente = futuro[futuro.length - 1];
    if (!siguiente) {
      return;
    }
    if (cambiosPendientes) {
      setHistorial((h) => [...h, fragmentos].slice(-LIMITE_HISTORIAL));
      setFuturo((f) => f.slice(0, -1));
      setFragmentos(siguiente);
      setEstadoGuardado("pendiente");
      return;
    }
    if (await persistir(siguiente.map(aSolicitud), fragmentos)) {
      setFuturo((f) => f.slice(0, -1));
    }
  }, [cambiosPendientes, fragmentos, futuro, persistir]);

  const segmentarAutomatico = useCallback(async () => {
    setSegmentando(true);
    setError("");
    try {
      const nuevos = await segmentar(id);
      setHistorial((h) => [...h, fragmentos].slice(-LIMITE_HISTORIAL));
      setFuturo([]);
      setCambiosPendientes(false);
      setFragmentos(nuevos);
      await refrescarResultados(nuevos);
    } catch (e) {
      setError(mensajeDeError(e));
    } finally {
      setSegmentando(false);
    }
  }, [id, fragmentos, refrescarResultados]);

  return {
    detalle,
    fragmentos,
    resultados,
    estadoGuardado,
    cambiosPendientes,
    segmentando,
    error,
    setError,
    puedeDeshacer: historial.length > 0,
    puedeRehacer: futuro.length > 0,
    aplicar,
    editarLocal,
    guardarPendientes,
    deshacer,
    rehacer,
    segmentarAutomatico,
  };
}
