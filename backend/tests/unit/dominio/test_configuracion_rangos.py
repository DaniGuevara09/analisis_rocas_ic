"""Pruebas de la configuración de rangos de tamaño y colores (RF-14)."""

import pytest

from app.dominio import granulometria as g
from app.dominio.configuracion import (
    CONFIGURACION_POR_DEFECTO,
    ConfiguracionRangos,
    ModoRangos,
)
from app.dominio.errores import DatosNoValidos
from app.dominio.resultado import RangoTamano

COLORES_3 = ("#86b6ef", "#2a78d6", "#104281")


def config(
    modo: ModoRangos = ModoRangos.ABSOLUTO,
    cortes: tuple[float, ...] = (100.0, 300.0),
    nombres: tuple[str, ...] = ("Finos", "Medios", "Gruesos"),
    colores: tuple[str, ...] = COLORES_3,
) -> ConfiguracionRangos:
    return ConfiguracionRangos(modo=modo, cortes=cortes, nombres=nombres, colores=colores)


def test_por_defecto_son_cinco_rangos_relativos_a_d20_d50_d80_d90() -> None:
    assert CONFIGURACION_POR_DEFECTO.modo is ModoRangos.RELATIVO
    assert CONFIGURACION_POR_DEFECTO.cortes == (20.0, 50.0, 80.0, 90.0)
    assert len(CONFIGURACION_POR_DEFECTO.colores) == 5
    assert len(CONFIGURACION_POR_DEFECTO.nombres) == 5


def test_rangos_absolutos_usan_los_cortes_en_mm() -> None:
    curva = g.curva_granulometrica([10.0, 20.0, 30.0])
    assert config().rangos(curva) == (
        RangoTamano(0.0, 100.0),
        RangoTamano(100.0, 300.0),
        RangoTamano(300.0, None),
    )


def test_rangos_relativos_usan_los_percentiles_de_la_curva() -> None:
    curva = g.curva_granulometrica([10.0, 20.0, 30.0, 40.0])
    rangos = config(modo=ModoRangos.RELATIVO, cortes=(50.0, 80.0)).rangos(curva)
    assert rangos[0] == RangoTamano(0.0, g.percentil_dx(curva, 50.0))
    assert rangos[1] == RangoTamano(g.percentil_dx(curva, 50.0), g.percentil_dx(curva, 80.0))
    assert rangos[2] == RangoTamano(g.percentil_dx(curva, 80.0), None)


def test_configuracion_por_defecto_coincide_con_rangos_por_defecto() -> None:
    resultado = g.calcular([5.0, 12.0, 20.0, 33.0, 50.0, 71.0])
    assert CONFIGURACION_POR_DEFECTO.rangos(resultado.curva) == g.rangos_por_defecto(resultado)


@pytest.mark.parametrize(
    "cortes",
    [(), (300.0, 100.0), (100.0, 100.0), (-1.0, 100.0), (1, 2, 3, 4, 5, 6, 7, 8)],
)
def test_cortes_no_validos_lanzan_datos_no_validos(cortes: tuple[float, ...]) -> None:
    nombres = tuple(f"R{i}" for i in range(len(cortes) + 1))
    colores = tuple("#000000" for _ in range(len(cortes) + 1))
    with pytest.raises(DatosNoValidos):
        config(cortes=cortes, nombres=nombres, colores=colores)


@pytest.mark.parametrize("cortes", [(0.0, 50.0), (50.0, 100.0)])
def test_cortes_relativos_deben_estar_entre_0_y_100(cortes: tuple[float, ...]) -> None:
    with pytest.raises(DatosNoValidos):
        config(modo=ModoRangos.RELATIVO, cortes=cortes)


def test_debe_haber_un_nombre_y_un_color_por_rango() -> None:
    with pytest.raises(DatosNoValidos):
        config(nombres=("a", "b"))
    with pytest.raises(DatosNoValidos):
        config(colores=("#000000", "#ffffff"))


@pytest.mark.parametrize("color", ["rojo", "#12345", "#GGGGGG", "123456"])
def test_color_debe_ser_hexadecimal(color: str) -> None:
    with pytest.raises(DatosNoValidos):
        config(colores=(color, "#2a78d6", "#104281"))


def test_nombres_se_recortan_y_no_pueden_estar_vacios() -> None:
    assert config(nombres=("  Finos ", "Medios", "Gruesos")).nombres[0] == "Finos"
    with pytest.raises(DatosNoValidos):
        config(nombres=("   ", "Medios", "Gruesos"))


def test_colores_se_normalizan_a_minusculas() -> None:
    assert config(colores=("#ABCDEF", "#2a78d6", "#104281")).colores[0] == "#abcdef"
