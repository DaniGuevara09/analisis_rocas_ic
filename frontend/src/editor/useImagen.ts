import { useEffect, useState } from "react";

const LIMITE_CACHE = 8;
const cacheImagenes = new Map<string, HTMLImageElement>();
const enCurso = new Map<string, Promise<HTMLImageElement | null>>();

function guardarEnCache(url: string, img: HTMLImageElement): void {
  if (cacheImagenes.has(url)) {
    cacheImagenes.delete(url);
  }
  cacheImagenes.set(url, img);
  while (cacheImagenes.size > LIMITE_CACHE) {
    const masAntigua = cacheImagenes.keys().next().value;
    if (masAntigua !== undefined) {
      cacheImagenes.delete(masAntigua);
    }
  }
}

/** Inicia la descarga y decodificación de la imagen en paralelo para evitar esperas en cadena. */
export function precargarImagen(url: string): Promise<HTMLImageElement | null> {
  if (!url) {
    return Promise.resolve(null);
  }
  const existente = cacheImagenes.get(url);
  if (existente) {
    return Promise.resolve(existente);
  }
  const pendiente = enCurso.get(url);
  if (pendiente) {
    return pendiente;
  }
  const promesa = new Promise<HTMLImageElement | null>((resolve) => {
    const candidata = new window.Image();
    candidata.decoding = "async";
    candidata.onload = () => {
      guardarEnCache(url, candidata);
      enCurso.delete(url);
      resolve(candidata);
    };
    candidata.onerror = () => {
      enCurso.delete(url);
      resolve(null);
    };
    candidata.src = url;
  });
  enCurso.set(url, promesa);
  return promesa;
}

/** Carga una imagen del navegador reutilizando la caché en memoria para cambios instantáneos de paso. */
export function useImagen(url: string): HTMLImageElement | null {
  const [imagen, setImagen] = useState<HTMLImageElement | null>(() => cacheImagenes.get(url) ?? null);

  useEffect(() => {
    const enMemoria = cacheImagenes.get(url);
    if (enMemoria) {
      setImagen(enMemoria);
      return;
    }
    setImagen(null);
    let activo = true;
    void precargarImagen(url).then((cargada) => {
      if (activo && cargada) {
        setImagen(cargada);
      }
    });
    return () => {
      activo = false;
    };
  }, [url]);

  return imagen;
}
