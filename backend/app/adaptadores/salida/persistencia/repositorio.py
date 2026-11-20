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

    def listar(self) -> list[Analisis]:
        """Recupera todos los análisis, el más reciente primero."""
        with self._sesiones() as sesion:
            filas = sesion.scalars(
                select(TablaAnalisis).order_by(TablaAnalisis.fecha_creacion.desc())
            ).all()
            return [self._reconstruir(sesion, fila) for fila in filas]

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
