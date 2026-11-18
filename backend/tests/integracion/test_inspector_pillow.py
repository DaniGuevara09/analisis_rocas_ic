"""Pruebas del inspector de imágenes con imágenes generadas con Pillow."""
from io import BytesIO

import pytest
from PIL import Image

from app.adaptadores.salida.almacenamiento.inspector_pillow import InspectorImagenesPillow
from app.dominio.errores import FormatoImagenNoValido


def imagen_en(formato: str, ancho: int = 40, alto: int = 30) -> bytes:
    salida = BytesIO()
    Image.new("RGB", (ancho, alto), (120, 90, 60)).save(salida, format=formato)
    return salida.getvalue()


@pytest.mark.parametrize("formato_pillow, esperado", [("JPEG", "JPG"), ("PNG", "PNG")])
def test_detecta_formato_y_dimensiones(formato_pillow: str, esperado: str) -> None:
    assert InspectorImagenesPillow().inspeccionar(imagen_en(formato_pillow)) == (esperado, 40, 30)


def test_rechaza_archivo_de_texto() -> None:
    with pytest.raises(FormatoImagenNoValido):
        InspectorImagenesPillow().inspeccionar(b"esto no es una imagen")


def test_rechaza_imagen_de_otro_formato() -> None:
    with pytest.raises(FormatoImagenNoValido):
        InspectorImagenesPillow().inspeccionar(imagen_en("GIF"))


def test_detecta_por_contenido_no_por_extension() -> None:
    # Un PNG es PNG aunque se suba como "foto.jpg": el inspector solo ve los bytes.
    assert InspectorImagenesPillow().inspeccionar(imagen_en("PNG"))[0] == "PNG"
