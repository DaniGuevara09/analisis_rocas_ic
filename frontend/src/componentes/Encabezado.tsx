import { Link } from "react-router-dom";

import "./Encabezado.css";

/** Encabezado mínimo: solo el título, que lleva a la lista de análisis. */
export function Encabezado() {
  return (
    <header className="encabezado">
      <div className="encabezado__contenido">
        <Link to="/" className="encabezado__titulo">
          Análisis Granulométrico
        </Link>
      </div>
    </header>
  );
}
