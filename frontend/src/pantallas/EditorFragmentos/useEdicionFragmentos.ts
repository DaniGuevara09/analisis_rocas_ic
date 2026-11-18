import { useCallback, useEffect, useRef, useState } from "react";

import { guardarFragmentos, obtenerAnalisis, obtenerResultados, segmentar } from "../../api/analisis";
import { ErrorApi, mensajeDeError } from "../../api/errores";
import type { AnalisisDetalle, Fragmento, FragmentoSolicitud, Resultados } from "../../api/tipos";

/** Máximo de pasos que se pueden deshacer. */
const LIMITE_HISTORIAL = 50;

export type EstadoGuardado = "guardado" | "guardando" | "error";

export function aSolicitud(fragmento: Fragmento): FragmentoSolicitud {
  return { id: fragmento.id, poligono: fragmento.poligono, origen: fragmento.origen };
}

/**
 * Estado del editor: cada cambio se guarda en la API (PUT /fragmentos) y luego se piden los
 * resultados para refrescar métricas y colores. El frontend no calcula indicadores.
 */
export function useEdicionFragmentos(id: string) {
  const [detalle, setDetalle] = useState<AnalisisDetalle | null>(null);
  const [fragmentos, setFragmentos] = useState<Fragmento[]>([]);
  const [resultados, setResultados] = useState<Resultados | null>(null);
  const [historial, setHistorial] = useState<Fragmento[][]>([]);
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
    (lista: FragmentoSolicitud[]) => persistir(lista, fragmentos),
    [persistir, fragmentos],
  );

  const deshacer = useCallback(async () => {
    const anterior = historial[historial.length - 1];
    if (!anterior) {
      return;
    }
    if (await persistir(anterior.map(aSolicitud), null)) {
      setHistorial((h) => h.slice(0, -1));
    }
  }, [historial, persistir]);

  const segmentarAutomatico = useCallback(async () => {
    setSegmentando(true);
    setError("");
    try {
      const nuevos = await segmentar(id);
      setHistorial((h) => [...h, fragmentos].slice(-LIMITE_HISTORIAL));
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
    segmentando,
    error,
    setError,
    puedeDeshacer: historial.length > 0,
    aplicar,
    deshacer,
    segmentarAutomatico,
  };
}
