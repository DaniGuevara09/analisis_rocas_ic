import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { obtenerAnalisis, obtenerResultados, urlImagen } from "../../api/analisis";
import { mensajeDeError } from "../../api/errores";
import type { AnalisisDetalle, Resultados as DatosResultados } from "../../api/tipos";
import { Boton } from "../../componentes/Boton";
import { Encabezado } from "../../componentes/Encabezado";
import { IndicadorPasos } from "../../componentes/IndicadorPasos";
import { LeyendaRangos, textoRango } from "../../componentes/LeyendaRangos";
import { MensajeError } from "../../componentes/MensajeError";
import { GraficoCurva } from "../../graficos/GraficoCurva";
import { GraficoHistograma } from "../../graficos/GraficoHistograma";
import { VistaFragmentos } from "../../graficos/VistaFragmentos";
import { formatearFecha, formatearMm, formatearNumero } from "../../utilidades/formato";
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

  const rangoPorId = useMemo(
    () => new Map((resultados?.fragmentos ?? []).map((f) => [f.id, f.indice_rango])),
    [resultados],
  );
  const ordenados = useMemo(
    () => [...(resultados?.fragmentos ?? [])].sort((a, b) => b.diametro_equivalente_mm - a.diametro_equivalente_mm),
    [resultados],
  );

  const indicadores = resultados
    ? ([
        ["D20", formatearMm(resultados.d20)],
        ["D50", formatearMm(resultados.d50)],
        ["D60", formatearMm(resultados.d60)],
        ["D80", formatearMm(resultados.d80)],
        ["D90", formatearMm(resultados.d90)],
        ["Índice n", formatearNumero(resultados.indice_n, 2)],
      ] as const)
    : [];

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
            <Boton onClick={exportarPdf} disabled={!resultados}>
              Exportar PDF
            </Boton>
          </div>
        </div>

        {resultados && detalle && (
          <>
            <section className="resultados__indicadores" aria-label="Indicadores granulométricos">
              {indicadores.map(([nombre, valor]) => (
                <div key={nombre} className="resultados__indicador">
                  <span className="resultados__indicador-nombre">{nombre}</span>
                  <span className="resultados__indicador-valor">{valor}</span>
                </div>
              ))}
            </section>

            <div className="resultados__graficos">
              <section className="resultados__tarjeta">
                <h2 className="resultados__subtitulo">Curva granulométrica</h2>
                <GraficoCurva
                  curva={resultados.curva}
                  referencias={[
                    { etiqueta: "D50", diametro_mm: resultados.d50, pasante_pct: 50 },
                    { etiqueta: "D80", diametro_mm: resultados.d80, pasante_pct: 80 },
                  ]}
                />
              </section>
              <section className="resultados__tarjeta">
                <h2 className="resultados__subtitulo">Histograma</h2>
                <GraficoHistograma clases={resultados.histograma} />
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
                  rangoPorId={rangoPorId}
                />
              </div>
              <div className="resultados__lateral">
                <h3 className="resultados__subtitulo">Leyenda</h3>
                <LeyendaRangos rangos={resultados.rangos} fragmentos={resultados.fragmentos} />
                <h3 className="resultados__subtitulo">Supuestos del cálculo</h3>
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
