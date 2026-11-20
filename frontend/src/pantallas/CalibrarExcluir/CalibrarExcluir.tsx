import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { calibrar, excluirRegion, obtenerAnalisis, quitarRegion, urlImagen } from "../../api/analisis";
import { mensajeDeError } from "../../api/errores";
import type { AnalisisDetalle, EstadoAnalisis, Punto } from "../../api/tipos";
import { Boton } from "../../componentes/Boton";
import { Encabezado } from "../../componentes/Encabezado";
import { Icono } from "../../componentes/Icono";
import { IndicadorPasos } from "../../componentes/IndicadorPasos";
import { MensajeError } from "../../componentes/MensajeError";
import { ModalConfirmacion } from "../../componentes/ModalConfirmacion";
import { LienzoCalibracion } from "../../editor/LienzoCalibracion";
import { formatearMm, formatearNumero } from "../../utilidades/formato";
import { aMilimetros, avisoLongitud, OBJETOS_REFERENCIA, type Unidad, UNIDADES } from "./longitud";
import "./CalibrarExcluir.css";

type Modo = "ninguno" | "linea" | "region";

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
  const [factor, setFactor] = useState<number | null>(null);

  const [region, setRegion] = useState<Punto[]>([]);
  const [regionCerrada, setRegionCerrada] = useState(false);
  const [regionGuardada, setRegionGuardada] = useState(false);
  const [confirmarDescarte, setConfirmarDescarte] = useState(false);

  // Reanudar: se dibuja lo que ya guarda el servidor (también al refrescar la página).
  useEffect(() => {
    obtenerAnalisis(id)
      .then((datos) => {
        setDetalle(datos);
        setEstado(datos.estado);
        if (datos.calibracion) {
          setLinea([datos.calibracion.inicio, datos.calibracion.fin]);
          setLongitud(String(datos.calibracion.longitud_real_mm));
          setUnidad("mm");
          setLongitudCalibrada(datos.calibracion.longitud_real_mm);
          setFactor(datos.calibracion.factor_mm_por_px);
        }
        if (datos.region_excluida) {
          setRegion(datos.region_excluida.poligono);
          setRegionCerrada(true);
          setRegionGuardada(true);
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
    } else if (modo === "region" && !regionCerrada) {
      setRegion([...region, punto]);
      setRegionGuardada(false);
    }
  };

  const alMoverExtremo = (indice: number, punto: Punto) => {
    setLinea((actual) => actual.map((p, i) => (i === indice ? punto : p)));
    setFactor(null);
  };

  const trazarLinea = () => {
    setLinea([]);
    setFactor(null);
    setModo("linea");
  };

  const longitudMm = aMilimetros(longitud, unidad);

  const hacerCalibracion = () =>
    ejecutar(async () => {
      if (longitudMm === null) {
        return;
      }
      const respuesta = await calibrar(id, linea[0], linea[1], longitudMm);
      setFactor(respuesta.factor_mm_por_px);
      setLongitudCalibrada(longitudMm);
      setEstado(respuesta.estado);
    });

  const cambiarLongitud = (texto: string, nuevaUnidad: Unidad = unidad) => {
    setLongitud(texto);
    setUnidad(nuevaUnidad);
    setFactor(null);
  };

  const marcarRegion = () => {
    setRegion([]);
    setRegionCerrada(false);
    setRegionGuardada(false);
    setModo("region");
  };

  const cerrarRegion = () =>
    ejecutar(async () => {
      setRegionCerrada(true);
      setModo("ninguno");
      await excluirRegion(id, region);
      setRegionGuardada(true);
    });

  const deshacerPunto = () => {
    setRegion(region.slice(0, -1));
    setRegionGuardada(false);
    if (regionCerrada) {
      setRegionCerrada(false);
      setModo("region");
    }
  };

  const guardarRegion = () =>
    ejecutar(async () => {
      await excluirRegion(id, region);
      setRegionGuardada(true);
    });

  const quitarLaRegion = () =>
    ejecutar(async () => {
      await quitarRegion(id);
      setRegion([]);
      setRegionCerrada(false);
      setRegionGuardada(false);
      setModo("ninguno");
    });

  const longitudValida = longitudMm !== null;
  const aviso = avisoLongitud(longitudMm);
  const calibrado = estado !== "IMAGEN_CARGADA";
  const segmentado = estado === "SEGMENTADO";
  const pendienteRecalibrar = calibrado && factor === null;
  const longitudPx = linea.length === 2 ? Math.hypot(linea[1].x - linea[0].x, linea[1].y - linea[0].y) : null;

  const ayuda =
    modo === "linea"
      ? `Haga clic en los dos extremos del objeto de referencia (${linea.length} de 2).`
      : modo === "region"
        ? "Haga clic en los vértices alrededor del objeto de referencia y pulse «Cerrar y guardar región»."
        : linea.length < 2
          ? "Pulse «Trazar línea» y marque los dos extremos del objeto de referencia."
          : factor === null
            ? "Arrastre los extremos para ajustar la línea, ingrese la longitud real y pulse «Calibrar»."
            : !regionGuardada
              ? "Escala calibrada. Si el objeto de referencia está entre las rocas, delimítelo para excluirlo del conteo."
              : "Calibración completa. Puede continuar con la segmentación.";
  const textoModo = { linea: "Línea de escala", region: "Delimitar región", ninguno: "Navegación" }[modo];
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
                region={region}
                regionCerrada={regionCerrada}
                aceptaClics={modo !== "ninguno"}
                onClicImagen={alClicImagen}
                onMoverExtremo={alMoverExtremo}
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
                Marque los extremos del objeto de referencia sobre la imagen e ingrese su longitud real.
              </p>
              <Boton variante="secundario" onClick={trazarLinea} disabled={!detalle}>
                {linea.length === 2 ? "Volver a trazar línea" : "Trazar línea"}
              </Boton>
              <span className="calibrar__etiqueta">Objeto de referencia</span>
              <div className="calibrar__objetos" role="group" aria-label="Objetos de referencia frecuentes">
                {OBJETOS_REFERENCIA.map((objeto) => {
                  const activo = aMilimetros(String(objeto.valor), objeto.unidad) === longitudMm && unidad === objeto.unidad;
                  return (
                    <button
                      key={objeto.nombre}
                      type="button"
                      className={`calibrar__objeto${activo ? " calibrar__objeto--activo" : ""}`}
                      aria-pressed={activo}
                      onClick={() => cambiarLongitud(String(objeto.valor), objeto.unidad)}
                    >
                      {objeto.nombre}
                    </button>
                  );
                })}
              </div>
              <label className="calibrar__etiqueta" htmlFor="longitud-real">
                Longitud real (u otro objeto)
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
                    onChange={(e) => cambiarLongitud(e.target.value)}
                  />
                  <select
                    className="calibrar__selector-unidad"
                    aria-label="Unidad"
                    value={unidad}
                    onChange={(e) => cambiarLongitud(longitud, e.target.value as Unidad)}
                  >
                    {UNIDADES.map((u) => (
                      <option key={u} value={u}>
                        {u}
                      </option>
                    ))}
                  </select>
                </span>
                <Boton
                  onClick={() => void hacerCalibracion()}
                  disabled={ocupado || linea.length < 2 || !longitudValida}
                >
                  {calibrado ? "Recalibrar" : "Calibrar"}
                </Boton>
              </div>
              <p id="longitud-ayuda" className={`calibrar__ayuda${longitud !== "" && !longitudValida ? " calibrar__ayuda--error" : ""}`}>
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
              {pendienteRecalibrar && (
                <p className="calibrar__aviso" role="status">
                  Cambió la línea o la longitud: pulse «Recalibrar» para aplicar la nueva escala.
                  {segmentado && " Los tamaños de todos los fragmentos se recalculan con ella."}
                </p>
              )}
              {factor !== null && (
                <dl className="calibrar__resultado" role="status">
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
                </dl>
              )}
            </section>

            <section
              className={`calibrar__seccion${calibrado && !regionGuardada ? " calibrar__seccion--activa" : ""}`}
              aria-labelledby="titulo-exclusion"
            >
              <div className="calibrar__cabecera">
                {marcaTarea(regionGuardada, calibrado && !regionGuardada, "2")}
                <h2 id="titulo-exclusion" className="calibrar__subtitulo">
                  Exclusión del objeto de referencia
                </h2>
                <span className="calibrar__requisito">Recomendado</span>
              </div>
              <p className="calibrar__ayuda">
                <strong>¿Es necesario?</strong> Sí, si el objeto de referencia aparece sobre o entre las rocas: el modelo
                lo detectaría como un fragmento más y alteraría la curva. Puede omitirse si el objeto está fuera de la
                pila. Los fragmentos cuyo centro cae dentro de la región no se cuentan.
              </p>
              {regionGuardada ? (
                <div className="calibrar__fila calibrar__fila--separada">
                  <span className="calibrar__exito" role="status">
                    <Icono nombre="hecho" />
                    Región excluida guardada
                  </span>
                  <Boton variante="peligro" onClick={() => setConfirmarDescarte(true)} disabled={ocupado}>
                    Eliminar región
                  </Boton>
                </div>
              ) : (
                <>
                  <div className="calibrar__fila">
                    {modo === "region" ? (
                      <Boton onClick={() => void cerrarRegion()} disabled={ocupado || region.length < 3}>
                        Cerrar y guardar región
                      </Boton>
                    ) : regionCerrada ? (
                      <Boton onClick={() => void guardarRegion()} disabled={ocupado}>
                        Reintentar guardar región
                      </Boton>
                    ) : (
                      <Boton variante="secundario" onClick={marcarRegion} disabled={!detalle}>
                        Delimitar región
                      </Boton>
                    )}
                    {region.length > 0 && (
                      <Boton variante="secundario" onClick={deshacerPunto}>
                        <Icono nombre="deshacer" />
                        Deshacer vértice
                      </Boton>
                    )}
                  </div>
                  {region.length > 0 && (
                    <Boton variante="peligro" onClick={() => setConfirmarDescarte(true)} disabled={ocupado}>
                      Descartar región
                    </Boton>
                  )}
                </>
              )}
            </section>

            <div className="calibrar__fila">
              <Boton variante="secundario" onClick={() => navigate("/")}>
                Atrás
              </Boton>
              <Boton
                className="calibrar__continuar"
                onClick={() => navigate(`/analisis/${id}/editor`)}
                disabled={!calibrado || ocupado || modo === "region"}
              >
                {calibrado ? "Continuar a segmentación" : "Se requiere calibración"}
                {calibrado && <Icono nombre="siguiente" />}
              </Boton>
            </div>
          </aside>
        </div>
      </main>

      {confirmarDescarte && (
        <ModalConfirmacion
          titulo="Descartar la región excluida"
          mensaje="Sin esta región, si el objeto de referencia está entre las rocas, el modelo lo contará como un fragmento y alterará la curva y los indicadores. Descártela solo si el objeto está fuera de la pila."
          textoConfirmar="Descartar región"
          onConfirmar={() => {
            setConfirmarDescarte(false);
            void quitarLaRegion();
          }}
          onCancelar={() => setConfirmarDescarte(false)}
        />
      )}
    </div>
  );
}
