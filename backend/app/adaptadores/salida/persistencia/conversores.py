"""Conversión entre el agregado del dominio y las filas de las tablas."""

from typing import Any

from app.adaptadores.salida.persistencia.tablas import (
    TablaAnalisis,
    TablaCalibracion,
    TablaFragmento,
    TablaRegionExcluida,
)
from app.dominio.modelo import (
    Analisis,
    Calibracion,
    EstadoAnalisis,
    Fragmento,
    Imagen,
    OrigenFragmento,
    Poligono,
    Punto,
    RegionExcluida,
)


def poligono_a_json(poligono: Poligono) -> list[dict[str, float]]:
    """Serializa un polígono como lista de {x, y}."""
    return [{"x": p.x, "y": p.y} for p in poligono.puntos]


def poligono_desde_json(datos: list[Any]) -> Poligono:
    """Reconstruye un polígono desde la lista de {x, y}."""
    return Poligono(tuple(Punto(float(p["x"]), float(p["y"])) for p in datos))


def analisis_a_filas(
    analisis: Analisis,
) -> tuple[
    TablaAnalisis, TablaCalibracion | None, TablaRegionExcluida | None, list[TablaFragmento]
]:
    """Convierte el agregado en sus filas (análisis, calibración, región, fragmentos)."""
    fila = TablaAnalisis(
        id=analisis.id,
        nombre=analisis.nombre,
        fecha_creacion=analisis.fecha_creacion,
        estado=analisis.estado.value,
        imagen_ruta=analisis.imagen.ruta,
        imagen_ancho_px=analisis.imagen.ancho_px,
        imagen_alto_px=analisis.imagen.alto_px,
        imagen_formato=analisis.imagen.formato,
    )
    calibracion = None
    if analisis.calibracion is not None:
        c = analisis.calibracion
        calibracion = TablaCalibracion(
            analisis_id=analisis.id,
            inicio_x_px=c.inicio.x,
            inicio_y_px=c.inicio.y,
            fin_x_px=c.fin.x,
            fin_y_px=c.fin.y,
            longitud_real_mm=c.longitud_real_mm,
        )
    region = None
    if analisis.region_excluida is not None:
        region = TablaRegionExcluida(
            analisis_id=analisis.id, poligono=poligono_a_json(analisis.region_excluida.poligono)
        )
    fragmentos = [
        TablaFragmento(
            id=f.id,
            analisis_id=analisis.id,
            poligono=poligono_a_json(f.poligono),
            origen=f.origen.value,
        )
        for f in analisis.fragmentos
    ]
    return fila, calibracion, region, fragmentos


def analisis_desde_filas(
    fila: TablaAnalisis,
    calibracion: TablaCalibracion | None,
    region: TablaRegionExcluida | None,
    fragmentos: list[TablaFragmento],
) -> Analisis:
    """Reconstruye el agregado a partir de sus filas."""
    return Analisis(
        id=fila.id,
        nombre=fila.nombre,
        fecha_creacion=fila.fecha_creacion,
        estado=EstadoAnalisis(fila.estado),
        imagen=Imagen(
            ruta=fila.imagen_ruta,
            ancho_px=fila.imagen_ancho_px,
            alto_px=fila.imagen_alto_px,
            formato=fila.imagen_formato,
        ),
        calibracion=None
        if calibracion is None
        else Calibracion(
            inicio=Punto(calibracion.inicio_x_px, calibracion.inicio_y_px),
            fin=Punto(calibracion.fin_x_px, calibracion.fin_y_px),
            longitud_real_mm=calibracion.longitud_real_mm,
        ),
        region_excluida=None
        if region is None
        else RegionExcluida(poligono_desde_json(region.poligono)),
        fragmentos=[
            Fragmento(f.id, poligono_desde_json(f.poligono), OrigenFragmento(f.origen))
            for f in fragmentos
        ],
    )
