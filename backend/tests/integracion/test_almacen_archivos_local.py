"""Pruebas del almacén de archivos local."""
from pathlib import Path

import pytest

from app.adaptadores.salida.almacenamiento.archivos_local import AlmacenArchivosLocal


def test_guardar_leer_y_eliminar(tmp_path: Path) -> None:
    almacen = AlmacenArchivosLocal(str(tmp_path / "imagenes"))
    ruta = almacen.guardar(b"abc", "JPG")
    assert ruta.endswith(".jpg") and "/" not in ruta
    assert (tmp_path / "imagenes" / ruta).exists()
    assert almacen.leer(ruta) == b"abc"
    almacen.eliminar(ruta)
    assert not (tmp_path / "imagenes" / ruta).exists()


def test_eliminar_archivo_inexistente_no_falla(tmp_path: Path) -> None:
    AlmacenArchivosLocal(str(tmp_path)).eliminar("no-existe.png")


def test_rechaza_rutas_fuera_de_la_carpeta(tmp_path: Path) -> None:
    almacen = AlmacenArchivosLocal(str(tmp_path / "imagenes"))
    with pytest.raises(ValueError):
        almacen.leer("../secreto.txt")
