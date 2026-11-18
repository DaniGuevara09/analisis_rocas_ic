"""Esquemas Pydantic de la API (ver docs/api.md)."""
from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.dominio.modelo import Analisis, Fragmento, Poligono, ReporteGranulometrico

Coordenada = Annotated[float, Field(allow_inf_nan=False)]
LongitudMm = Annotated[float, Field(allow_inf_nan=False)]


class PuntoEsquema(BaseModel):
    """Punto en píxeles (coordenadas finitas)."""

    x: Coordenada
    y: Coordenada


class ImagenEsquema(BaseModel):
    """Datos de la imagen del análisis."""

    url: str
    ancho_px: int
    alto_px: int
    formato: Literal["JPG", "PNG"]


class CalibracionEsquema(BaseModel):
    """Calibración de la escala."""

    inicio: PuntoEsquema
    fin: PuntoEsquema
    longitud_real_mm: float
    factor_mm_por_px: float


class RegionExcluidaEsquema(BaseModel):
    """Región excluida del conteo."""

    poligono: list[PuntoEsquema]


class FragmentoEsquema(BaseModel):
    """Fragmento con su diámetro equivalente (null si no hay calibración)."""

    id: UUID
    poligono: list[PuntoEsquema]
    origen: Literal["MODELO", "MANUAL"]
    diametro_equivalente_mm: float | None


class AnalisisResumen(BaseModel):
    """Resumen de un análisis para listados."""

    id: UUID
    nombre: str
    fecha_creacion: datetime
    estado: str
    numero_fragmentos: int


class AnalisisDetalle(AnalisisResumen):
    """Análisis completo."""

    imagen: ImagenEsquema
    calibracion: CalibracionEsquema | None
    region_excluida: RegionExcluidaEsquema | None
    fragmentos: list[FragmentoEsquema]


class CalibracionSolicitud(BaseModel):
    """Cuerpo de PUT /analisis/{id}/calibracion."""

    inicio: PuntoEsquema
    fin: PuntoEsquema
    longitud_real_mm: LongitudMm


class CalibracionRespuesta(BaseModel):
    """Resultado de calibrar."""

    factor_mm_por_px: float
    estado: str


class RegionExcluidaSolicitud(BaseModel):
    """Cuerpo de PUT /analisis/{id}/region-excluida."""

    poligono: list[PuntoEsquema]


class FragmentoSolicitud(BaseModel):
    """Fragmento editado: sin id si es nuevo (dibujado, unido o dividido)."""

    id: UUID | None = None
    poligono: list[PuntoEsquema]
    origen: Literal["MODELO", "MANUAL"] = "MANUAL"


class FragmentosSolicitud(BaseModel):
    """Cuerpo de PUT /analisis/{id}/fragmentos: la lista completa editada."""

    fragmentos: list[FragmentoSolicitud]


class PuntoCurvaEsquema(BaseModel):
    """Punto de la curva granulométrica."""

    diametro_mm: float
    pasante_pct: float


class RangoEsquema(BaseModel):
    """Rango de tamaño para colorear fragmentos; el frontend asigna el color por índice."""

    indice: int
    limite_inferior_mm: float
    limite_superior_mm: float | None


class ClaseHistogramaEsquema(BaseModel):
    """Clase del histograma."""

    limite_inferior_mm: float
    limite_superior_mm: float
    numero_fragmentos: int
    porcentaje_retenido: float


class FragmentoMedidoEsquema(BaseModel):
    """Diámetro y rango de cada fragmento."""

    id: UUID
    diametro_equivalente_mm: float
    indice_rango: int


class ResultadosEsquema(BaseModel):
    """Respuesta de GET /analisis/{id}/resultados."""

    d20: float
    d50: float
    d60: float
    d80: float
    d90: float
    indice_n: float
    numero_fragmentos: int
    curva: list[PuntoCurvaEsquema]
    rangos: list[RangoEsquema]
    histograma: list[ClaseHistogramaEsquema]
    fragmentos: list[FragmentoMedidoEsquema]
    supuestos: list[str]


SUPUESTOS = [
    "Forma esférica de los fragmentos (diámetro del círculo de igual área).",
    "Los finos no visibles en la fotografía no se cuentan.",
    "Medición sobre la superficie 2D visible de la pila.",
    "Curva ponderada por volumen de esfera equivalente (d³).",
]


class RenombrarSolicitud(BaseModel):
    """Cuerpo de PATCH /analisis/{id}."""

    nombre: str


def _puntos(poligono: Poligono) -> list[PuntoEsquema]:
    return [PuntoEsquema(x=p.x, y=p.y) for p in poligono.puntos]


def a_resumen(analisis: Analisis) -> AnalisisResumen:
    """Convierte el agregado en su resumen."""
    return AnalisisResumen(
        id=analisis.id,
        nombre=analisis.nombre,
        fecha_creacion=analisis.fecha_creacion,
        estado=analisis.estado.value,
        numero_fragmentos=len(analisis.fragmentos),
    )


def a_fragmento(fragmento: Fragmento, factor: float | None) -> FragmentoEsquema:
    """Convierte un fragmento; el diámetro es null sin calibración."""
    return FragmentoEsquema(
        id=fragmento.id,
        poligono=_puntos(fragmento.poligono),
        origen=fragmento.origen.value,  # type: ignore[arg-type]
        diametro_equivalente_mm=None
        if factor is None
        else fragmento.diametro_equivalente_mm(factor),
    )


def a_fragmentos(analisis: Analisis, fragmentos: list[Fragmento]) -> list[FragmentoEsquema]:
    """Convierte una lista de fragmentos con la calibración del análisis."""
    factor = analisis.calibracion.factor_mm_por_px() if analisis.calibracion else None
    return [a_fragmento(f, factor) for f in fragmentos]


def a_resultados(reporte: ReporteGranulometrico) -> ResultadosEsquema:
    """Convierte el reporte del dominio en la respuesta de resultados."""
    r = reporte.resultado
    return ResultadosEsquema(
        d20=r.d20,
        d50=r.d50,
        d60=r.d60,
        d80=r.d80,
        d90=r.d90,
        indice_n=r.indice_n,
        numero_fragmentos=r.numero_fragmentos,
        curva=[
            PuntoCurvaEsquema(diametro_mm=p.diametro_mm, pasante_pct=p.pasante_pct)
            for p in r.curva
        ],
        rangos=[
            RangoEsquema(
                indice=i,
                limite_inferior_mm=rango.limite_inferior_mm,
                limite_superior_mm=rango.limite_superior_mm,
            )
            for i, rango in enumerate(reporte.rangos)
        ],
        histograma=[
            ClaseHistogramaEsquema(
                limite_inferior_mm=c.limite_inferior_mm,
                limite_superior_mm=c.limite_superior_mm,
                numero_fragmentos=c.numero_fragmentos,
                porcentaje_retenido=c.porcentaje_retenido,
            )
            for c in reporte.histograma
        ],
        fragmentos=[
            FragmentoMedidoEsquema(
                id=m.id,
                diametro_equivalente_mm=m.diametro_equivalente_mm,
                indice_rango=m.indice_rango,
            )
            for m in reporte.fragmentos
        ],
        supuestos=SUPUESTOS,
    )


def a_detalle(analisis: Analisis) -> AnalisisDetalle:
    """Convierte el agregado en su detalle."""
    calibracion = analisis.calibracion

    return AnalisisDetalle(
        **a_resumen(analisis).model_dump(),
        imagen=ImagenEsquema(
            url=f"/api/analisis/{analisis.id}/imagen",
            ancho_px=analisis.imagen.ancho_px,
            alto_px=analisis.imagen.alto_px,
            formato=analisis.imagen.formato,  # type: ignore[arg-type]
        ),
        calibracion=None
        if calibracion is None
        else CalibracionEsquema(
            inicio=PuntoEsquema(x=calibracion.inicio.x, y=calibracion.inicio.y),
            fin=PuntoEsquema(x=calibracion.fin.x, y=calibracion.fin.y),
            longitud_real_mm=calibracion.longitud_real_mm,
            factor_mm_por_px=calibracion.factor_mm_por_px(),
        ),
        region_excluida=None
        if analisis.region_excluida is None
        else RegionExcluidaEsquema(poligono=_puntos(analisis.region_excluida.poligono)),
        fragmentos=a_fragmentos(analisis, analisis.fragmentos),
    )
