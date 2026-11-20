import { useRef, useState } from "react";
import type { ChangeEvent, DragEvent, KeyboardEvent } from "react";
import { useNavigate } from "react-router-dom";

import { crearAnalisis } from "../../api/analisis";
import { mensajeDeError } from "../../api/errores";
import { Boton } from "../../componentes/Boton";
import { Encabezado } from "../../componentes/Encabezado";
import { Icono } from "../../componentes/Icono";
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

        <div className="nuevo-analisis__cuerpo">
          <section className="nuevo-analisis__tarjeta" aria-labelledby="titulo-carga">
            <div className="nuevo-analisis__cabecera">
              <h1 id="titulo-carga" className="nuevo-analisis__titulo">
                Carga de imagen
              </h1>
              <p className="nuevo-analisis__ayuda">
                Formatos admitidos: JPG o PNG, tamaño máximo 20 MB. La imagen debe incluir un objeto de longitud
                conocida para la calibración.
              </p>
            </div>

            <div className="nuevo-analisis__campo-grupo">
              <label className="nuevo-analisis__etiqueta" htmlFor="nombre-analisis">
                Identificador del análisis <span className="nuevo-analisis__opcional">(opcional)</span>
              </label>
              <input
                id="nombre-analisis"
                className="nuevo-analisis__campo"
                type="text"
                placeholder="Ej.: Banco 3 – frente norte"
                value={nombre}
                onChange={(e: ChangeEvent<HTMLInputElement>) => setNombre(e.target.value)}
              />
            </div>

            <div
              className={`nuevo-analisis__zona${arrastrando ? " nuevo-analisis__zona--activa" : ""}${
                archivo ? " nuevo-analisis__zona--lista" : ""
              }`}
              role="button"
              tabIndex={0}
              aria-label="Seleccionar imagen"
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
                <>
                  <span className="nuevo-analisis__valida">
                    <Icono nombre="hecho" />
                    Imagen válida
                  </span>
                  <span className="nuevo-analisis__archivo">
                    {archivo.name} · <span className="cifra">{formatearTamano(archivo.size)}</span>
                  </span>
                  <span className="nuevo-analisis__ayuda">Haga clic para reemplazarla</span>
                </>
              ) : (
                <>
                  <span className="nuevo-analisis__icono-zona">
                    <Icono nombre="subir" />
                  </span>
                  <span className="nuevo-analisis__archivo">
                    Arrastre la imagen o <span className="nuevo-analisis__enlace">seleccione un archivo</span>
                  </span>
                  <span className="nuevo-analisis__ayuda">JPG, PNG · máx. 20 MB</span>
                </>
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
                {enviando ? "Creando..." : "Continuar a calibración"}
                {!enviando && <Icono nombre="siguiente" />}
              </Boton>
            </div>
          </section>

          <aside className="nuevo-analisis__requisitos" aria-labelledby="titulo-requisitos">
            <h2 id="titulo-requisitos" className="nuevo-analisis__subtitulo">
              Requisitos de captura
            </h2>
            <ol className="nuevo-analisis__lista">
              <li>
                <strong>Eje óptico perpendicular</strong> a la superficie de la pila, para minimizar la distorsión de
                perspectiva.
              </li>
              <li>
                <strong>Objeto de referencia</strong> (regla, mira o esfera) en el mismo plano que los fragmentos.
              </li>
              <li>
                <strong>Iluminación difusa</strong>: evitar sombras proyectadas y contraluz.
              </li>
              <li>
                <strong>Resolución suficiente</strong> para que los fragmentos más finos de interés ocupen varios
                píxeles.
              </li>
            </ol>
          </aside>
        </div>
      </main>
    </div>
  );
}
