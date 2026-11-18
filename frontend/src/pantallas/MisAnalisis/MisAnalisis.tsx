import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { eliminarAnalisis, listarAnalisis } from "../../api/analisis";
import { mensajeDeError } from "../../api/errores";
import type { AnalisisResumen, EstadoAnalisis } from "../../api/tipos";
import { Boton } from "../../componentes/Boton";
import { Encabezado } from "../../componentes/Encabezado";
import { EtiquetaEstado } from "../../componentes/EtiquetaEstado";
import { MensajeError } from "../../componentes/MensajeError";
import { ModalConfirmacion } from "../../componentes/ModalConfirmacion";
import { formatearFecha } from "../../utilidades/formato";
import "./MisAnalisis.css";

type FiltroEstado = EstadoAnalisis | "TODOS";

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
          <h1 className="mis-analisis__titulo">Mis análisis</h1>
          <Boton onClick={() => navigate("/analisis/nuevo")}>+ Nuevo análisis</Boton>
        </div>

        <div className="mis-analisis__filtros">
          <input
            type="search"
            className="mis-analisis__campo"
            placeholder="Buscar por nombre"
            aria-label="Buscar por nombre"
            value={busqueda}
            onChange={(e) => setBusqueda(e.target.value)}
          />
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
        </div>

        <MensajeError mensaje={error} />

        {cargando ? (
          <p className="mis-analisis__aviso">Cargando análisis...</p>
        ) : analisis.length === 0 ? (
          <p className="mis-analisis__aviso">Aún no hay análisis</p>
        ) : visibles.length === 0 ? (
          <p className="mis-analisis__aviso">Ningún análisis coincide con la búsqueda</p>
        ) : (
          <table className="mis-analisis__tabla">
            <thead>
              <tr>
                <th>Nombre</th>
                <th>Fecha</th>
                <th>Estado</th>
                <th>Fragmentos</th>
                <th>Acciones</th>
              </tr>
            </thead>
            <tbody>
              {visibles.map((a) => (
                <tr key={a.id}>
                  <td>{a.nombre}</td>
                  <td>{formatearFecha(a.fecha_creacion)}</td>
                  <td>
                    <EtiquetaEstado estado={a.estado} />
                  </td>
                  <td>{a.numero_fragmentos}</td>
                  <td className="mis-analisis__acciones">
                    <Boton variante="secundario" onClick={() => navigate(`/analisis/${a.id}/calibracion`)}>
                      Abrir
                    </Boton>
                    <Boton variante="peligro" onClick={() => setPorEliminar(a)}>
                      Eliminar
                    </Boton>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
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
