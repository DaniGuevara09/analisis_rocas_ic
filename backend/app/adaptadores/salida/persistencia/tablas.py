"""Modelos de tabla de SQLAlchemy (independientes de las clases del dominio)."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base declarativa de las tablas."""


class TablaAnalisis(Base):
    """Tabla `analisis`, con los datos de la imagen."""

    __tablename__ = "analisis"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(150))
    fecha_creacion: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    estado: Mapped[str] = mapped_column(String(20))
    imagen_ruta: Mapped[str] = mapped_column(String(255))
    imagen_ancho_px: Mapped[int] = mapped_column(Integer)
    imagen_alto_px: Mapped[int] = mapped_column(Integer)
    imagen_formato: Mapped[str] = mapped_column(String(3))


class TablaCalibracion(Base):
    """Tabla `calibracion` (1:1 con análisis)."""

    __tablename__ = "calibracion"

    analisis_id: Mapped[UUID] = mapped_column(
        ForeignKey("analisis.id", ondelete="CASCADE"), primary_key=True
    )
    inicio_x_px: Mapped[float] = mapped_column(Float)
    inicio_y_px: Mapped[float] = mapped_column(Float)
    fin_x_px: Mapped[float] = mapped_column(Float)
    fin_y_px: Mapped[float] = mapped_column(Float)
    longitud_real_mm: Mapped[float] = mapped_column(Float)


class TablaRegionExcluida(Base):
    """Tabla `region_excluida` (1:1 con análisis); el polígono va en JSONB."""

    __tablename__ = "region_excluida"

    analisis_id: Mapped[UUID] = mapped_column(
        ForeignKey("analisis.id", ondelete="CASCADE"), primary_key=True
    )
    poligono: Mapped[list[Any]] = mapped_column(JSONB)


class TablaFragmento(Base):
    """Tabla `fragmento`; el polígono va en JSONB."""

    __tablename__ = "fragmento"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    analisis_id: Mapped[UUID] = mapped_column(
        ForeignKey("analisis.id", ondelete="CASCADE"), index=True
    )
    poligono: Mapped[list[Any]] = mapped_column(JSONB)
    origen: Mapped[str] = mapped_column(String(10))


class TablaConfiguracion(Base):
    """Tabla `configuracion`: pares clave/valor JSON (p. ej. clave "rangos", RF-14)."""

    __tablename__ = "configuracion"

    clave: Mapped[str] = mapped_column(String(50), primary_key=True)
    valor: Mapped[dict[str, Any]] = mapped_column(JSONB)
