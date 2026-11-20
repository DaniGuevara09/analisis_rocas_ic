"""Caso de uso: renombrar un análisis."""

from uuid import UUID

from app.aplicacion.puertos import RepositorioAnalisis
from app.dominio.errores import AnalisisNoEncontrado
from app.dominio.modelo import Analisis


class RenombrarAnalisis:
    """Cambia el nombre de un análisis existente."""

    def __init__(self, repositorio: RepositorioAnalisis) -> None:
        self._repositorio = repositorio

    def ejecutar(self, id: UUID, nombre: str) -> Analisis:
        """Renombra el agregado (el dominio valida el nombre) y persiste."""
        analisis = self._repositorio.obtener(id)
        if analisis is None:
            raise AnalisisNoEncontrado(str(id))
        analisis.renombrar(nombre)
        self._repositorio.guardar(analisis)
        return analisis
