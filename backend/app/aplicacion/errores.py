"""Errores de la capa de aplicación (no son reglas de negocio)."""


class ErrorAplicacion(Exception):
    """Clase base de los errores de aplicación."""


class ModeloNoDisponible(ErrorAplicacion):
    """El modelo de segmentación no está cargado (por ejemplo, falta best.pt)."""
