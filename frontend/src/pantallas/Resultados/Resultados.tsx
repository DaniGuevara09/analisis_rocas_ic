import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { obtenerAnalisis, obtenerResultados, urlCsv, urlImagen } from "../../api/analisis";
import { mensajeDeError } from "../../api/errores";
import type { AnalisisDetalle, Resultados as DatosResultados } from "../../api/tipos";
import { Boton } from "../../componentes/Boton";
import { Encabezado } from "../../componentes/Encabezado";
import { Icono } from "../../componentes/Icono";
import { IndicadorPasos } from "../../componentes/IndicadorPasos";
import { colorPorFragmento, LeyendaRangos, textoRango } from "../../componentes/LeyendaRangos";
import { MensajeError } from "../../componentes/MensajeError";
import { GraficoCurva } from "../../graficos/GraficoCurva";
import { GraficoHistograma } from "../../graficos/GraficoHistograma";
import { VistaFragmentos } from "../../graficos/VistaFragmentos";
import { formatearFecha, formatearMm, formatearNumero } from "../../utilidades/formato";
import { type ClaveIndicador, DEFINICIONES, ORDEN_INDICADORES } from "./definiciones";
import "./Resultados.css";

export function Resultados() {
  const { id = "" } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [detalle, setDetalle] = useState<AnalisisDetalle | null>(null);
  const [resultados, setResultados] = useState<DatosResultados | null>(null);
  const [error, setError] = useState("");
  const datos = useRef<HTMLDetailsElement>(null);

  const exportarPdf = () => {
    // Las tablas de datos se incluyen en el informe aunque estén plegadas en pantalla.
    if (datos.current) {
      datos.current.open = true;
    }
    window.print();
  };

  useEffect(() => {
    Promise.all([obtenerAnalisis(id), obtenerResultados(id)])
      .then(([datos, calculo]) => {
        setDetalle(datos);
        setResultados(calculo);
      })
      .catch((e: unknown) => setError(mensajeDeError(e)));
  }, [id]);

  const colorPorId = useMemo(
    () => colorPorFragmento(resultados?.rangos ?? [], resultados?.fragmentos ?? []),
    [resultados],
  );
  const ordenados = useMemo(
    () => [...(resultados?.fragmentos ?? [])].sort((a, b) => b.diametro_equivalente_mm - a.diametro_equivalente_mm),
    [resultados],
  );

  const [seleccion, setSeleccion] = useState<ClaveIndicador>("d50");
  const definicion = DEFINICIONES[seleccion];
  const valorDe = (clave: ClaveIndicador): string =>
    resultados ? (clave === "indice_n" ? formatearNumero(resultados.indice_n, 2) : formatearMm(resultados[clave])) : "—";

  return (
    <div className="resultados">
      <div className="no-imprimir">
        <Encabezado />
      </div>
      <main className="resultados__contenido">
        <div className="no-imprimir">
          <IndicadorPasos actual={3} />
        </div>
        <MensajeError mensaje={error} />

        <div className="resultados__barra">
          <div>
            <p className="resultados__sobretitulo">Informe de análisis granulométrico</p>
            <h1 className="resultados__titulo">{detalle?.nombre ?? "Cargando..."}</h1>
            {detalle && (
              <p className="resultados__meta">
                {formatearFecha(detalle.fecha_creacion)} · Imagen {detalle.imagen.ancho_px}×{detalle.imagen.alto_px} px
                {detalle.calibracion &&
                  ` · Escala ${formatearNumero(detalle.calibracion.factor_mm_por_px, 4)} mm/px (objeto de ${formatearMm(detalle.calibracion.longitud_real_mm)})`}
                {resultados && ` · ${resultados.numero_fragmentos} fragmentos`}
              </p>
            )}
          </div>
          <div className="resultados__acciones no-imprimir">
            <Boton variante="secundario" onClick={() => navigate(`/analisis/${id}/editor`)}>
              Volver al editor
            </Boton>
            <a
              className={`boton boton--secundario${resultados ? "" : " resultados__enlace-boton--inactivo"}`}
              href={resultados ? urlCsv(id) : undefined}
              download
            >
              <Icono nombre="descargar" />
              Exportar CSV
            </a>
            <Boton onClick={exportarPdf} disabled={!resultados}>
              <Icono nombre="descargar" />
              Informe PDF
            </Boton>
          </div>
        </div>

        {resultados && detalle && (
          <>
            <section className="resultados__indicadores" aria-label="Indicadores granulométricos">
              {ORDEN_INDICADORES.map((clave) => (
                <button
                  key={clave}
                  type="button"
                  className={`resultados__indicador${seleccion === clave ? " resultados__indicador--activo" : ""}`}
                  aria-pressed={seleccion === clave}
                  onClick={() => setSeleccion(clave)}
                >
                  <span className="resultados__indicador-nombre">{DEFINICIONES[clave].nombre}</span>
                  <span className="resultados__indicador-valor cifra">{valorDe(clave)}</span>
                </button>
              ))}
            </section>

            <div className="resultados__graficos">
              <section className="resultados__tarjeta">
                <h2 className="resultados__subtitulo">Curva granulométrica acumulada</h2>
                <GraficoCurva
                  curva={resultados.curva}
                  referencias={
                    definicion.pasante_pct === null || seleccion === "indice_n"
                      ? []
                      : [{ etiqueta: definicion.nombre, diametro_mm: resultados[seleccion], pasante_pct: definicion.pasante_pct }]
                  }
                />
              </section>
              <section className="resultados__tarjeta resultados__definicion no-imprimir" aria-live="polite">
                <p className="resultados__sobretitulo resultados__sobretitulo--resaltado">Indicador seleccionado</p>
                <h2 className="resultados__definicion-titulo">
                  {definicion.nombre} <span className="cifra">= {valorDe(seleccion)}</span>
                </h2>
                <div className="resultados__bloque">
                  <span className="resultados__rotulo">Definición</span>
                  <p className="resultados__parrafo">{definicion.definicion}</p>
                </div>
                <div className="resultados__bloque resultados__bloque--separado">
                  <span className="resultados__rotulo">Aplicación</span>
                  <p className="resultados__parrafo">{definicion.aplicacion}</p>
                </div>
              </section>
            </div>

            <div className="resultados__graficos">
              <section className="resultados__tarjeta">
                <h2 className="resultados__subtitulo">Histograma de frecuencias</h2>
                <GraficoHistograma clases={resultados.histograma} />
              </section>
              <section className="resultados__tarjeta">
                <h2 className="resultados__subtitulo">Modelo de distribución</h2>
                <p className="resultados__ecuacion cifra">
                  P(x) = 1 − exp[−(x / x<sub>c</sub>)<sup>n</sup>]
                </p>
                <dl className="resultados__parametros">
                  <dt>Índice de uniformidad, n</dt>
                  <dd className="cifra">{formatearNumero(resultados.indice_n, 2)}</dd>
                  <dt>Fragmentos medidos, N</dt>
                  <dd className="cifra">{resultados.numero_fragmentos}</dd>
                </dl>
              </section>
            </div>

            <section className="resultados__tarjeta resultados__fragmentos">
              <div className="resultados__imagen">
                <h2 className="resultados__subtitulo">Fragmentos por rango de tamaño</h2>
                <VistaFragmentos
                  urlImagen={urlImagen(id)}
                  anchoImg={detalle.imagen.ancho_px}
                  altoImg={detalle.imagen.alto_px}
                  fragmentos={detalle.fragmentos}
                  colorPorId={colorPorId}
                />
              </div>
              <div className="resultados__lateral">
                <h3 className="resultados__subtitulo">Leyenda</h3>
                <p className="resultados__nota no-imprimir">
                  Los rangos y colores se cambian en <Link to="/configuracion">Configuración</Link>.
                </p>
                <LeyendaRangos rangos={resultados.rangos} fragmentos={resultados.fragmentos} />
                <h3 className="resultados__subtitulo">Supuestos y limitaciones</h3>
                <ul className="resultados__supuestos">
                  {resultados.supuestos.map((s) => (
                    <li key={s}>{s}</li>
                  ))}
                  <li>El resultado es una estimación y no reemplaza el tamizado.</li>
                </ul>
              </div>
            </section>

            <details ref={datos} className="resultados__tarjeta resultados__datos">
              <summary>Ver datos: histograma y tamaño de cada fragmento</summary>
              <h3 className="resultados__subtitulo">Histograma</h3>
              <table className="resultados__tabla">
                <thead>
                  <tr>
                    <th>Clase (mm)</th>
                    <th>Fragmentos</th>
                    <th>% retenido (masa)</th>
                  </tr>
                </thead>
                <tbody>
                  {resultados.histograma.map((c) => (
                    <tr key={c.limite_inferior_mm}>
                      <td>
                        {formatearNumero(c.limite_inferior_mm, 0)}–{formatearNumero(c.limite_superior_mm, 0)}
                      </td>
                      <td>{c.numero_fragmentos}</td>
                      <td>{formatearNumero(c.porcentaje_retenido, 1)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <h3 className="resultados__subtitulo">Fragmentos (de mayor a menor)</h3>
              <table className="resultados__tabla">
                <thead>
                  <tr>
                    <th>#</th>
                    <th>Diámetro equivalente</th>
                    <th>Rango</th>
                  </tr>
                </thead>
                <tbody>
                  {ordenados.map((f, i) => (
                    <tr key={f.id}>
                      <td>{i + 1}</td>
                      <td>{formatearMm(f.diametro_equivalente_mm)}</td>
                      <td>{textoRango(resultados.rangos[f.indice_rango])}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </details>
          </>
        )}
      </main>
    </div>
  );
}
