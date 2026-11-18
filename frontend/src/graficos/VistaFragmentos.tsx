import type { Fragmento } from "../api/tipos";
import { formatearMm } from "../utilidades/formato";
import "./VistaFragmentos.css";

interface Props {
  urlImagen: string;
  anchoImg: number;
  altoImg: number;
  fragmentos: Fragmento[];
  rangoPorId: Map<string, number>;
}

/** Imagen con los fragmentos coloreados por rango, en SVG (se imprime nítida en el PDF). */
export function VistaFragmentos({ urlImagen, anchoImg, altoImg, fragmentos, rangoPorId }: Props) {
  return (
    <svg
      className="vista-fragmentos"
      viewBox={`0 0 ${anchoImg} ${altoImg}`}
      role="img"
      aria-label="Fotografía con los fragmentos coloreados por rango de tamaño"
    >
      <image href={urlImagen} width={anchoImg} height={altoImg} />
      {fragmentos.map((f) => (
        <polygon
          key={f.id}
          className={`vista-fragmentos__poligono vista-fragmentos__poligono--${rangoPorId.get(f.id) ?? "sin-rango"}`}
          points={f.poligono.map((p) => `${p.x},${p.y}`).join(" ")}
        >
          {f.diametro_equivalente_mm != null && <title>{formatearMm(f.diametro_equivalente_mm)}</title>}
        </polygon>
      ))}
    </svg>
  );
}
