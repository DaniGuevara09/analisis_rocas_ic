import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { eliminarAnalisis, listarAnalisis } from "../../api/analisis";
import { mensajeDeError } from "../../api/errores";
import type { AnalisisResumen, EstadoAnalisis } from "../../api/tipos";
import { Boton } from "../../componentes/Boton";
import { Encabezado } from "../../componentes/Encabezado";
import { Icono } from "../../componentes/Icono";
import { PASOS } from "../../componentes/IndicadorPasos";
import { MensajeError } from "../../componentes/MensajeError";
import { ModalConfirmacion } from "../../componentes/ModalConfirmacion";
import { formatearFecha } from "../../utilidades/formato";
import "./MisAnalisis.css";

type FiltroEstado = EstadoAnalisis | "TODOS";

const DESCRIPCION_PASOS = [
  "JPG/PNG con objeto de referencia visible.",
  "Factor mm/px a partir de una longitud conocida.",
  "Detección automática y edición manual de contornos.",
  "Curva, histograma, D20–D90 e índice n.",
];

/** Pantalla donde el operador retoma el análisis según su avance. */
function rutaDeContinuacion(analisis: AnalisisResumen): string {
  return analisis.estado === "IMAGEN_CARGADA"
    ? `/analisis/${analisis.id}/calibracion`
    : `/analisis/${analisis.id}/editor`;
}

function tieneResultados(analisis: AnalisisResumen): boolean {
  return analisis.estado === "SEGMENTADO" && analisis.numero_fragmentos >= 3;
}

/** Etapas completadas (1 a 4) según el estado que informa la API. */
function etapasCompletadas(analisis: AnalisisResumen): number {
  if (tieneResultados(analisis)) {
    return 4;
  }
  return { IMAGEN_CARGADA: 1, CALIBRADO: 2, SEGMENTADO: 3 }[analisis.estado];
}

function textoEtapa(analisis: AnalisisResumen): string {
  const hechas = etapasCompletadas(analisis);
  return hechas === 4 ? "Resultados disponibles" : PASOS[hechas];
}

export function MisAnalisis() {
  const navigate = useNavigate();
  const [analisis, setAnalisis] = useState<AnalisisResumen[]>([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState("");
  const [busqueda, setBusqueda] = useState("");
  const [filtro, setFiltro] = useState<FiltroEstado>("TODOS");
  const [porEliminar, setPorEliminar] = useState<AnalisisResumen | null>(null);

  const cargar = useCallback(async () => {
    setCargando(true);
    try {
      setAnalisis(await listarAnalisis());
      setError("");
    } catch (e) {
      setError(mensajeDeError(e));
    } finally {
      setCargando(false);
    }
  }, []);

  useEffect(() => {
    void cargar();
  }, [cargar]);

  const visibles = useMemo(() => {
    const texto = busqueda.trim().toLowerCase();
    return analisis.filter(
      (a) => a.nombre.toLowerCase().includes(texto) && (filtro === "TODOS" || a.estado === filtro),
    );
  }, [analisis, busqueda, filtro]);

  const confirmarEliminar = async () => {
    if (!porEliminar) {
      return;
    }
    const objetivo = porEliminar;
    setPorEliminar(null);
    try {
      await eliminarAnalisis(objetivo.id);
      await cargar();
    } catch (e) {
      setError(mensajeDeError(e));
    }
  };

  return (
    <div className="mis-analisis">
      <Encabezado />
      <main className="mis-analisis__contenido">
        <div className="mis-analisis__barra">
          <div className="mis-analisis__presentacion">
            <h1 className="mis-analisis__titulo">Análisis</h1>
            <p className="mis-analisis__descripcion">
              Estimación de la distribución granulométrica de material fragmentado a partir de fotografías, con
              segmentación automática (YOLOv11m-seg) y ajuste Rosin-Rammler.
            </p>
          </div>
          <div className="mis-analisis__botones">
            <Boton variante="secundario" onClick={() => navigate("/configuracion")}>
              <Icono nombre="ajustes" />
              Configurar rangos
            </Boton>
            <Boton onClick={() => navigate("/analisis/nuevo")}>
              <Icono nombre="mas" />
              Nuevo análisis
            </Boton>
          </div>
        </div>

        <ol className="mis-analisis__flujo" aria-label="Flujo de trabajo">
          {PASOS.map((nombre, indice) => (
            <li key={nombre} className="mis-analisis__etapa">
              <span className="mis-analisis__etapa-numero cifra">{String(indice + 1).padStart(2, "0")}</span>
              <span className="mis-analisis__etapa-texto">
                <strong>{nombre}</strong>
                <span>{DESCRIPCION_PASOS[indice]}</span>
              </span>
            </li>
          ))}
        </ol>

        <section className="mis-analisis__registros" aria-labelledby="titulo-registros">
          <div className="mis-analisis__filtros">
            <h2 id="titulo-registros" className="mis-analisis__subtitulo">
              Registros
            </h2>
            <div className="mis-analisis__controles">
              <select
                className="mis-analisis__campo"
                aria-label="Filtrar por estado"
                value={filtro}
                onChange={(e) => setFiltro(e.target.value as FiltroEstado)}
              >
                <option value="TODOS">Todos los estados</option>
                <option value="IMAGEN_CARGADA">Imagen cargada</option>
                <option value="CALIBRADO">Calibrado</option>
                <option value="SEGMENTADO">Segmentado</option>
              </select>
              <input
                type="search"
                className="mis-analisis__campo"
                placeholder="Buscar por nombre"
                aria-label="Buscar por nombre"
                value={busqueda}
                onChange={(e) => setBusqueda(e.target.value)}
              />
            </div>
          </div>

          <MensajeError mensaje={error} />

          {cargando ? (
            <p className="mis-analisis__aviso">Cargando análisis...</p>
          ) : analisis.length === 0 ? (
            <p className="mis-analisis__aviso">Aún no hay análisis. Use “Nuevo análisis” para comenzar.</p>
          ) : visibles.length === 0 ? (
            <p className="mis-analisis__aviso">Ningún análisis coincide con la búsqueda</p>
          ) : (
            <div className="mis-analisis__desplazable">
              <table className="mis-analisis__tabla">
                <thead>
                  <tr>
                    <th>Nombre</th>
                    <th>Fecha</th>
                    <th>Etapa</th>
                    <th className="mis-analisis__numero">Fragmentos</th>
                    <th>
                      <span className="mis-analisis__oculto">Acciones</span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {visibles.map((a) => {
                    const hechas = etapasCompletadas(a);
                    const completo = hechas === 4;
                    return (
                      <tr key={a.id}>
                        <td className="mis-analisis__nombre">{a.nombre}</td>
                        <td className="mis-analisis__secundario">{formatearFecha(a.fecha_creacion)}</td>
                        <td>
                          <span className="mis-analisis__etapa-fila">
                            <span
                              className={`mis-analisis__punto${completo ? " mis-analisis__punto--completo" : ""}`}
                            />
                            {textoEtapa(a)}
                          </span>
                          <span className="mis-analisis__avance" aria-label={`${hechas} de 4 etapas`}>
                            {PASOS.map((nombre, i) => (
                              <span
                                key={nombre}
                                className={`mis-analisis__segmento${
                                  i < hechas ? (completo ? " mis-analisis__segmento--completo" : " mis-analisis__segmento--hecho") : ""
                                }`}
                              />
                            ))}
                          </span>
                        </td>
                        <td className="mis-analisis__numero cifra">{a.numero_fragmentos}</td>
                        <td>
                          <span className="mis-analisis__acciones">
                            {completo ? (
                              <Boton variante="secundario" onClick={() => navigate(`/analisis/${a.id}/resultados`)}>
                                Ver informe
                              </Boton>
                            ) : (
                              <Boton variante="secundario" onClick={() => navigate(rutaDeContinuacion(a))}>
                                Continuar
                              </Boton>
                            )}
                            {completo && (
                              <Boton variante="secundario" onClick={() => navigate(rutaDeContinuacion(a))}>
                                Editar
                              </Boton>
                            )}
                            <Boton
                              variante="peligro"
                              aria-label={`Eliminar ${a.nombre}`}
                              title="Eliminar"
                              onClick={() => setPorEliminar(a)}
                            >
                              <Icono nombre="papelera" />
                            </Boton>
                          </span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </main>

      {porEliminar && (
        <ModalConfirmacion
          titulo="Eliminar análisis"
          mensaje={`¿Eliminar "${porEliminar.nombre}"? Se borrará también su imagen y no se puede deshacer.`}
          textoConfirmar="Eliminar"
          onConfirmar={() => void confirmarEliminar()}
          onCancelar={() => setPorEliminar(null)}
        />
      )}
    </div>
  );
}
