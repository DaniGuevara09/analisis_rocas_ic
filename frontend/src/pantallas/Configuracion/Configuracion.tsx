import { useEffect, useState } from "react";

import {
  guardarConfiguracionRangos,
  obtenerConfiguracionRangos,
  restablecerConfiguracionRangos,
} from "../../api/analisis";
import { mensajeDeError } from "../../api/errores";
import type { ConfiguracionRangos, ModoRangos } from "../../api/tipos";
import { Boton } from "../../componentes/Boton";
import { Encabezado } from "../../componentes/Encabezado";
import { MensajeError } from "../../componentes/MensajeError";
import { ModalConfirmacion } from "../../componentes/ModalConfirmacion";
import { leerToken } from "../../tema/leerTokens";
import { formatearNumero } from "../../utilidades/formato";
import {
  MAXIMO_RANGOS,
  MINIMO_RANGOS,
  agregarRango,
  cambiarEnLista,
  cambiarModo,
  problemaDeConfiguracion,
  quitarRango,
} from "./edicionRangos";
import "./Configuracion.css";

const UNIDAD: Record<ModoRangos, string> = { RELATIVO: "% pasante", ABSOLUTO: "mm" };

function textoLimite(modo: ModoRangos, valor: number): string {
  return modo === "RELATIVO" ? `D${formatearNumero(valor, 1)}` : `${formatearNumero(valor, 1)} mm`;
}

/** RF-14: configurar los rangos de tamaño y sus colores (se aplican a todos los análisis). */
export function Configuracion() {
  const [config, setConfig] = useState<ConfiguracionRangos | null>(null);
  const [guardada, setGuardada] = useState<ConfiguracionRangos | null>(null);
  const [error, setError] = useState("");
  const [aviso, setAviso] = useState("");
  const [ocupado, setOcupado] = useState(false);
  const [confirmarRestablecer, setConfirmarRestablecer] = useState(false);

  useEffect(() => {
    obtenerConfiguracionRangos()
      .then((datos) => {
        setConfig(datos);
        setGuardada(datos);
      })
      .catch((e: unknown) => setError(mensajeDeError(e)));
  }, []);

  const cambiar = (nueva: ConfiguracionRangos) => {
    setConfig(nueva);
    setAviso("");
  };

  const ejecutar = async (accion: () => Promise<ConfiguracionRangos>, mensaje: string) => {
    setOcupado(true);
    setError("");
    try {
      const resultado = await accion();
      setConfig(resultado);
      setGuardada(resultado);
      setAviso(mensaje);
    } catch (e) {
      setError(mensajeDeError(e));
    } finally {
      setOcupado(false);
    }
  };

  if (!config) {
    return (
      <div className="configuracion">
        <Encabezado />
        <main className="configuracion__contenido">
          <MensajeError mensaje={error} />
          {!error && <p>Cargando configuración...</p>}
        </main>
      </div>
    );
  }

  const problema = problemaDeConfiguracion(config);
  const sinCambios = JSON.stringify(config) === JSON.stringify(guardada);

  return (
    <div className="configuracion">
      <Encabezado />
      <main className="configuracion__contenido">
        <div>
          <h1 className="configuracion__titulo">Rangos de tamaño y colores</h1>
          <p className="configuracion__ayuda">
            Definen cómo se colorean los fragmentos en el editor, los resultados, el PDF y el CSV. Se
            aplican a todos los análisis.
          </p>
        </div>
        <MensajeError mensaje={error} />

        <section className="configuracion__tarjeta">
          <h2 className="configuracion__subtitulo">Tipo de límites</h2>
          <div className="configuracion__opciones" role="radiogroup" aria-label="Tipo de límites">
            <label className="configuracion__opcion">
              <input
                type="radio"
                name="modo"
                checked={config.modo === "RELATIVO"}
                onChange={() => cambiar(cambiarModo(config, "RELATIVO"))}
              />
              <span>
                <strong>Relativos a la curva</strong> — límites en % pasante (p. ej. 50 = D50). Se adaptan a
                cada pila.
              </span>
            </label>
            <label className="configuracion__opcion">
              <input
                type="radio"
                name="modo"
                checked={config.modo === "ABSOLUTO"}
                onChange={() => cambiar(cambiarModo(config, "ABSOLUTO"))}
              />
              <span>
                <strong>Tamaño fijo</strong> — límites en milímetros. Permiten comparar pilas entre sí.
              </span>
            </label>
          </div>
        </section>

        <section className="configuracion__tarjeta">
          <h2 className="configuracion__subtitulo">Rangos</h2>
          <table className="configuracion__tabla">
            <thead>
              <tr>
                <th>Color</th>
                <th>Nombre</th>
                <th>Desde</th>
                <th>Hasta ({UNIDAD[config.modo]})</th>
                <th aria-label="Acciones" />
              </tr>
            </thead>
            <tbody>
              {config.nombres.map((nombre, i) => {
                const esUltimo = i === config.nombres.length - 1;
                return (
                  <tr key={i}>
                    <td>
                      <input
                        type="color"
                        className="configuracion__color"
                        aria-label={`Color del rango ${i + 1}`}
                        value={config.colores[i]}
                        onChange={(e) => cambiar({ ...config, colores: cambiarEnLista(config.colores, i, e.target.value) })}
                      />
                    </td>
                    <td>
                      <input
                        className="configuracion__campo configuracion__campo--nombre"
                        aria-label={`Nombre del rango ${i + 1}`}
                        value={nombre}
                        maxLength={40}
                        onChange={(e) => cambiar({ ...config, nombres: cambiarEnLista(config.nombres, i, e.target.value) })}
                      />
                    </td>
                    <td className="configuracion__desde">{i === 0 ? "0" : textoLimite(config.modo, config.cortes[i - 1])}</td>
                    <td>
                      {esUltimo ? (
                        <span className="configuracion__desde">en adelante</span>
                      ) : (
                        <input
                          type="number"
                          className="configuracion__campo"
                          aria-label={`Límite superior del rango ${i + 1}`}
                          min="0"
                          step="any"
                          value={Number.isFinite(config.cortes[i]) ? config.cortes[i] : ""}
                          onChange={(e) =>
                            cambiar({
                              ...config,
                              cortes: cambiarEnLista(config.cortes, i, e.target.value === "" ? Number.NaN : Number(e.target.value)),
                            })
                          }
                        />
                      )}
                    </td>
                    <td>
                      <Boton
                        variante="peligro"
                        onClick={() => cambiar(quitarRango(config, i))}
                        disabled={config.nombres.length <= MINIMO_RANGOS}
                        aria-label={`Quitar el rango ${nombre}`}
                      >
                        Quitar
                      </Boton>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          <div>
            <Boton
              variante="secundario"
              onClick={() => cambiar(agregarRango(config, leerToken("--color-rango-nuevo")))}
              disabled={config.nombres.length >= MAXIMO_RANGOS}
            >
              + Agregar rango
            </Boton>
          </div>

          <div className="configuracion__vista-previa" aria-label="Vista previa de los colores">
            {config.nombres.map((nombre, i) => (
              <span key={i} className="configuracion__segmento" style={{ background: config.colores[i] }} title={nombre} />
            ))}
          </div>
          {problema && <p className="configuracion__problema">{problema}</p>}
        </section>

        <div className="configuracion__acciones">
          <Boton
            onClick={() => void ejecutar(() => guardarConfiguracionRangos(config), "Configuración guardada.")}
            disabled={ocupado || Boolean(problema) || sinCambios}
          >
            Guardar
          </Boton>
          <Boton variante="secundario" onClick={() => guardada && cambiar(guardada)} disabled={ocupado || sinCambios}>
            Descartar cambios
          </Boton>
          <Boton variante="peligro" onClick={() => setConfirmarRestablecer(true)} disabled={ocupado}>
            Restablecer valores por defecto
          </Boton>
          {aviso && (
            <p className="configuracion__aviso" role="status">
              {aviso}
            </p>
          )}
        </div>
      </main>

      {confirmarRestablecer && (
        <ModalConfirmacion
          titulo="Restablecer rangos"
          mensaje="Se volverá a los 5 rangos por defecto (< D20, D20–D50, D50–D80, D80–D90, ≥ D90) con sus colores."
          textoConfirmar="Restablecer"
          onConfirmar={() => {
            setConfirmarRestablecer(false);
            void ejecutar(restablecerConfiguracionRangos, "Se restablecieron los valores por defecto.");
          }}
          onCancelar={() => setConfirmarRestablecer(false)}
        />
      )}
    </div>
  );
}
