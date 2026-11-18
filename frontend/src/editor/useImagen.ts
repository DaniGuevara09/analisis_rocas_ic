import { useEffect, useState } from "react";

/** Carga una imagen del navegador para dibujarla en el lienzo. */
export function useImagen(url: string): HTMLImageElement | null {
  const [imagen, setImagen] = useState<HTMLImageElement | null>(null);

  useEffect(() => {
    const candidata = new window.Image();
    candidata.onload = () => setImagen(candidata);
    candidata.src = url;
    return () => {
      candidata.onload = null;
    };
  }, [url]);

  return imagen;
}
