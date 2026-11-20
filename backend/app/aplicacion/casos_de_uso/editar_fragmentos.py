"""Caso de uso: guardar la lista de fragmentos editada por el operador (HU-05, HU-06)."""

from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID

from app.aplicacion.puertos import RepositorioAnalisis
from app.dominio.errores import AnalisisNoEncontrado
from app.dominio.modelo import Fragmento, OrigenFragmento, Poligono, Punto


@dataclass(frozen=True)
class FragmentoEditado:
    """Fragmento enviado por el editor; sin id si es nuevo."""

    id: UUID | None
    puntos: Sequence[Punto]
    origen: OrigenFragmento


class EditarFragmentos:
    """Reemplaza todos los fragmentos del análisis por la lista editada."""

    def __init__(self, repositorio: RepositorioAnalisis) -> None:
        self._repositorio = repositorio

    def ejecutar(self, id: UUID, editados: Sequence[FragmentoEditado]) -> list[Fragmento]:
        """Valida en el dominio, guarda y devuelve los fragmentos vigentes."""
        analisis = self._repositorio.obtener(id)
        if analisis is None:
            raise AnalisisNoEncontrado(str(id))
        fragmentos = [self._a_fragmento(e) for e in editados]
        analisis.reemplazar_fragmentos(fragmentos)
        self._repositorio.guardar(analisis)
        return list(analisis.fragmentos)

    @staticmethod
    def _a_fragmento(editado: FragmentoEditado) -> Fragmento:
        poligono = Poligono(tuple(editado.puntos))
        if editado.id is None:
            return Fragmento.crear(poligono, editado.origen)
        return Fragmento(id=editado.id, poligono=poligono, origen=editado.origen)
