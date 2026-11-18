"""Pruebas de las funciones puras de granulometria (valores calculados a mano)."""
import math

import pytest

from app.dominio import granulometria as g
from app.dominio.errores import DatosInsuficientes
from app.dominio.resultado import PuntoCurva


def test_factor_mm_por_px() -> None:
    # distancia (0,0)-(300,400) = 500 px; 250 mm / 500 px = 0.5
    assert g.factor_mm_por_px(250.0, 500.0) == pytest.approx(0.5, abs=1e-3)


def test_area_mm2() -> None:
    assert g.area_mm2(100.0, 0.5) == pytest.approx(25.0, abs=1e-3)


def test_diametro_equivalente_mm() -> None:
    assert g.diametro_equivalente_mm(25.0) == pytest.approx(5.642, abs=1e-3)


def test_ponderacion_es_volumen_de_esfera_proporcional_a_d_cubo() -> None:
    assert g.ponderacion(10.0) == pytest.approx(1000.0)


def test_curva_granulometrica() -> None:
    curva = g.curva_granulometrica([30.0, 10.0, 20.0])
    assert [p.diametro_mm for p in curva] == [10.0, 20.0, 30.0]
    esperado = [2.778, 25.000, 100.000]
    for punto, p in zip(curva, esperado, strict=True):
        assert punto.pasante_pct == pytest.approx(p, abs=1e-3)


def test_curva_vacia_lanza_datos_insuficientes() -> None:
    with pytest.raises(DatosInsuficientes):
        g.curva_granulometrica([])


@pytest.fixture
def curva_10_20_30() -> list[PuntoCurva]:
    return g.curva_granulometrica([10.0, 20.0, 30.0])


@pytest.mark.parametrize(
    ("x", "esperado"), [(20, 17.750), (50, 23.333), (90, 28.667), (25, 20.0)]
)
def test_percentil_dx_interpolacion_lineal(
    curva_10_20_30: list[PuntoCurva], x: float, esperado: float
) -> None:
    assert g.percentil_dx(curva_10_20_30, x) == pytest.approx(esperado, abs=1e-3)


def test_percentil_bajo_el_primer_punto_devuelve_diametro_menor(
    curva_10_20_30: list[PuntoCurva],
) -> None:
    assert g.percentil_dx(curva_10_20_30, 1.0) == 10.0


def test_percentil_sobre_el_ultimo_punto_devuelve_diametro_mayor(
    curva_10_20_30: list[PuntoCurva],
) -> None:
    assert g.percentil_dx(curva_10_20_30, 100.0) == 30.0


def test_percentil_con_curva_vacia_lanza_datos_insuficientes() -> None:
    with pytest.raises(DatosInsuficientes):
        g.percentil_dx([], 50.0)


def test_indice_n_rosin_rammler_exacto() -> None:
    xs = [50.0, 100.0, 200.0]
    curva = [
        PuntoCurva(x, 100.0 * (1.0 - math.exp(-((x / 100.0) ** 1.5)))) for x in xs
    ]
    assert g.indice_uniformidad_n(curva) == pytest.approx(1.5, abs=1e-9)


def test_indice_n_ignora_puntos_con_p_igual_a_100() -> None:
    xs = [50.0, 100.0, 200.0]
    curva = [
        PuntoCurva(x, 100.0 * (1.0 - math.exp(-((x / 100.0) ** 1.5)))) for x in xs
    ]
    curva.append(PuntoCurva(400.0, 100.0))
    assert g.indice_uniformidad_n(curva) == pytest.approx(1.5, abs=1e-9)


def test_indice_n_con_un_solo_punto_valido_lanza_datos_insuficientes() -> None:
    curva = [PuntoCurva(10.0, 30.0), PuntoCurva(20.0, 100.0)]
    with pytest.raises(DatosInsuficientes):
        g.indice_uniformidad_n(curva)


def test_indice_n_con_diametros_iguales_lanza_datos_insuficientes() -> None:
    curva = [PuntoCurva(10.0, 30.0), PuntoCurva(10.0, 60.0)]
    with pytest.raises(DatosInsuficientes):
        g.indice_uniformidad_n(curva)


def test_calcular_lista_vacia_lanza_datos_insuficientes() -> None:
    with pytest.raises(DatosInsuficientes):
        g.calcular([])


def test_calcular_devuelve_resultado_completo() -> None:
    diametros = [10.0, 20.0, 30.0, 40.0]
    resultado = g.calcular(diametros)
    assert resultado.numero_fragmentos == 4
    assert len(resultado.curva) == 4
    assert resultado.d20 <= resultado.d50 <= resultado.d60 <= resultado.d80 <= resultado.d90
    assert resultado.d90 <= 40.0
    assert resultado.indice_n > 0
