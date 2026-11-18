"""Excepciones de dominio."""


class ErrorDominio(Exception):
    """Clase base de todos los errores de dominio."""


class FormatoImagenNoValido(ErrorDominio):
    """El formato de la imagen no es JPG ni PNG."""


class CalibracionNoValida(ErrorDominio):
    """Longitud real menor o igual a cero, o puntos de calibración coincidentes."""


class EscalaNoCalibrada(ErrorDominio):
    """Se intenta segmentar o calcular sin calibración."""


class PoligonoNoValido(ErrorDominio):
    """Polígono con menos de 3 puntos o de área cero."""


class DatosInsuficientes(ErrorDominio):
    """No hay fragmentos suficientes para calcular."""


class AnalisisNoEncontrado(ErrorDominio):
    """El id del análisis no existe (lo lanza la capa de aplicación)."""


class FragmentoNoEncontrado(ErrorDominio):
    """El id del fragmento no existe en el análisis."""


class ImagenNoValida(ErrorDominio):
    """La imagen tiene ancho o alto menor o igual a cero."""


class FragmentoEnRegionExcluida(ErrorDominio):
    """El centroide del fragmento cae dentro de la región excluida."""


class DatosNoValidos(ErrorDominio):
    """Datos de entrada inválidos (por ejemplo, un nombre vacío o demasiado largo)."""
