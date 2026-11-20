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


@pytest.mark.parametrize(("x", "esperado"), [(20, 17.750), (50, 23.333), (90, 28.667), (25, 20.0)])
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
    curva = [PuntoCurva(x, 100.0 * (1.0 - math.exp(-((x / 100.0) ** 1.5)))) for x in xs]
    assert g.indice_uniformidad_n(curva) == pytest.approx(1.5, abs=1e-9)


def test_indice_n_ignora_puntos_con_p_igual_a_100() -> None:
    xs = [50.0, 100.0, 200.0]
    curva = [PuntoCurva(x, 100.0 * (1.0 - math.exp(-((x / 100.0) ** 1.5)))) for x in xs]
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


# --- Ajuste Rosin-Rammler en el tramo central (10 % <= P <= 90 %) -------------
def _rr(x: float, n: float, xc: float) -> float:
    return 100.0 * (1.0 - math.exp(-((x / xc) ** n)))


def test_ajuste_ignora_la_cola_de_finos_por_debajo_del_10_pct() -> None:
    # Tramo central exacto con n = 2 y xc = 100; la cola fina (P < 10 %) sigue otra pendiente.
    centrales = [PuntoCurva(x, _rr(x, 2.0, 100.0)) for x in (40.0, 70.0, 100.0, 140.0)]
    cola = [PuntoCurva(x, _rr(x, 3.5, 160.0)) for x in (5.0, 10.0, 20.0)]
    assert all(p.pasante_pct < 10.0 for p in cola)
    n, xc = g.ajuste_rosin_rammler([*cola, *centrales])
    assert n == pytest.approx(2.0, abs=1e-9)
    assert xc == pytest.approx(100.0, rel=1e-9)


def test_ajuste_ignora_los_puntos_sobre_el_90_pct() -> None:
    centrales = [PuntoCurva(x, _rr(x, 1.2, 300.0)) for x in (100.0, 200.0, 400.0)]
    gruesos = [PuntoCurva(x, 99.0) for x in (900.0, 1000.0)]
    n, _ = g.ajuste_rosin_rammler([*centrales, *gruesos])
    assert n == pytest.approx(1.2, abs=1e-9)


def test_tamano_caracteristico_es_el_tamano_con_63_2_pct_pasante() -> None:
    curva = [PuntoCurva(x, _rr(x, 1.5, 250.0)) for x in (100.0, 200.0, 300.0, 400.0)]
    _, xc = g.ajuste_rosin_rammler(curva)
    assert xc == pytest.approx(250.0, rel=1e-9)


def test_ajuste_con_pocos_puntos_centrales_usa_toda_la_curva() -> None:
    # Solo un punto entre 10 % y 90 %: se ajusta con todos los puntos 0 < P < 100.
    curva = [PuntoCurva(x, _rr(x, 1.5, 100.0)) for x in (20.0, 100.0, 300.0)]
    assert [p.pasante_pct > 90 or p.pasante_pct < 10 for p in curva] == [True, False, True]
    n, xc = g.ajuste_rosin_rammler(curva)
    assert n == pytest.approx(1.5, abs=1e-9)
    assert xc == pytest.approx(100.0, rel=1e-9)


def test_curva_rosin_rammler_pasa_por_xc_y_es_creciente() -> None:
    curva = g.curva_rosin_rammler(2.0, 100.0, 10.0, 1000.0, cantidad=5)
    assert len(curva) == 5
    assert curva[0].diametro_mm == pytest.approx(10.0)
    assert curva[-1].diametro_mm == pytest.approx(1000.0)
    assert curva[2].diametro_mm == pytest.approx(100.0)  # espaciado logarítmico
    assert curva[2].pasante_pct == pytest.approx(100.0 * (1 - math.exp(-1)))
    assert all(a.pasante_pct < b.pasante_pct for a, b in zip(curva, curva[1:], strict=False))


def test_calcular_incluye_xc_y_curva_teorica() -> None:
    resultado = g.calcular([10.0, 20.0, 30.0, 40.0, 50.0])
    assert resultado.tamano_caracteristico_mm > 0
    assert len(resultado.curva_teorica) == g.PUNTOS_CURVA_TEORICA
    assert resultado.curva_teorica[0].diametro_mm == pytest.approx(10.0)
    assert resultado.curva_teorica[-1].diametro_mm == pytest.approx(50.0)
