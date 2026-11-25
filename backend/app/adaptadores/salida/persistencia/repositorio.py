"""Repositorio de análisis sobre PostgreSQL."""

from uuid import UUID

from sqlalchemy import Engine, delete, select
from sqlalchemy.orm import Session, sessionmaker

from app.adaptadores.salida.persistencia.conversores import (
    analisis_a_filas,
    analisis_desde_filas,
)
from app.adaptadores.salida.persistencia.tablas import (
    TablaAnalisis,
    TablaCalibracion,
    TablaFragmento,
    TablaRegionExcluida,
)
from app.dominio.modelo import Analisis


class RepositorioPostgreSQL:
    """Implementa `RepositorioAnalisis`; cada operación usa su propia transacción."""

    def __init__(self, motor: Engine) -> None:
        self._sesiones = sessionmaker(motor, expire_on_commit=False)

    def guardar(self, analisis: Analisis) -> None:
        """Persiste el agregado completo (reemplaza calibración, región y fragmentos)."""
        fila, calibracion, region, fragmentos = analisis_a_filas(analisis)
        with self._sesiones.begin() as sesion:
            sesion.execute(
                select(TablaAnalisis.id)
                .where(TablaAnalisis.id == analisis.id)
                .with_for_update()
            )
            sesion.merge(fila)
            for tabla in (TablaCalibracion, TablaRegionExcluida, TablaFragmento):
                sesion.execute(delete(tabla).where(tabla.analisis_id == analisis.id))
            sesion.flush()
            if calibracion is not None:
                sesion.add(calibracion)
            if region is not None:
                sesion.add(region)
            sesion.add_all(fragmentos)

    def obtener(self, id: UUID) -> Analisis | None:
        """Recupera el agregado o None si no existe."""
        with self._sesiones() as sesion:
            fila = sesion.get(TablaAnalisis, id)
            return None if fila is None else self._reconstruir(sesion, fila)

    def obtener_meta_imagen(self, id: UUID) -> tuple[str, str] | None:
        """Recupera solo `(imagen_ruta, imagen_formato)` sin cargar fragmentos."""
        with self._sesiones() as sesion:
            fila = sesion.execute(
                select(TablaAnalisis.imagen_ruta, TablaAnalisis.imagen_formato).where(
                    TablaAnalisis.id == id
                )
            ).first()
            return None if fila is None else (fila[0], fila[1])

    def listar(self) -> list[Analisis]:
        """Recupera todos los análisis en 4 consultas (sin N+1), el más reciente primero."""
        with self._sesiones() as sesion:
            filas = list(
                sesion.scalars(
                    select(TablaAnalisis).order_by(TablaAnalisis.fecha_creacion.desc())
                ).all()
            )
            if not filas:
                return []
            ids = [f.id for f in filas]
            calibraciones = {
                c.analisis_id: c
                for c in sesion.scalars(
                    select(TablaCalibracion).where(TablaCalibracion.analisis_id.in_(ids))
                ).all()
            }
            regiones = {
                r.analisis_id: r
                for r in sesion.scalars(
                    select(TablaRegionExcluida).where(TablaRegionExcluida.analisis_id.in_(ids))
                ).all()
            }
            fragmentos_por_id: dict[UUID, list[TablaFragmento]] = {i: [] for i in ids}
            for frag in sesion.scalars(
                select(TablaFragmento).where(TablaFragmento.analisis_id.in_(ids))
            ).all():
                fragmentos_por_id[frag.analisis_id].append(frag)
            return [
                analisis_desde_filas(
                    fila,
                    calibraciones.get(fila.id),
                    regiones.get(fila.id),
                    fragmentos_por_id[fila.id],
                )
                for fila in filas
            ]

    def eliminar(self, id: UUID) -> None:
        """Elimina el análisis; las demás tablas caen en cascada."""
        with self._sesiones.begin() as sesion:
            sesion.execute(delete(TablaAnalisis).where(TablaAnalisis.id == id))

    @staticmethod
    def _reconstruir(sesion: Session, fila: TablaAnalisis) -> Analisis:
        fragmentos = sesion.scalars(
            select(TablaFragmento).where(TablaFragmento.analisis_id == fila.id)
        ).all()
        return analisis_desde_filas(
            fila,
            sesion.get(TablaCalibracion, fila.id),
            sesion.get(TablaRegionExcluida, fila.id),
            list(fragmentos),
        )
