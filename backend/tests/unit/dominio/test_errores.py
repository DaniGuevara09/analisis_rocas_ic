"""Las excepciones de dominio comparten una clase base."""

import pytest

from app.dominio import errores


@pytest.mark.parametrize(
    "nombre",
    [
        "FormatoImagenNoValido",
        "CalibracionNoValida",
        "EscalaNoCalibrada",
        "PoligonoNoValido",
        "DatosInsuficientes",
        "AnalisisNoEncontrado",
        "FragmentoNoEncontrado",
        "ImagenNoValida",
        "FragmentoEnRegionExcluida",
        "DatosNoValidos",
    ],
)
def test_excepcion_hereda_de_error_dominio(nombre: str) -> None:
    clase = getattr(errores, nombre)
    assert issubclass(clase, errores.ErrorDominio)
    assert issubclass(errores.ErrorDominio, Exception)
