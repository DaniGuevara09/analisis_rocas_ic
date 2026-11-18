"""Pruebas de rangos de tamaño (RF-06) e histograma (RF-08), con valores calculados a mano."""

import pytest

from app.dominio import granulometria as g
from app.dominio.errores import DatosInsuficientes
from app.dominio.resultado import RangoTamano, ResultadoGranulometrico


def resultado(d20: float, d50: float, d80: float, d90: float) -> ResultadoGranulometrico:
    return ResultadoGranulometrico(
        d20=d20, d50=d50, d60=d50, d80=d80, d90=d90, indice_n=1.0, numero_fragmentos=3, curva=()
    )


# --- Rangos -----------------------------------------------------------------
def test_rangos_por_defecto_se_cortan_en_d20_d50_d80_d90() -> None:
    rangos = g.rangos_por_defecto(resultado(10, 20, 30, 40))
    assert rangos == (
        RangoTamano(0.0, 10.0),
        RangoTamano(10.0, 20.0),
        RangoTamano(20.0, 30.0),
        RangoTamano(30.0, 40.0),
        RangoTamano(40.0, None),
    )


def test_rango_incluye_el_limite_inferior_y_excluye_el_superior() -> None:
    rango = RangoTamano(10.0, 20.0)
    assert rango.contiene(10.0)
    assert rango.contiene(19.99)
    assert not rango.contiene(20.0)


def test_rango_sin_limite_superior_contiene_todo_lo_mayor() -> None:
    assert RangoTamano(40.0, None).contiene(1e9)


@pytest.mark.parametrize(
    ("diametro", "indice"), [(5, 0), (10, 1), (25, 2), (35, 3), (40, 4), (1000, 4)]
)
def test_indice_rango(diametro: float, indice: int) -> None:
    rangos = g.rangos_por_defecto(resultado(10, 20, 30, 40))
    assert g.indice_rango(diametro, rangos) == indice


def test_indice_rango_con_dx_iguales_usa_el_ultimo_rango_valido() -> None:
    rangos = g.rangos_por_defecto(resultado(10, 10, 10, 10))
    assert g.indice_rango(10, rangos) == 4
    assert g.indice_rango(9, rangos) == 0


# --- Histograma -------------------------------------------------------------
def test_histograma_dos_clases_cuenta_y_pondera_por_volumen() -> None:
    clases = g.histograma([1.0, 2.0, 3.0, 4.0], numero_clases=2)
    assert len(clases) == 2
    assert (clases[0].limite_inferior_mm, clases[0].limite_superior_mm) == (1.0, 2.5)
    assert (clases[1].limite_inferior_mm, clases[1].limite_superior_mm) == (2.5, 4.0)
    assert [c.numero_fragmentos for c in clases] == [2, 2]
    # pesos d³: 1 + 8 = 9 y 27 + 64 = 91, total 100
    assert clases[0].porcentaje_retenido == pytest.approx(9.0)
    assert clases[1].porcentaje_retenido == pytest.approx(91.0)


def test_histograma_el_maximo_cae_en_la_ultima_clase() -> None:
    clases = g.histograma([1.0, 10.0], numero_clases=3)
    assert [c.numero_fragmentos for c in clases] == [1, 0, 1]


def test_histograma_numero_de_clases_por_sturges() -> None:
    # n = 8 -> ceil(log2(8)) + 1 = 4
    clases = g.histograma([float(i) for i in range(1, 9)])
    assert len(clases) == 4


def test_histograma_limita_el_numero_de_clases() -> None:
    clases = g.histograma([float(i) for i in range(1, 100_001)])
    assert len(clases) == g.MAXIMO_CLASES_HISTOGRAMA


def test_histograma_con_diametros_iguales_tiene_una_clase() -> None:
    clases = g.histograma([5.0, 5.0, 5.0])
    assert len(clases) == 1
    assert clases[0].numero_fragmentos == 3
    assert clases[0].porcentaje_retenido == pytest.approx(100.0)


def test_histograma_vacio_lanza_datos_insuficientes() -> None:
    with pytest.raises(DatosInsuficientes):
        g.histograma([])


def test_histograma_los_porcentajes_suman_100() -> None:
    clases = g.histograma([1.0, 1.5, 2.2, 3.7, 8.1, 9.9, 12.0])
    assert sum(c.porcentaje_retenido for c in clases) == pytest.approx(100.0)
    assert sum(c.numero_fragmentos for c in clases) == 7
