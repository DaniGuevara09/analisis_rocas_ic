"""Inspector de imágenes basado en Pillow."""
from io import BytesIO

from PIL import Image, UnidentifiedImageError

from app.dominio.errores import FormatoImagenNoValido

FORMATOS_PILLOW = {"JPEG": "JPG", "PNG": "PNG"}


class InspectorImagenesPillow:
    """Implementa `InspectorImagenes`: detecta formato y tamaño por el contenido."""

    def inspeccionar(self, contenido: bytes) -> tuple[str, int, int]:
        """Devuelve (formato, ancho_px, alto_px) o lanza `FormatoImagenNoValido`."""
        try:
            with Image.open(BytesIO(contenido)) as imagen:
                formato = FORMATOS_PILLOW.get(imagen.format or "")
                ancho_px, alto_px = imagen.size
        except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as error:
            raise FormatoImagenNoValido("El archivo no es una imagen JPG o PNG") from error
        if formato is None:
            raise FormatoImagenNoValido("Solo se aceptan imagenes JPG o PNG")
        return formato, ancho_px, alto_px
