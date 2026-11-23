import { useRef, useState } from "react";
import type { ChangeEvent, DragEvent, KeyboardEvent } from "react";
import { useNavigate } from "react-router-dom";

import { crearAnalisis, urlImagen } from "../../api/analisis";
import { mensajeDeError } from "../../api/errores";
import { Boton } from "../../componentes/Boton";
import { Encabezado } from "../../componentes/Encabezado";
import { Icono } from "../../componentes/Icono";
import { IndicadorPasos } from "../../componentes/IndicadorPasos";
import { MensajeError } from "../../componentes/MensajeError";
import { precargarImagen } from "../../editor/useImagen";
import { formatearTamano } from "../../utilidades/formato";
import "./NuevoAnalisis.css";

const TAMANO_MAXIMO_BYTES = 20 * 1024 * 1024;
/** Igual que el dominio (LONGITUD_MAXIMA_NOMBRE en backend/app/dominio/modelo.py). */
export const LONGITUD_MAXIMA_NOMBRE = 150;

/** Validación del nombre (el servidor también la hace). Devuelve el mensaje o "". */
export function validarNombre(nombre: string): string {
  const limpio = nombre.trim();
  if (!limpio) {
    return "Escriba un nombre para identificar el análisis.";
  }
  if (limpio.length > LONGITUD_MAXIMA_NOMBRE) {
    return `El nombre no puede superar ${LONGITUD_MAXIMA_NOMBRE} caracteres (tiene ${limpio.length}).`;
  }
  return "";
}

/** Nombre sugerido a partir del archivo: sin extensión y con espacios en lugar de _ y -. */
export function nombreDesdeArchivo(nombreArchivo: string): string {
  return nombreArchivo
    .replace(/\.[^.]+$/, "")
    .replace(/[_-]+/g, " ")
    .trim()
    .slice(0, LONGITUD_MAXIMA_NOMBRE);
}
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
  const [errorNombre, setErrorNombre] = useState("");
  const [nombreTocado, setNombreTocado] = useState(false);
  const [arrastrando, setArrastrando] = useState(false);
  const [enviando, setEnviando] = useState(false);

  const elegir = (candidato: File | undefined) => {
    if (!candidato) {
      return;
    }
    const problema = validarArchivo(candidato);
    setError(problema);
    setArchivo(problema ? null : candidato);
    if (!problema && !nombre.trim()) {
      setNombre(nombreDesdeArchivo(candidato.name));
      setErrorNombre("");
    }
  };

  const cambiarNombre = (valor: string) => {
    setNombre(valor);
    if (nombreTocado) {
      setErrorNombre(validarNombre(valor));
    }
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
    const problemaNombre = validarNombre(nombre);
    setNombreTocado(true);
    setErrorNombre(problemaNombre);
    if (problemaNombre) {
      document.getElementById("nombre-analisis")?.focus();
      return;
    }
    if (!archivo) {
      setError("Seleccione una imagen JPG o PNG.");
      return;
    }
    setEnviando(true);
    try {
      const creado = await crearAnalisis(nombre.trim(), archivo);
      void precargarImagen(urlImagen(creado.id));
      navigate(`/analisis/${creado.id}/calibracion`);
    } catch (e) {
      const mensaje = mensajeDeError(e);
      // Si el servidor rechaza el nombre, el error se muestra en su campo.
      if (/nombre/i.test(mensaje)) {
        setErrorNombre(mensaje);
      } else {
        setError(mensaje);
      }
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
                Identificador del análisis
              </label>
              <input
                id="nombre-analisis"
                className={`nuevo-analisis__campo${errorNombre ? " nuevo-analisis__campo--error" : ""}`}
                type="text"
                placeholder="Ej.: Banco 3 – frente norte"
                value={nombre}
                maxLength={LONGITUD_MAXIMA_NOMBRE + 20}
                aria-invalid={errorNombre !== ""}
                aria-describedby="nombre-analisis-ayuda"
                onChange={(e: ChangeEvent<HTMLInputElement>) => cambiarNombre(e.target.value)}
                onBlur={() => {
                  setNombreTocado(true);
                  setErrorNombre(validarNombre(nombre));
                }}
              />
              <p
                id="nombre-analisis-ayuda"
                className={`nuevo-analisis__nota${errorNombre ? " nuevo-analisis__nota--error" : ""}`}
                role={errorNombre ? "alert" : undefined}
              >
                {errorNombre || `Obligatorio, hasta ${LONGITUD_MAXIMA_NOMBRE} caracteres. Se propone el nombre del archivo.`}
              </p>
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
              <Boton disabled={!archivo || enviando || errorNombre !== ""} onClick={() => void continuar()}>
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
