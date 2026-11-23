"""Pruebas de los casos de uso de análisis con adaptadores falsos."""

from uuid import uuid4

import pytest

from app.aplicacion.casos_de_uso.crear_analisis import CrearAnalisis
from app.aplicacion.casos_de_uso.eliminar_analisis import EliminarAnalisis
from app.aplicacion.casos_de_uso.listar_analisis import ListarAnalisis
from app.aplicacion.casos_de_uso.obtener_analisis import ObtenerAnalisis
from app.aplicacion.casos_de_uso.obtener_imagen import ObtenerImagen
from app.aplicacion.casos_de_uso.renombrar_analisis import RenombrarAnalisis
from app.dominio.errores import AnalisisNoEncontrado, DatosNoValidos, FormatoImagenNoValido
from app.dominio.modelo import EstadoAnalisis
from tests.unit.aplicacion.fakes import (
    CABECERA_JPG,
    CABECERA_PNG,
    AlmacenFalso,
    InspectorFalso,
    RepositorioFalso,
)

JPG = CABECERA_JPG + b"datos"
PNG = CABECERA_PNG + b"datos"


@pytest.fixture
def repositorio() -> RepositorioFalso:
    return RepositorioFalso()


@pytest.fixture
def almacen() -> AlmacenFalso:
    return AlmacenFalso()


@pytest.fixture
def crear(repositorio: RepositorioFalso, almacen: AlmacenFalso) -> CrearAnalisis:
    return CrearAnalisis(repositorio, almacen, InspectorFalso())


# --- CrearAnalisis ----------------------------------------------------------
def test_crear_guarda_imagen_y_persiste_el_agregado(
    crear: CrearAnalisis, repositorio: RepositorioFalso, almacen: AlmacenFalso
) -> None:
    analisis = crear.ejecutar("pila 1", JPG)
    assert repositorio.datos[analisis.id] is analisis
    assert analisis.estado is EstadoAnalisis.IMAGEN_CARGADA
    assert analisis.imagen.formato == "JPG"
    assert (analisis.imagen.ancho_px, analisis.imagen.alto_px) == (640, 480)
    assert analisis.imagen.ruta.endswith(".jpg")
    assert almacen.archivos[analisis.imagen.ruta] == JPG


def test_crear_con_png_usa_extension_png(crear: CrearAnalisis) -> None:
    analisis = crear.ejecutar("pila", PNG)
    assert analisis.imagen.formato == "PNG"
    assert analisis.imagen.ruta.endswith(".png")


def test_crear_quita_espacios_del_nombre(crear: CrearAnalisis) -> None:
    assert crear.ejecutar("  pila  ", JPG).nombre == "pila"


def test_crear_con_formato_no_valido_no_guarda_nada(
    crear: CrearAnalisis, repositorio: RepositorioFalso, almacen: AlmacenFalso
) -> None:
    with pytest.raises(FormatoImagenNoValido):
        crear.ejecutar("pila", b"texto plano")
    assert repositorio.datos == {}
    assert almacen.archivos == {}


@pytest.mark.parametrize("nombre", ["", "   ", "x" * 151])
def test_crear_con_nombre_no_valido_lanza_datos_no_validos(
    crear: CrearAnalisis, almacen: AlmacenFalso, nombre: str
) -> None:
    with pytest.raises(DatosNoValidos):
        crear.ejecutar(nombre, JPG)
    assert almacen.archivos == {}


def test_crear_acepta_nombre_de_150_caracteres(crear: CrearAnalisis) -> None:
    assert len(crear.ejecutar("x" * 150, JPG).nombre) == 150


def test_crear_elimina_la_imagen_si_falla_el_repositorio(
    crear: CrearAnalisis, repositorio: RepositorioFalso, almacen: AlmacenFalso
) -> None:
    repositorio.fallar_al_guardar = True
    with pytest.raises(RuntimeError):
        crear.ejecutar("pila", JPG)
    assert almacen.archivos == {}
    assert repositorio.datos == {}


# --- Listar / obtener -------------------------------------------------------
def test_listar_devuelve_el_mas_reciente_primero(
    crear: CrearAnalisis, repositorio: RepositorioFalso
) -> None:
    primero = crear.ejecutar("a", JPG)
    segundo = crear.ejecutar("b", JPG)
    primero.fecha_creacion = segundo.fecha_creacion.replace(year=2000)
    assert ListarAnalisis(repositorio).ejecutar() == [segundo, primero]


def test_listar_vacio(repositorio: RepositorioFalso) -> None:
    assert ListarAnalisis(repositorio).ejecutar() == []


def test_obtener_devuelve_el_analisis(crear: CrearAnalisis, repositorio: RepositorioFalso) -> None:
    analisis = crear.ejecutar("a", JPG)
    assert ObtenerAnalisis(repositorio).ejecutar(analisis.id) is analisis


def test_obtener_inexistente_lanza_no_encontrado(repositorio: RepositorioFalso) -> None:
    with pytest.raises(AnalisisNoEncontrado):
        ObtenerAnalisis(repositorio).ejecutar(uuid4())


# --- Renombrar --------------------------------------------------------------
def test_renombrar_cambia_y_persiste(crear: CrearAnalisis, repositorio: RepositorioFalso) -> None:
    analisis = crear.ejecutar("a", JPG)
    renombrado = RenombrarAnalisis(repositorio).ejecutar(analisis.id, "nuevo")
    assert renombrado.nombre == "nuevo"
    assert repositorio.datos[analisis.id].nombre == "nuevo"


@pytest.mark.parametrize("nombre", ["", "  ", "x" * 151])
def test_renombrar_con_nombre_no_valido_no_cambia_nada(
    crear: CrearAnalisis, repositorio: RepositorioFalso, nombre: str
) -> None:
    analisis = crear.ejecutar("a", JPG)
    with pytest.raises(DatosNoValidos):
        RenombrarAnalisis(repositorio).ejecutar(analisis.id, nombre)
    assert analisis.nombre == "a"


def test_renombrar_inexistente_lanza_no_encontrado(repositorio: RepositorioFalso) -> None:
    with pytest.raises(AnalisisNoEncontrado):
        RenombrarAnalisis(repositorio).ejecutar(uuid4(), "x")


# --- Eliminar ---------------------------------------------------------------
def test_eliminar_borra_registro_e_imagen(
    crear: CrearAnalisis, repositorio: RepositorioFalso, almacen: AlmacenFalso
) -> None:
    analisis = crear.ejecutar("a", JPG)
    EliminarAnalisis(repositorio, almacen).ejecutar(analisis.id)
    assert repositorio.datos == {}
    assert almacen.archivos == {}


def test_eliminar_inexistente_lanza_no_encontrado(
    repositorio: RepositorioFalso, almacen: AlmacenFalso
) -> None:
    with pytest.raises(AnalisisNoEncontrado):
        EliminarAnalisis(repositorio, almacen).ejecutar(uuid4())


# --- Obtener imagen ---------------------------------------------------------
def test_obtener_imagen_devuelve_contenido_y_formato(
    crear: CrearAnalisis, repositorio: RepositorioFalso, almacen: AlmacenFalso
) -> None:
    analisis = crear.ejecutar("a", PNG)
    contenido, formato = ObtenerImagen(repositorio, almacen).ejecutar(analisis.id)
    assert (contenido, formato) == (PNG, "PNG")


def test_obtener_imagen_inexistente_lanza_no_encontrado(
    repositorio: RepositorioFalso, almacen: AlmacenFalso
) -> None:
    with pytest.raises(AnalisisNoEncontrado):
        ObtenerImagen(repositorio, almacen).ejecutar(uuid4())


def test_obtener_imagen_usa_consulta_ligera_si_el_repositorio_la_expone(
    crear: CrearAnalisis, repositorio: RepositorioFalso, almacen: AlmacenFalso
) -> None:
    analisis = crear.ejecutar("a", JPG)

    class RepoLigero(RepositorioFalso):
        def obtener(self, id):  # type: ignore[override]
            raise AssertionError("No debe cargar todo el agregado para servir la imagen")

        def obtener_meta_imagen(self, id):  # type: ignore[no-untyped-def]
            item = self.datos.get(id)
            return None if item is None else (item.imagen.ruta, item.imagen.formato)

    repo_ligero = RepoLigero()
    repo_ligero.datos = repositorio.datos
    contenido, formato = ObtenerImagen(repo_ligero, almacen).ejecutar(analisis.id)
    assert (contenido, formato) == (JPG, "JPG")
