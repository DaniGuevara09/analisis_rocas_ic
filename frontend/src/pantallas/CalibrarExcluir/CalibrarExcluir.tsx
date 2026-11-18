import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { calibrar, excluirRegion, obtenerAnalisis, quitarRegion, urlImagen } from "../../api/analisis";
import { mensajeDeError } from "../../api/errores";
import type { AnalisisDetalle, EstadoAnalisis, Punto } from "../../api/tipos";
import { Boton } from "../../componentes/Boton";
import { Encabezado } from "../../componentes/Encabezado";
import { EtiquetaEstado } from "../../componentes/EtiquetaEstado";
import { IndicadorPasos } from "../../componentes/IndicadorPasos";
import { MensajeError } from "../../componentes/MensajeError";
import { LienzoCalibracion } from "../../editor/LienzoCalibracion";
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
  const [factor, setFactor] = useState<number | null>(null);

  const [region, setRegion] = useState<Punto[]>([]);
  const [regionCerrada, setRegionCerrada] = useState(false);
  const [regionGuardada, setRegionGuardada] = useState(false);

  // Reanudar: se dibuja lo que ya guarda el servidor (también al refrescar la página).
  useEffect(() => {
    obtenerAnalisis(id)
      .then((datos) => {
        setDetalle(datos);
        setEstado(datos.estado);
        if (datos.calibracion) {
          setLinea([datos.calibracion.inicio, datos.calibracion.fin]);
          setLongitud(String(datos.calibracion.longitud_real_mm));
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

  const hacerCalibracion = () =>
    ejecutar(async () => {
      const respuesta = await calibrar(id, linea[0], linea[1], Number(longitud));
      setFactor(respuesta.factor_mm_por_px);
      setEstado(respuesta.estado);
    });

  const marcarRegion = () => {
    setRegion([]);
    setRegionCerrada(false);
    setRegionGuardada(false);
    setModo("region");
  };

  const cerrarRegion = () => {
    setRegionCerrada(true);
    setModo("ninguno");
  };

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

  const longitudValida = Number(longitud) > 0;
  const ayuda =
    modo === "linea"
      ? `Haga clic en los dos extremos del objeto de escala (${linea.length} de 2).`
      : modo === "region"
        ? "Haga clic para agregar vértices alrededor del objeto de escala y luego cierre la región."
        : "";

  return (
    <div className="calibrar">
      <Encabezado />
      <main className="calibrar__contenido">
        <IndicadorPasos actual={1} />
        <MensajeError mensaje={error} />

        <div className="calibrar__cuerpo">
          <section className="calibrar__lienzo" aria-label="Imagen del análisis">
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
          </section>

          <aside className="calibrar__panel">
            <div className="calibrar__encabezado-panel">
              <h1 className="calibrar__nombre">{detalle?.nombre ?? "Cargando..."}</h1>
              <EtiquetaEstado estado={estado} />
            </div>
            {ayuda && <p className="calibrar__ayuda">{ayuda}</p>}

            <section className="calibrar__seccion">
              <h2 className="calibrar__subtitulo">Calibración</h2>
              <Boton variante="secundario" onClick={trazarLinea} disabled={!detalle}>
                Trazar línea
              </Boton>
              <label className="calibrar__etiqueta" htmlFor="longitud-real">
                Longitud real (mm)
              </label>
              <input
                id="longitud-real"
                className="calibrar__campo"
                type="number"
                min="0"
                step="any"
                value={longitud}
                onChange={(e) => setLongitud(e.target.value)}
              />
              <Boton
                onClick={() => void hacerCalibracion()}
                disabled={ocupado || linea.length < 2 || !longitudValida}
              >
                Calibrar
              </Boton>
              {factor !== null && (
                <p className="calibrar__resultado">Factor de escala: {factor} mm/px</p>
              )}
            </section>

            <section className="calibrar__seccion">
              <h2 className="calibrar__subtitulo">Exclusión del objeto de escala</h2>
              <Boton variante="secundario" onClick={marcarRegion} disabled={!detalle}>
                Marcar región
              </Boton>
              <div className="calibrar__fila">
                <Boton
                  variante="secundario"
                  onClick={cerrarRegion}
                  disabled={modo !== "region" || region.length < 3}
                >
                  Cerrar región
                </Boton>
                <Boton variante="secundario" onClick={deshacerPunto} disabled={region.length === 0}>
                  Deshacer último punto
                </Boton>
              </div>
              <div className="calibrar__fila">
                <Boton
                  onClick={() => void guardarRegion()}
                  disabled={ocupado || !regionCerrada || regionGuardada}
                >
                  Guardar región
                </Boton>
                <Boton
                  variante="peligro"
                  onClick={() => void quitarLaRegion()}
                  disabled={ocupado || (region.length === 0 && !regionGuardada)}
                >
                  Quitar región
                </Boton>
              </div>
              {regionGuardada && <p className="calibrar__resultado">Región guardada</p>}
            </section>

            <section className="calibrar__seccion">
              <Boton disabled>Segmentar</Boton>
              <p className="calibrar__ayuda">Disponible en el Sprint 3</p>
            </section>

            <Boton variante="secundario" onClick={() => navigate("/")}>
              Atrás
            </Boton>
          </aside>
        </div>
      </main>
    </div>
  );
}
