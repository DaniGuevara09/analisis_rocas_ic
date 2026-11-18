import { Link } from "react-router-dom";

import "./Encabezado.css";

export function Encabezado() {
  return (
    <header className="encabezado">
      <Link to="/" className="encabezado__titulo">
        Análisis Granulométrico de Roca
      </Link>
    </header>
  );
}
