"""Traducción de errores de dominio a respuestas HTTP `{codigo, detalle}`."""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.aplicacion.errores import ModeloNoDisponible
from app.dominio.errores import (
    AnalisisNoEncontrado,
    CalibracionNoValida,
    DatosInsuficientes,
    DatosNoValidos,
    ErrorDominio,
    EscalaNoCalibrada,
    FormatoImagenNoValido,
    FragmentoEnRegionExcluida,
    FragmentoNoEncontrado,
    ImagenNoValida,
    PoligonoNoValido,
)

# (HTTP, codigo) por excepción, según docs/api.md
TABLA_ERRORES: dict[type[ErrorDominio], tuple[int, str]] = {
    FormatoImagenNoValido: (415, "FORMATO_NO_VALIDO"),
    CalibracionNoValida: (422, "DATOS_NO_VALIDOS"),
    PoligonoNoValido: (422, "DATOS_NO_VALIDOS"),
    ImagenNoValida: (422, "DATOS_NO_VALIDOS"),
    FragmentoEnRegionExcluida: (422, "DATOS_NO_VALIDOS"),
    DatosNoValidos: (422, "DATOS_NO_VALIDOS"),
    AnalisisNoEncontrado: (404, "NO_ENCONTRADO"),
    FragmentoNoEncontrado: (404, "NO_ENCONTRADO"),
    EscalaNoCalibrada: (409, "ESCALA_NO_CALIBRADA"),
    DatosInsuficientes: (409, "DATOS_INSUFICIENTES"),
}


class ArchivoDemasiadoGrande(Exception):
    """El archivo subido supera el tamaño máximo permitido."""


def _respuesta(estado: int, codigo: str, detalle: str) -> JSONResponse:
    return JSONResponse(status_code=estado, content={"codigo": codigo, "detalle": detalle})


def registrar_manejadores(app: FastAPI) -> None:
    """Instala los manejadores globales de errores."""

    @app.exception_handler(ErrorDominio)
    def _error_dominio(_: Request, error: ErrorDominio) -> JSONResponse:
        for clase in type(error).__mro__:
            if clase in TABLA_ERRORES:
                estado, codigo = TABLA_ERRORES[clase]  # type: ignore[index]
                return _respuesta(estado, codigo, str(error))
        return _respuesta(500, "ERROR_INTERNO", "Error interno")

    @app.exception_handler(ModeloNoDisponible)
    def _modelo_no_disponible(_: Request, error: ModeloNoDisponible) -> JSONResponse:
        detalle = f"El modelo de segmentacion no esta disponible ({error})"
        return _respuesta(503, "MODELO_NO_DISPONIBLE", detalle)

    @app.exception_handler(ArchivoDemasiadoGrande)
    def _archivo_grande(_: Request, error: ArchivoDemasiadoGrande) -> JSONResponse:
        return _respuesta(413, "ARCHIVO_DEMASIADO_GRANDE", str(error))

    @app.exception_handler(RequestValidationError)
    def _validacion(_: Request, error: RequestValidationError) -> JSONResponse:
        campos = ", ".join(str(e["loc"][-1]) for e in error.errors())
        return _respuesta(422, "DATOS_NO_VALIDOS", f"Datos no validos: {campos}")
