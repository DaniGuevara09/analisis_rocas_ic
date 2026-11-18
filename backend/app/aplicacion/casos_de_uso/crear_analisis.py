"""Caso de uso: crear un análisis a partir de una fotografía."""
from app.aplicacion.puertos import AlmacenImagenes, InspectorImagenes, RepositorioAnalisis
from app.dominio.modelo import Analisis, Imagen


class CrearAnalisis:
    """Inspecciona y guarda la imagen, crea el agregado y lo persiste."""

    def __init__(
        self,
        repositorio: RepositorioAnalisis,
        almacen: AlmacenImagenes,
        inspector: InspectorImagenes,
    ) -> None:
        self._repositorio = repositorio
        self._almacen = almacen
        self._inspector = inspector

    def ejecutar(self, nombre: str, contenido: bytes) -> Analisis:
        """Crea el análisis; si falla la persistencia, elimina la imagen guardada."""
        formato, ancho_px, alto_px = self._inspector.inspeccionar(contenido)
        ruta = self._almacen.guardar(contenido, formato.lower())
        try:
            analisis = Analisis.crear(nombre, Imagen(ruta, ancho_px, alto_px, formato))
            self._repositorio.guardar(analisis)
        except Exception:
            self._almacen.eliminar(ruta)
            raise
        return analisis
