"""Entidades del dominio: Analisis, Calibracion, RegionExcluida, Fragmento, Poligono, Punto."""
import math
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from uuid import UUID, uuid4

from app.dominio import granulometria
from app.dominio.errores import (
    CalibracionNoValida,
    DatosNoValidos,
    EscalaNoCalibrada,
    FormatoImagenNoValido,
    FragmentoEnRegionExcluida,
    FragmentoNoEncontrado,
    ImagenNoValida,
    PoligonoNoValido,
)
from app.dominio.resultado import PuntoCurva, ResultadoGranulometrico

__all__ = [
    "Analisis",
    "Calibracion",
    "EstadoAnalisis",
    "Fragmento",
    "Imagen",
    "OrigenFragmento",
    "Poligono",
    "Punto",
    "PuntoCurva",
    "RegionExcluida",
    "ResultadoGranulometrico",
]

FORMATOS_IMAGEN = ("JPG", "PNG")
TOLERANCIA_AREA_PX = 1e-9
LONGITUD_MAXIMA_NOMBRE = 150


def _validar_nombre(nombre: str) -> str:
    """Devuelve el nombre recortado o lanza `DatosNoValidos` si está vacío o es muy largo."""
    limpio = nombre.strip()
    if not limpio:
        raise DatosNoValidos("El nombre no puede estar vacio")
    if len(limpio) > LONGITUD_MAXIMA_NOMBRE:
        raise DatosNoValidos(f"El nombre no puede superar {LONGITUD_MAXIMA_NOMBRE} caracteres")
    return limpio


class EstadoAnalisis(Enum):
    """Estados del análisis, en orden de avance."""

    IMAGEN_CARGADA = "IMAGEN_CARGADA"
    CALIBRADO = "CALIBRADO"
    SEGMENTADO = "SEGMENTADO"


class OrigenFragmento(Enum):
    """Quién creó el fragmento."""

    MODELO = "MODELO"
    MANUAL = "MANUAL"


@dataclass(frozen=True)
class Punto:
    """Coordenadas en píxeles."""

    x: float
    y: float


@dataclass(frozen=True)
class Poligono:
    """Polígono simple con al menos 3 puntos y área mayor que cero."""

    puntos: tuple[Punto, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "puntos", tuple(self.puntos))
        if len(self.puntos) < 3:
            raise PoligonoNoValido("Un poligono necesita al menos 3 puntos")
        if self.area() <= TOLERANCIA_AREA_PX:
            raise PoligonoNoValido("El poligono tiene area cero")

    def _area_con_signo(self) -> float:
        suma = 0.0
        for a, b in zip(self.puntos, self.puntos[1:] + self.puntos[:1], strict=True):
            suma += a.x * b.y - b.x * a.y
        return suma / 2.0

    def area(self) -> float:
        """Área en px² (fórmula del zapato, valor absoluto)."""
        return abs(self._area_con_signo())

    def centroide(self) -> Punto:
        """Centro de masa del polígono."""
        area = self._area_con_signo()
        cx = cy = 0.0
        for a, b in zip(self.puntos, self.puntos[1:] + self.puntos[:1], strict=True):
            cruz = a.x * b.y - b.x * a.y
            cx += (a.x + b.x) * cruz
            cy += (a.y + b.y) * cruz
        return Punto(cx / (6.0 * area), cy / (6.0 * area))

    def contiene(self, punto: Punto) -> bool:
        """Indica si el punto está dentro del polígono (ray casting)."""
        dentro = False
        for a, b in zip(self.puntos, self.puntos[1:] + self.puntos[:1], strict=True):
            if (a.y > punto.y) != (b.y > punto.y):
                x_cruce = a.x + (punto.y - a.y) * (b.x - a.x) / (b.y - a.y)
                if punto.x < x_cruce:
                    dentro = not dentro
        return dentro


@dataclass(frozen=True)
class Imagen:
    """Fotografía del análisis: ruta relativa, tamaño en px y formato JPG o PNG."""

    ruta: str
    ancho_px: int
    alto_px: int
    formato: str

    def __post_init__(self) -> None:
        if self.formato.upper() not in FORMATOS_IMAGEN:
            raise FormatoImagenNoValido(f"Formato no soportado: {self.formato}")
        if self.ancho_px <= 0 or self.alto_px <= 0:
            raise ImagenNoValida("Las dimensiones de la imagen deben ser positivas")


@dataclass(frozen=True)
class Calibracion:
    """Línea trazada sobre el objeto de escala y su longitud real en mm."""

    inicio: Punto
    fin: Punto
    longitud_real_mm: float

    def __post_init__(self) -> None:
        if self.longitud_real_mm <= 0:
            raise CalibracionNoValida("La longitud real debe ser mayor que cero")
        if self.distancia_px() == 0:
            raise CalibracionNoValida("Los puntos de calibracion no pueden coincidir")

    def distancia_px(self) -> float:
        """Distancia entre los puntos de la línea, en píxeles."""
        return math.hypot(self.fin.x - self.inicio.x, self.fin.y - self.inicio.y)

    def factor_mm_por_px(self) -> float:
        """Milímetros reales por píxel."""
        return granulometria.factor_mm_por_px(self.longitud_real_mm, self.distancia_px())


@dataclass(frozen=True)
class RegionExcluida:
    """Región de la imagen (objeto de escala) que no se cuenta."""

    poligono: Poligono

    def contiene(self, punto: Punto) -> bool:
        """Indica si el punto cae dentro de la región."""
        return self.poligono.contiene(punto)


@dataclass(frozen=True)
class Fragmento:
    """Fragmento de roca delimitado por un polígono en píxeles."""

    id: UUID
    poligono: Poligono
    origen: OrigenFragmento

    @classmethod
    def crear(cls, poligono: Poligono, origen: OrigenFragmento) -> "Fragmento":
        """Crea un fragmento con un id nuevo."""
        return cls(id=uuid4(), poligono=poligono, origen=origen)

    def area_px(self) -> float:
        """Área del fragmento en px²."""
        return self.poligono.area()

    def diametro_equivalente_mm(self, factor_mm_por_px: float) -> float:
        """Diámetro equivalente en mm según el factor de escala."""
        area = granulometria.area_mm2(self.area_px(), factor_mm_por_px)
        return granulometria.diametro_equivalente_mm(area)


@dataclass
class Analisis:
    """Agregado raíz: toda modificación de sus partes pasa por sus métodos."""

    id: UUID
    nombre: str
    fecha_creacion: datetime
    estado: EstadoAnalisis
    imagen: Imagen
    calibracion: Calibracion | None = None
    region_excluida: RegionExcluida | None = None
    fragmentos: list[Fragmento] = field(default_factory=list)

    @classmethod
    def crear(cls, nombre: str, imagen: Imagen) -> "Analisis":
        """Crea un análisis nuevo en estado IMAGEN_CARGADA; valida el nombre."""
        return cls(
            id=uuid4(),
            nombre=_validar_nombre(nombre),
            fecha_creacion=datetime.now(UTC),
            estado=EstadoAnalisis.IMAGEN_CARGADA,
            imagen=imagen,
        )

    def renombrar(self, nombre: str) -> None:
        """Cambia el nombre (se recorta; vacío o de más de 150 caracteres es inválido)."""
        self.nombre = _validar_nombre(nombre)

    def calibrar(self, inicio: Punto, fin: Punto, longitud_mm: float) -> None:
        """Fija la calibración. Los puntos deben estar dentro de la imagen.

        Un análisis SEGMENTADO conserva su estado.
        """
        calibracion = Calibracion(inicio, fin, longitud_mm)
        if not (self._dentro_de_imagen(inicio) and self._dentro_de_imagen(fin)):
            raise CalibracionNoValida("Los puntos de calibracion deben estar dentro de la imagen")
        self.calibracion = calibracion
        if self.estado is EstadoAnalisis.IMAGEN_CARGADA:
            self.estado = EstadoAnalisis.CALIBRADO

    def factor_mm_por_px(self) -> float:
        """Factor de escala vigente; lanza `EscalaNoCalibrada` si no hay calibración."""
        return self._exigir_calibracion().factor_mm_por_px()

    def excluir_region(self, poligono: Poligono) -> None:
        """Fija la región excluida y elimina los fragmentos cuyo centroide quede dentro.

        Todos los vértices deben estar dentro de la imagen.
        """
        if not all(self._dentro_de_imagen(p) for p in poligono.puntos):
            raise PoligonoNoValido("La region excluida debe estar dentro de la imagen")
        region = RegionExcluida(poligono)
        self.region_excluida = region
        self.fragmentos = [
            f for f in self.fragmentos if not region.contiene(f.poligono.centroide())
        ]

    def quitar_region_excluida(self) -> None:
        """Elimina la región excluida."""
        self.region_excluida = None

    def registrar_fragmentos(
        self, poligonos: Sequence[Poligono], origen: OrigenFragmento
    ) -> list[Fragmento]:
        """Reemplaza todos los fragmentos por los polígonos dados, omitiendo los excluidos."""
        self._exigir_calibracion()
        self.fragmentos = []
        registrados = []
        for poligono in poligonos:
            if self._en_region_excluida(poligono):
                continue
            fragmento = Fragmento.crear(poligono, origen)
            self.fragmentos.append(fragmento)
            registrados.append(fragmento)
        self.estado = EstadoAnalisis.SEGMENTADO
        return registrados

    def agregar_fragmento(self, poligono: Poligono) -> Fragmento:
        """Agrega un fragmento dibujado a mano; no puede caer en la región excluida."""
        self._exigir_calibracion()
        if self._en_region_excluida(poligono):
            raise FragmentoEnRegionExcluida("El fragmento cae en la region excluida")
        fragmento = Fragmento.crear(poligono, OrigenFragmento.MANUAL)
        self.fragmentos.append(fragmento)
        self.estado = EstadoAnalisis.SEGMENTADO
        return fragmento

    def eliminar_fragmento(self, id_fragmento: UUID) -> None:
        """Elimina un fragmento por su id."""
        for indice, fragmento in enumerate(self.fragmentos):
            if fragmento.id == id_fragmento:
                del self.fragmentos[indice]
                return
        raise FragmentoNoEncontrado(str(id_fragmento))

    def calcular_resultado(self) -> ResultadoGranulometrico:
        """Calcula los indicadores granulométricos con la calibración vigente."""
        factor = self.factor_mm_por_px()
        diametros = [f.diametro_equivalente_mm(factor) for f in self.fragmentos]
        return granulometria.calcular(diametros)

    def _exigir_calibracion(self) -> Calibracion:
        if self.calibracion is None:
            raise EscalaNoCalibrada("El analisis no tiene calibracion")
        return self.calibracion

    def _dentro_de_imagen(self, punto: Punto) -> bool:
        return 0 <= punto.x <= self.imagen.ancho_px and 0 <= punto.y <= self.imagen.alto_px

    def _en_region_excluida(self, poligono: Poligono) -> bool:
        return self.region_excluida is not None and self.region_excluida.contiene(
            poligono.centroide()
        )
