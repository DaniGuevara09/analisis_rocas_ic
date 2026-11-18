import { useRef, useState } from "react";
import type { ChangeEvent, DragEvent, KeyboardEvent } from "react";
import { useNavigate } from "react-router-dom";

import { crearAnalisis } from "../../api/analisis";
import { mensajeDeError } from "../../api/errores";
import { Boton } from "../../componentes/Boton";
import { Encabezado } from "../../componentes/Encabezado";
import { IndicadorPasos } from "../../componentes/IndicadorPasos";
import { MensajeError } from "../../componentes/MensajeError";
import { formatearTamano } from "../../utilidades/formato";
import "./NuevoAnalisis.css";

const TAMANO_MAXIMO_BYTES = 20 * 1024 * 1024;
const EXTENSION_VALIDA = /\.(jpe?g|png)$/i;

/** Validación previa en el cliente; la autoridad es el servidor. Devuelve el mensaje o "". */
export function validarArchivo(archivo: File): string {
  if (!EXTENSION_VALIDA.test(archivo.name)) {
    return "El archivo debe ser una imagen JPG o PNG.";
  }
  if (archivo.size > TAMANO_MAXIMO_BYTES) {
    return "La imagen supera el tamaño máximo de 20 MB.";
  }
  return "";
}

export function NuevoAnalisis() {
  const navigate = useNavigate();
  const selector = useRef<HTMLInputElement>(null);
  const [nombre, setNombre] = useState("");
  const [archivo, setArchivo] = useState<File | null>(null);
  const [error, setError] = useState("");
  const [arrastrando, setArrastrando] = useState(false);
  const [enviando, setEnviando] = useState(false);

  const elegir = (candidato: File | undefined) => {
    if (!candidato) {
      return;
    }
    const problema = validarArchivo(candidato);
    setError(problema);
    setArchivo(problema ? null : candidato);
  };

  const alSoltar = (evento: DragEvent<HTMLDivElement>) => {
    evento.preventDefault();
    setArrastrando(false);
    elegir(evento.dataTransfer.files[0]);
  };

  const alTeclear = (evento: KeyboardEvent<HTMLDivElement>) => {
    if (evento.key === "Enter" || evento.key === " ") {
      evento.preventDefault();
      selector.current?.click();
    }
  };

  const continuar = async () => {
    if (!archivo) {
      return;
    }
    setEnviando(true);
    try {
      const creado = await crearAnalisis(nombre, archivo);
      navigate(`/analisis/${creado.id}/calibracion`);
    } catch (e) {
      setError(mensajeDeError(e));
      setEnviando(false);
    }
  };

  return (
    <div className="nuevo-analisis">
      <Encabezado />
      <main className="nuevo-analisis__contenido">
        <IndicadorPasos actual={0} />
        <h1 className="nuevo-analisis__titulo">Nuevo análisis</h1>

        <label className="nuevo-analisis__etiqueta" htmlFor="nombre-analisis">
          Nombre del análisis
        </label>
        <input
          id="nombre-analisis"
          className="nuevo-analisis__campo"
          type="text"
          value={nombre}
          onChange={(e: ChangeEvent<HTMLInputElement>) => setNombre(e.target.value)}
        />

        <div
          className={`nuevo-analisis__zona${arrastrando ? " nuevo-analisis__zona--activa" : ""}`}
          role="button"
          tabIndex={0}
          onClick={() => selector.current?.click()}
          onKeyDown={alTeclear}
          onDragOver={(e) => {
            e.preventDefault();
            setArrastrando(true);
          }}
          onDragLeave={() => setArrastrando(false)}
          onDrop={alSoltar}
        >
          {archivo ? (
            <p className="nuevo-analisis__archivo">
              {archivo.name} · {formatearTamano(archivo.size)}
            </p>
          ) : (
            <p>Arrastre una fotografía JPG o PNG aquí, o haga clic para elegirla (máximo 20 MB)</p>
          )}
          <input
            ref={selector}
            type="file"
            hidden
            accept=".jpg,.jpeg,.png"
            aria-label="Archivo de imagen"
            onChange={(e) => elegir(e.target.files?.[0])}
          />
        </div>

        <MensajeError mensaje={error} />

        <div className="nuevo-analisis__acciones">
          <Boton variante="secundario" onClick={() => navigate("/")}>
            Cancelar
          </Boton>
          <Boton disabled={!archivo || enviando} onClick={() => void continuar()}>
            {enviando ? "Creando..." : "Continuar"}
          </Boton>
        </div>
      </main>
    </div>
  );
}
