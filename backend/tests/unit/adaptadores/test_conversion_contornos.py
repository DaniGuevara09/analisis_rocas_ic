"""Pruebas de la conversión de contornos de YOLO a polígonos (sin ultralytics)."""

import pytest

from app.adaptadores.salida.segmentacion.contornos import (
    poligonos_desde_contornos,
    simplificar,
)
from app.adaptadores.salida.segmentacion.no_disponible import SegmentadorNoDisponible
from app.aplicacion.errores import ModeloNoDisponible


def cuadrado_denso(lado: float, por_lado: int) -> list[tuple[float, float]]:
    """Cuadrado con `por_lado` vértices en cada arista (4 * por_lado en total)."""
    paso = lado / por_lado
    puntos = [(i * paso, 0.0) for i in range(por_lado)]
    puntos += [(lado, i * paso) for i in range(por_lado)]
    puntos += [(lado - i * paso, lado) for i in range(por_lado)]
    puntos += [(0.0, lado - i * paso) for i in range(por_lado)]
    return puntos


def test_recorta_los_puntos_a_los_bordes_de_la_imagen() -> None:
    contorno = [(-5.0, -5.0), (50.0, -2.0), (120.0, 40.0), (30.0, 80.0)]
    (poligono,) = poligonos_desde_contornos([contorno], 100, 60)
    assert all(0 <= p.x <= 100 and 0 <= p.y <= 60 for p in poligono.puntos)


def test_descarta_contornos_con_menos_de_tres_puntos() -> None:
    assert poligonos_desde_contornos([[(0.0, 0.0), (10.0, 10.0)]], 100, 100) == []


def test_descarta_contornos_colineales() -> None:
    assert poligonos_desde_contornos([[(0.0, 0.0), (5.0, 5.0), (10.0, 10.0)]], 100, 100) == []


def test_descarta_contornos_de_area_menor_a_la_minima() -> None:
    pequeno = [(0.0, 0.0), (4.0, 0.0), (4.0, 4.0), (0.0, 4.0)]  # 16 px²
    grande = [(10.0, 10.0), (20.0, 10.0), (20.0, 20.0), (10.0, 20.0)]  # 100 px²
    resultado = poligonos_desde_contornos([pequeno, grande], 100, 100, area_minima_px=20)
    assert len(resultado) == 1
    assert resultado[0].area() == pytest.approx(100.0)


def test_simplificacion_conserva_el_area_del_cuadrado() -> None:
    contorno = cuadrado_denso(100.0, 100)  # 400 vértices
    (poligono,) = poligonos_desde_contornos([contorno], 200, 200)
    assert len(poligono.puntos) < 20
    assert poligono.area() == pytest.approx(10_000.0, rel=0.01)


def test_simplificar_mantiene_las_esquinas() -> None:
    linea = [(0.0, 0.0), (1.0, 0.1), (2.0, 0.0), (2.0, 2.0)]
    assert simplificar(linea, 0.5) == [(0.0, 0.0), (2.0, 0.0), (2.0, 2.0)]


def test_acepta_arreglos_tipo_numpy_de_pares() -> None:
    contorno = [[0, 0], [30, 0], [30, 30], [0, 30]]
    (poligono,) = poligonos_desde_contornos([contorno], 100, 100)
    assert poligono.area() == pytest.approx(900.0)


def test_segmentador_no_disponible_lanza_modelo_no_disponible() -> None:
    with pytest.raises(ModeloNoDisponible):
        SegmentadorNoDisponible("falta best.pt").segmentar(b"x")
