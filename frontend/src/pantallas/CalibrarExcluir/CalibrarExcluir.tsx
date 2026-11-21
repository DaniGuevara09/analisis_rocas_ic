import { type ChangeEvent, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { calibrar, obtenerAnalisis, urlImagen } from "../../api/analisis";
import { mensajeDeError } from "../../api/errores";
import type { AnalisisDetalle, EstadoAnalisis, Punto } from "../../api/tipos";
import { Boton } from "../../componentes/Boton";
import { Encabezado } from "../../componentes/Encabezado";
import { Icono } from "../../componentes/Icono";
import { IndicadorPasos } from "../../componentes/IndicadorPasos";
import { MensajeError } from "../../componentes/MensajeError";
import { LienzoCalibracion } from "../../editor/LienzoCalibracion";
import { formatearMm, formatearNumero } from "../../utilidades/formato";
import {
  aMilimetros,
  avisoLongitud,
  calcularLongitudEfectivaMm,
  distanciaLineaPx,
  type Unidad,
  UNIDADES,
} from "./longitud";
import "./CalibrarExcluir.css";

type Modo = "ninguno" | "linea" | "linea2";

interface SegundoObjetoGuardado {
  linea1Texto: string;
  unidad1: Unidad;
  longitudCalibrada1: number;
  linea2: Punto[];
  longitud2: string;
  unidad2: Unidad;
  longitudCalibrada2: number;
}

function claveSegundoObjeto(id: string): string {
  return `calibracion_obj2_${id}`;
}

function leerSegundoObjeto(id: string): SegundoObjetoGuardado | null {
  try {
    const crudo = localStorage.getItem(claveSegundoObjeto(id));
    if (!crudo) {
      return null;
    }
    return JSON.parse(crudo) as SegundoObjetoGuardado;
  } catch {
    return null;
  }
}

export function CalibrarExcluir() {
  const { id = "" } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const [detalle, setDetalle] = useState<AnalisisDetalle | null>(null);
  const [estado, setEstado] = useState<EstadoAnalisis>("IMAGEN_CARGADA");
  const [error, setError] = useState("");
  const [ocupado, setOcupado] = useState(false);
  const [modo, setModo] = useState<Modo>("ninguno");

  const [linea, setLinea] = useState<Punto[]>([]);
  const [longitud, setLongitud] = useState("");
  const [unidad, setUnidad] = useState<Unidad>("mm");
  const [longitudCalibrada, setLongitudCalibrada] = useState<number | null>(null);

  const [usarSegundoObjeto, setUsarSegundoObjeto] = useState(false);
  const [linea2, setLinea2] = useState<Punto[]>([]);
  const [longitud2, setLongitud2] = useState("");
  const [unidad2, setUnidad2] = useState<Unidad>("mm");
  const [longitudCalibrada2, setLongitudCalibrada2] = useState<number | null>(null);

  const [factor, setFactor] = useState<number | null>(null);

  // Reanudar: se dibuja lo que ya guarda el servidor (también al refrescar la página).
  useEffect(() => {
    obtenerAnalisis(id)
      .then((datos) => {
        setDetalle(datos);
        setEstado(datos.estado);
        if (datos.calibracion) {
          setLinea([datos.calibracion.inicio, datos.calibracion.fin]);
          setFactor(datos.calibracion.factor_mm_por_px);
          const guardado2 = leerSegundoObjeto(id);
          if (guardado2 && guardado2.linea2.length === 2) {
            setUsarSegundoObjeto(true);
            setLongitud(guardado2.linea1Texto);
            setUnidad(guardado2.unidad1);
            setLongitudCalibrada(guardado2.longitudCalibrada1);
            setLinea2(guardado2.linea2);
            setLongitud2(guardado2.longitud2);
            setUnidad2(guardado2.unidad2);
            setLongitudCalibrada2(guardado2.longitudCalibrada2);
          } else {
            setLongitud(String(datos.calibracion.longitud_real_mm));
            setUnidad("mm");
            setLongitudCalibrada(datos.calibracion.longitud_real_mm);
          }
        }
      })
      .catch((e: unknown) => setError(mensajeDeError(e)));
  }, [id]);

  const ejecutar = async (accion: () => Promise<void>) => {
    setOcupado(true);
    setError("");
    try {
      await accion();
    } catch (e) {
      setError(mensajeDeError(e));
    } finally {
      setOcupado(false);
    }
  };

  const alClicImagen = (punto: Punto) => {
    if (modo === "linea" && linea.length < 2) {
      const nueva = [...linea, punto];
      setLinea(nueva);
      setFactor(null);
      if (nueva.length === 2) {
        setModo("ninguno");
      }
    } else if (modo === "linea2" && linea2.length < 2) {
      const nueva = [...linea2, punto];
      setLinea2(nueva);
      setFactor(null);
      if (nueva.length === 2) {
        setModo("ninguno");
      }
    }
  };

  const alMoverExtremo = (indice: number, punto: Punto) => {
    setLinea((actual) => actual.map((p, i) => (i === indice ? punto : p)));
    setFactor(null);
  };

  const alMoverExtremo2 = (indice: number, punto: Punto) => {
    setLinea2((actual) => actual.map((p, i) => (i === indice ? punto : p)));
    setFactor(null);
  };

  const trazarLinea = () => {
    setLinea([]);
    setFactor(null);
    setModo("linea");
  };

  const trazarLinea2 = () => {
    setLinea2([]);
    setFactor(null);
    setModo("linea2");
  };

  const agregarSegundoObjeto = () => {
    setUsarSegundoObjeto(true);
    setLinea2([]);
    setLongitud2("");
    setUnidad2("mm");
    setLongitudCalibrada2(null);
    setFactor(null);
    setModo("linea2");
  };

  const quitarSegundoObjeto = () => {
    setUsarSegundoObjeto(false);
    setLinea2([]);
    setLongitud2("");
    setLongitudCalibrada2(null);
    setFactor(null);
    if (modo === "linea2") {
      setModo("ninguno");
    }
    try {
      localStorage.removeItem(claveSegundoObjeto(id));
    } catch {
      // Ignorar si localStorage no está disponible.
    }
  };

  const longitudMm = aMilimetros(longitud, unidad);
  const longitudMm2 = aMilimetros(longitud2, unidad2);
  const longitudPx = distanciaLineaPx(linea);
  const longitudPx2 = distanciaLineaPx(linea2);

  const hacerCalibracion = () =>
    ejecutar(async () => {
      if (longitudMm === null || longitudPx === null) {
        return;
      }
      if (usarSegundoObjeto && (longitudMm2 === null || longitudPx2 === null)) {
        return;
      }
      const longitudEfectiva = usarSegundoObjeto
        ? calcularLongitudEfectivaMm(longitudPx, longitudMm, longitudPx2, longitudMm2)
        : longitudMm;

      const respuesta = await calibrar(id, linea[0], linea[1], longitudEfectiva);
      setFactor(respuesta.factor_mm_por_px);
      setLongitudCalibrada(longitudMm);
      setLongitudCalibrada2(usarSegundoObjeto ? longitudMm2 : null);
      setEstado(respuesta.estado);

      try {
        if (usarSegundoObjeto && longitudMm2 !== null) {
          const datos2: SegundoObjetoGuardado = {
            linea1Texto: longitud,
            unidad1: unidad,
            longitudCalibrada1: longitudMm,
            linea2,
            longitud2,
            unidad2,
            longitudCalibrada2: longitudMm2,
          };
          localStorage.setItem(claveSegundoObjeto(id), JSON.stringify(datos2));
        } else {
          localStorage.removeItem(claveSegundoObjeto(id));
        }
      } catch {
        // Ignorar errores de almacenamiento local.
      }
    });

  const cambiarLongitud = (texto: string, nuevaUnidad: Unidad = unidad) => {
    setLongitud(texto);
    setUnidad(nuevaUnidad);
    setFactor(null);
  };

  const cambiarLongitud2 = (texto: string, nuevaUnidad: Unidad = unidad2) => {
    setLongitud2(texto);
    setUnidad2(nuevaUnidad);
    setFactor(null);
  };

  const longitudValida = longitudMm !== null;
  const longitud2Valida = longitudMm2 !== null;
  const aviso = avisoLongitud(longitudMm);
  const aviso2 = avisoLongitud(longitudMm2);
  const calibrado = estado !== "IMAGEN_CARGADA";
  const segmentado = estado === "SEGMENTADO";
  const pendienteRecalibrar = calibrado && factor === null;
  const listoParaCalibrar =
    longitudPx !== null &&
    longitudValida &&
    (!usarSegundoObjeto || (longitudPx2 !== null && longitud2Valida));

  const ayuda =
    modo === "linea"
      ? `Haga clic en los dos extremos del objeto de referencia 1 (${linea.length} de 2).`
      : modo === "linea2"
        ? `Haga clic en los dos extremos del objeto de referencia 2 (${linea2.length} de 2).`
        : linea.length < 2
          ? "Pulse «Trazar línea» y marque los dos extremos del objeto de referencia."
          : usarSegundoObjeto && linea2.length < 2
            ? "Pulse «Trazar línea 2» y marque los dos extremos del segundo objeto de referencia."
            : factor === null
              ? "Arrastre los extremos para ajustar las líneas, ingrese la longitud real y pulse «Calibrar»."
              : "Calibración completa. Puede continuar con la segmentación.";
  const textoModo = {
    linea: "Línea objeto 1",
    linea2: "Línea objeto 2",
    ninguno: "Navegación",
  }[modo];
  const marcaTarea = (hecha: boolean, activa: boolean, numero: string) => (
    <span
      className={`calibrar__marca${hecha ? " calibrar__marca--hecha" : activa ? " calibrar__marca--activa" : ""}`}
    >
      {hecha ? <Icono nombre="hecho" /> : numero}
    </span>
  );

  return (
    <div className="calibrar">
      <Encabezado />
      <main className="calibrar__contenido">
        <IndicadorPasos actual={1} />
        <MensajeError mensaje={error} />

        <div className="calibrar__cuerpo">
          <section className="calibrar__lienzo" aria-label="Imagen del análisis">
            <div className="calibrar__barra-lienzo">
              <span className={`calibrar__modo calibrar__modo--${modo}`}>{textoModo}</span>
              <span className="calibrar__nombre-imagen">{detalle?.nombre ?? "Cargando..."}</span>
            </div>
            {detalle && (
              <LienzoCalibracion
                urlImagen={urlImagen(id)}
                anchoImg={detalle.imagen.ancho_px}
                altoImg={detalle.imagen.alto_px}
                linea={linea}
                lineaSecundaria={usarSegundoObjeto ? linea2 : []}
                region={[]}
                regionCerrada={false}
                aceptaClics={modo !== "ninguno"}
                onClicImagen={alClicImagen}
                onMoverExtremo={alMoverExtremo}
                onMoverExtremoSecundario={alMoverExtremo2}
              />
            )}
            <p className="calibrar__ayuda-lienzo" role="status">
              <Icono nombre="info" />
              {ayuda}
            </p>
          </section>

          <aside className="calibrar__panel">
            <section
              className={`calibrar__seccion${!calibrado ? " calibrar__seccion--activa" : ""}`}
              aria-labelledby="titulo-calibracion"
            >
              <div className="calibrar__cabecera">
                {marcaTarea(calibrado, !calibrado, "1")}
                <h2 id="titulo-calibracion" className="calibrar__subtitulo">
                  Calibración de escala
                </h2>
                <span className="calibrar__requisito">Requerido</span>
              </div>
              <p className="calibrar__ayuda">
                Marque los extremos de uno o dos objetos de referencia sobre la imagen e ingrese su longitud real.
              </p>

              {/* Objeto de referencia 1 */}
              <div className="calibrar__objeto-bloque">
                <div className="calibrar__fila calibrar__fila--separada">
                  <span className="calibrar__etiqueta">
                    <span className="calibrar__punto-color" aria-hidden="true" />{" "}
                    {usarSegundoObjeto ? "Objeto de referencia 1" : "Objeto de referencia"}
                  </span>
                  {longitudPx !== null && (
                    <span className="calibrar__ayuda cifra">{formatearNumero(longitudPx, 0)} px</span>
                  )}
                </div>
                <div className="calibrar__barra-trazo">
                  <Boton
                    variante="secundario"
                    className="calibrar__boton-trazo"
                    onClick={trazarLinea}
                    disabled={!detalle}
                  >
                    <Icono nombre="lapiz" />
                    {linea.length === 2
                      ? usarSegundoObjeto
                        ? "Volver a trazar línea 1"
                        : "Volver a trazar línea"
                      : usarSegundoObjeto
                        ? "Trazar línea 1"
                        : "Trazar línea"}
                  </Boton>
                </div>
                <label className="calibrar__etiqueta" htmlFor="longitud-real">
                  Longitud real
                </label>
                <div className="calibrar__fila">
                  <span className="calibrar__entrada">
                    <input
                      id="longitud-real"
                      className="calibrar__campo cifra"
                      type="text"
                      inputMode="decimal"
                      value={longitud}
                      aria-invalid={longitud !== "" && !longitudValida}
                      aria-describedby="longitud-ayuda"
                      onChange={(e: ChangeEvent<HTMLInputElement>) => cambiarLongitud(e.target.value)}
                    />
                    <select
                      className="calibrar__selector-unidad"
                      aria-label="Unidad"
                      value={unidad}
                      onChange={(e: ChangeEvent<HTMLSelectElement>) => cambiarLongitud(longitud, e.target.value as Unidad)}
                    >
                      {UNIDADES.map((u) => (
                        <option key={u} value={u}>
                          {u}
                        </option>
                      ))}
                    </select>
                  </span>
                </div>
                <p
                  id="longitud-ayuda"
                  className={`calibrar__ayuda${longitud !== "" && !longitudValida ? " calibrar__ayuda--error" : ""}`}
                >
                  {longitud !== "" && !longitudValida
                    ? "Ingrese un número mayor que cero."
                    : longitudMm !== null && unidad !== "mm"
                      ? `Equivale a ${formatearMm(longitudMm)}.`
                      : "Mida el objeto en la dirección de la línea trazada."}
                </p>
                {aviso && (
                  <p className="calibrar__aviso" role="status">
                    {aviso}
                  </p>
                )}
              </div>

              {/* Objeto de referencia 2 (opcional) */}
              {!usarSegundoObjeto ? (
                <Boton variante="secundario" onClick={agregarSegundoObjeto} disabled={!detalle || ocupado}>
                  <Icono nombre="mas" />
                  Agregar segundo objeto de referencia
                </Boton>
              ) : (
                <div className="calibrar__objeto-bloque">
                  <div className="calibrar__fila calibrar__fila--separada">
                    <span className="calibrar__etiqueta">
                      <span className="calibrar__punto-color calibrar__punto-color--secundario" aria-hidden="true" />{" "}
                      Objeto de referencia 2
                    </span>
                    {longitudPx2 !== null && (
                      <span className="calibrar__ayuda cifra">{formatearNumero(longitudPx2, 0)} px</span>
                    )}
                  </div>
                  <div className="calibrar__barra-trazo">
                    <Boton
                      variante="secundario"
                      className="calibrar__boton-trazo"
                      onClick={trazarLinea2}
                      disabled={!detalle}
                    >
                      <Icono nombre="lapiz" />
                      {linea2.length === 2 ? "Volver a trazar línea 2" : "Trazar línea 2"}
                    </Boton>
                  </div>
                  <label className="calibrar__etiqueta" htmlFor="longitud-real-2">
                    Longitud real del objeto 2
                  </label>
                  <div className="calibrar__fila">
                    <span className="calibrar__entrada">
                      <input
                        id="longitud-real-2"
                        className="calibrar__campo cifra"
                        type="text"
                        inputMode="decimal"
                        value={longitud2}
                        aria-invalid={longitud2 !== "" && !longitud2Valida}
                        aria-describedby="longitud-ayuda-2"
                        onChange={(e: ChangeEvent<HTMLInputElement>) => cambiarLongitud2(e.target.value)}
                      />
                      <select
                        className="calibrar__selector-unidad"
                        aria-label="Unidad objeto 2"
                        value={unidad2}
                        onChange={(e: ChangeEvent<HTMLSelectElement>) => cambiarLongitud2(longitud2, e.target.value as Unidad)}
                      >
                        {UNIDADES.map((u) => (
                          <option key={u} value={u}>
                            {u}
                          </option>
                        ))}
                      </select>
                    </span>
                  </div>
                  <p
                    id="longitud-ayuda-2"
                    className={`calibrar__ayuda${longitud2 !== "" && !longitud2Valida ? " calibrar__ayuda--error" : ""}`}
                  >
                    {longitud2 !== "" && !longitud2Valida
                      ? "Ingrese un número mayor que cero."
                      : longitudMm2 !== null && unidad2 !== "mm"
                        ? `Equivale a ${formatearMm(longitudMm2)}.`
                        : "Mida el segundo objeto en la dirección de la línea 2."}
                  </p>
                  {aviso2 && (
                    <p className="calibrar__aviso" role="status">
                      {aviso2}
                    </p>
                  )}
                  <Boton variante="peligro" onClick={quitarSegundoObjeto} disabled={ocupado}>
                    Quitar
                  </Boton>
                </div>
              )}

              <div className="calibrar__fila">
                <Boton
                  onClick={() => void hacerCalibracion()}
                  disabled={ocupado || !listoParaCalibrar}
                >
                  {calibrado ? "Recalibrar" : "Calibrar"}
                </Boton>
              </div>

              {pendienteRecalibrar && (
                <p className="calibrar__aviso" role="status">
                  Cambió la línea o la longitud: pulse «Recalibrar» para aplicar la nueva escala.
                  {segmentado && " Los tamaños de todos los fragmentos se recalculan con ella."}
                </p>
              )}
              {factor !== null && (
                <dl className="calibrar__resultado" role="status">
                  {usarSegundoObjeto && longitudPx2 !== null && longitudCalibrada2 !== null ? (
                    <>
                      <div>
                        <dt>Objeto 1</dt>
                        <dd className="cifra">
                          {longitudPx === null ? "—" : `${formatearNumero(longitudPx, 0)} px`} ·{" "}
                          {longitudCalibrada === null ? "—" : formatearMm(longitudCalibrada)}
                        </dd>
                      </div>
                      <div>
                        <dt>Objeto 2</dt>
                        <dd className="cifra">
                          {`${formatearNumero(longitudPx2, 0)} px`} · {formatearMm(longitudCalibrada2)}
                        </dd>
                      </div>
                      <div>
                        <dt>Factor promedio</dt>
                        <dd className="cifra">{formatearNumero(factor, 4)} mm/px</dd>
                      </div>
                    </>
                  ) : (
                    <>
                      <div>
                        <dt>Longitud trazada</dt>
                        <dd className="cifra">{longitudPx === null ? "—" : `${formatearNumero(longitudPx, 0)} px`}</dd>
                      </div>
                      <div>
                        <dt>Longitud real</dt>
                        <dd className="cifra">{longitudCalibrada === null ? "—" : formatearMm(longitudCalibrada)}</dd>
                      </div>
                      <div>
                        <dt>Factor de escala</dt>
                        <dd className="cifra">{formatearNumero(factor, 4)} mm/px</dd>
                      </div>
                    </>
                  )}
                </dl>
              )}
            </section>

            <div className="calibrar__fila">
              <Boton variante="secundario" onClick={() => navigate("/")}>
                Atrás
              </Boton>
              <Boton
                className="calibrar__continuar"
                onClick={() => navigate(`/analisis/${id}/editor`)}
                disabled={!calibrado || ocupado}
              >
                {calibrado ? "Continuar a segmentación" : "Se requiere calibración"}
                {calibrado && <Icono nombre="siguiente" />}
              </Boton>
            </div>
          </aside>
        </div>
      </main>
    </div>
  );
}
