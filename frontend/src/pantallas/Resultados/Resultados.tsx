import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { obtenerAnalisis, obtenerResultados, urlCsv, urlImagen, urlXlsx } from "../../api/analisis";
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
  // El informe PDF usa la plantilla de impresión (@media print): sin botones ni ayudas.
  const exportarPdf = () => window.print();

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
              <p className="resultados__meta no-imprimir">
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
              href={resultados ? urlXlsx(id) : undefined}
              title="Hojas Resumen, Curva y Fragmentos"
              download
            >
              <Icono nombre="descargar" />
              Exportar Excel
            </a>
            <a
              className={`boton boton--secundario${resultados ? "" : " resultados__enlace-boton--inactivo"}`}
              href={resultados ? urlCsv(id) : undefined}
              title="Tabla de fragmentos en CSV estándar (coma y punto decimal)"
              download
            >
              <Icono nombre="descargar" />
              CSV
            </a>
            <Boton onClick={exportarPdf} disabled={!resultados}>
              <Icono nombre="descargar" />
              Informe PDF
            </Boton>
          </div>
        </div>

        {resultados && detalle && (
          <>
            <section className="resultados__informe solo-imprimir" aria-label="Datos del informe">
              <table className="resultados__tabla resultados__tabla--ficha">
                <tbody>
                  <tr>
                    <th scope="row">Fecha</th>
                    <td>{formatearFecha(detalle.fecha_creacion)}</td>
                    <th scope="row">Resolución</th>
                    <td>
                      {detalle.imagen.ancho_px} × {detalle.imagen.alto_px} px
                    </td>
                  </tr>
                  <tr>
                    <th scope="row">Objeto de referencia</th>
                    <td>{detalle.calibracion ? formatearMm(detalle.calibracion.longitud_real_mm) : "—"}</td>
                    <th scope="row">Escala</th>
                    <td>
                      {detalle.calibracion ? `${formatearNumero(detalle.calibracion.factor_mm_por_px, 4)} mm/px` : "—"}
                    </td>
                  </tr>
                  <tr>
                    <th scope="row">Fragmentos medidos (N)</th>
                    <td>{resultados.numero_fragmentos}</td>
                    <th scope="row">Modelo</th>
                    <td>Rosin-Rammler (tramo 10 %–90 %)</td>
                  </tr>
                </tbody>
              </table>
              <table className="resultados__tabla resultados__tabla--resumen">
                <thead>
                  <tr>
                    <th>D20</th>
                    <th>D50</th>
                    <th>D60</th>
                    <th>D80</th>
                    <th>D90</th>
                    <th>
                      x<sub>c</sub>
                    </th>
                    <th>n</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td>{formatearMm(resultados.d20)}</td>
                    <td>{formatearMm(resultados.d50)}</td>
                    <td>{formatearMm(resultados.d60)}</td>
                    <td>{formatearMm(resultados.d80)}</td>
                    <td>{formatearMm(resultados.d90)}</td>
                    <td>{formatearMm(resultados.tamano_caracteristico_mm)}</td>
                    <td>{formatearNumero(resultados.indice_n, 2)}</td>
                  </tr>
                </tbody>
              </table>
            </section>

            <section className="resultados__indicadores no-imprimir" aria-label="Indicadores granulométricos">
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

            <div className="resultados__graficos resultados__graficos--curva">
              <section className="resultados__tarjeta">
                <h2 className="resultados__subtitulo">Curva granulométrica acumulada</h2>
                <GraficoCurva
                  curva={resultados.curva}
                  curvaTeorica={resultados.curva_teorica}
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
                <h2 className="resultados__subtitulo">Distribución por rango de tamaño</h2>
                <GraficoHistograma clases={resultados.histograma} rangos={resultados.rangos} />
              </section>
              <section className="resultados__tarjeta">
                <h2 className="resultados__subtitulo">Modelo de distribución</h2>
                <p className="resultados__ecuacion cifra">
                  P(x) = 1 − exp[−(x / x<sub>c</sub>)<sup>n</sup>]
                </p>
                <dl className="resultados__parametros">
                  <dt>
                    Tamaño característico, x<sub>c</sub> (63,2 % pasante)
                  </dt>
                  <dd className="cifra">{formatearMm(resultados.tamano_caracteristico_mm)}</dd>
                  <dt>Índice de uniformidad, n</dt>
                  <dd className="cifra">{formatearNumero(resultados.indice_n, 2)}</dd>
                  <dt>Fragmentos medidos, N</dt>
                  <dd className="cifra">{resultados.numero_fragmentos}</dd>
                </dl>
                <p className="resultados__nota">
                  Ajustado en el tramo central de la curva (10 %–90 % pasante). La línea punteada de la curva
                  acumulada es este modelo: si se aparta mucho de la medida, el ajuste es pobre.
                </p>
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

            <details className="resultados__tarjeta resultados__datos no-imprimir">
              <summary>Ver datos: rangos y tamaño de cada fragmento</summary>
              <h3 className="resultados__subtitulo">Por rango de tamaño</h3>
              <table className="resultados__tabla">
                <thead>
                  <tr>
                    <th>Rango</th>
                    <th>Tamaño</th>
                    <th>Fragmentos</th>
                    <th>% retenido (masa)</th>
                  </tr>
                </thead>
                <tbody>
                  {resultados.histograma.map((c, i) => (
                    <tr key={i}>
                      <td>{resultados.rangos[i]?.nombre}</td>
                      <td>{resultados.rangos[i] ? textoRango(resultados.rangos[i]) : ""}</td>
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
