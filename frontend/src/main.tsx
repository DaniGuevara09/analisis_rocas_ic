import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Route, Routes } from "react-router-dom";

import "./tema/tokens.css";
import "./estilos-base.css";
import { CalibrarExcluir } from "./pantallas/CalibrarExcluir/CalibrarExcluir";
import { EditorFragmentos } from "./pantallas/EditorFragmentos/EditorFragmentos";
import { MisAnalisis } from "./pantallas/MisAnalisis/MisAnalisis";
import { NuevoAnalisis } from "./pantallas/NuevoAnalisis/NuevoAnalisis";
import { Resultados } from "./pantallas/Resultados/Resultados";

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<MisAnalisis />} />
        <Route path="/analisis/nuevo" element={<NuevoAnalisis />} />
        <Route path="/analisis/:id/calibracion" element={<CalibrarExcluir />} />
        <Route path="/analisis/:id/editor" element={<EditorFragmentos />} />
        <Route path="/analisis/:id/resultados" element={<Resultados />} />
      </Routes>
    </BrowserRouter>
  </React.StrictMode>,
);
