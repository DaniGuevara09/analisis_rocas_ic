"""Pruebas de la edición de fragmentos (RF-05) y del reporte granulométrico (RF-06 a RF-08)."""

import pytest

from app.dominio.errores import (
    DatosInsuficientes,
    DatosNoValidos,
    EscalaNoCalibrada,
    FragmentoEnRegionExcluida,
    PoligonoNoValido,
)
from app.dominio.modelo import (
    Analisis,
    EstadoAnalisis,
    Fragmento,
    Imagen,
    OrigenFragmento,
    Poligono,
    Punto,
)


def cuadrado(x: float, y: float, lado: float) -> Poligono:
    return Poligono(
        (Punto(x, y), Punto(x + lado, y), Punto(x + lado, y + lado), Punto(x, y + lado))
    )


def analisis_sin_calibrar() -> Analisis:
    return Analisis.crear("pila", Imagen(ruta="a.jpg", ancho_px=1920, alto_px=1080, formato="JPG"))


def analisis_calibrado() -> Analisis:
    analisis = analisis_sin_calibrar()
    analisis.calibrar(Punto(0, 0), Punto(300, 400), 250.0)  # 0.5 mm/px
    return analisis


def manual(poligono: Poligono) -> Fragmento:
    return Fragmento.crear(poligono, OrigenFragmento.MANUAL)


# --- reemplazar_fragmentos --------------------------------------------------
def test_reemplazar_fragmentos_conserva_ids_y_origen() -> None:
    analisis = analisis_calibrado()
    modelo = analisis.registrar_fragmentos([cuadrado(0, 0, 10)], OrigenFragmento.MODELO)[0]
    nuevo = manual(cuadrado(50, 50, 20))

    analisis.reemplazar_fragmentos([modelo, nuevo])

    assert [f.id for f in analisis.fragmentos] == [modelo.id, nuevo.id]
    assert [f.origen for f in analisis.fragmentos] == [
        OrigenFragmento.MODELO,
        OrigenFragmento.MANUAL,
    ]
    assert analisis.estado is EstadoAnalisis.SEGMENTADO


def test_reemplazar_fragmentos_con_lista_vacia_borra_todos() -> None:
    analisis = analisis_calibrado()
    analisis.registrar_fragmentos([cuadrado(0, 0, 10)], OrigenFragmento.MODELO)
    analisis.reemplazar_fragmentos([])
    assert analisis.fragmentos == []


def test_reemplazar_fragmentos_sin_calibracion_lanza_escala_no_calibrada() -> None:
    analisis = analisis_sin_calibrar()
    with pytest.raises(EscalaNoCalibrada):
        analisis.reemplazar_fragmentos([manual(cuadrado(0, 0, 10))])


def test_reemplazar_fragmentos_en_region_excluida_lanza_error_y_no_cambia() -> None:
    analisis = analisis_calibrado()
    analisis.excluir_region(cuadrado(100, 100, 100))
    previo = analisis.registrar_fragmentos([cuadrado(0, 0, 10)], OrigenFragmento.MODELO)
    with pytest.raises(FragmentoEnRegionExcluida):
        analisis.reemplazar_fragmentos([manual(cuadrado(140, 140, 10))])
    assert analisis.fragmentos == previo


def test_reemplazar_fragmentos_con_ids_repetidos_lanza_datos_no_validos() -> None:
    analisis = analisis_calibrado()
    fragmento = manual(cuadrado(0, 0, 10))
    with pytest.raises(DatosNoValidos):
        analisis.reemplazar_fragmentos([fragmento, fragmento])


def test_reemplazar_fragmentos_con_vertice_fuera_de_la_imagen_lanza_error() -> None:
    analisis = analisis_calibrado()
    with pytest.raises(PoligonoNoValido):
        analisis.reemplazar_fragmentos([manual(cuadrado(1910, 0, 20))])


# --- generar_reporte --------------------------------------------------------
def test_generar_reporte_clasifica_cada_fragmento() -> None:
    analisis = analisis_calibrado()
    fragmentos = analisis.registrar_fragmentos(
        [cuadrado(0, 0, 10), cuadrado(20, 0, 20), cuadrado(50, 0, 40), cuadrado(100, 0, 80)],
        OrigenFragmento.MODELO,
    )

    reporte = analisis.generar_reporte()

    assert reporte.resultado == analisis.calcular_resultado()
    assert len(reporte.rangos) == 5
    assert [m.id for m in reporte.fragmentos] == [f.id for f in fragmentos]
    factor = analisis.factor_mm_por_px()
    for medido, fragmento in zip(reporte.fragmentos, fragmentos, strict=True):
        assert medido.diametro_equivalente_mm == pytest.approx(
            fragmento.diametro_equivalente_mm(factor)
        )
        assert reporte.rangos[medido.indice_rango].contiene(medido.diametro_equivalente_mm)
    assert sum(c.numero_fragmentos for c in reporte.histograma) == 4


def test_generar_reporte_con_menos_de_tres_fragmentos_lanza_datos_insuficientes() -> None:
    analisis = analisis_calibrado()
    analisis.registrar_fragmentos([cuadrado(0, 0, 10)], OrigenFragmento.MODELO)
    with pytest.raises(DatosInsuficientes):
        analisis.generar_reporte()


def test_generar_reporte_sin_calibracion_lanza_escala_no_calibrada() -> None:
    with pytest.raises(EscalaNoCalibrada):
        analisis_sin_calibrar().generar_reporte()


def test_generar_reporte_usa_la_configuracion_de_rangos() -> None:
    from app.dominio.configuracion import ConfiguracionRangos, ModoRangos

    analisis = analisis_calibrado()
    analisis.registrar_fragmentos(
        [cuadrado(0, 0, 10), cuadrado(20, 0, 20), cuadrado(50, 0, 40), cuadrado(100, 0, 80)],
        OrigenFragmento.MODELO,
    )
    configuracion = ConfiguracionRangos(
        ModoRangos.ABSOLUTO, (10.0,), ("Chicos", "Grandes"), ("#ffffff", "#000000")
    )
    reporte = analisis.generar_reporte(configuracion)
    assert len(reporte.rangos) == 2
    assert reporte.rangos[0].limite_superior_mm == 10.0
    assert reporte.nombres_rangos == ("Chicos", "Grandes")
    assert reporte.colores_rangos == ("#ffffff", "#000000")
    # diámetros: 5,6 / 11,3 / 22,6 / 45,1 mm (factor 0,5) -> uno chico y tres grandes
    assert [m.indice_rango for m in reporte.fragmentos] == [0, 1, 1, 1]
