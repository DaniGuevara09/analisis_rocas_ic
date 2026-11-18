"""Pruebas de las entidades y objetos de valor del dominio."""
import dataclasses
from uuid import UUID

import pytest

from app.dominio.errores import (
    CalibracionNoValida,
    DatosInsuficientes,
    DatosNoValidos,
    EscalaNoCalibrada,
    FormatoImagenNoValido,
    FragmentoEnRegionExcluida,
    FragmentoNoEncontrado,
    ImagenNoValida,
    PoligonoNoValido,
)
from app.dominio.modelo import (
    Analisis,
    Calibracion,
    EstadoAnalisis,
    Fragmento,
    Imagen,
    OrigenFragmento,
    Poligono,
    Punto,
    RegionExcluida,
    ResultadoGranulometrico,
)


def cuadrado(x: float, y: float, lado: float, antihorario: bool = True) -> Poligono:
    puntos = [Punto(x, y), Punto(x + lado, y), Punto(x + lado, y + lado), Punto(x, y + lado)]
    return Poligono(tuple(puntos if antihorario else reversed(puntos)))


def imagen() -> Imagen:
    return Imagen(ruta="a/b.jpg", ancho_px=1920, alto_px=1080, formato="JPG")


def analisis_calibrado() -> Analisis:
    analisis = Analisis.crear("pila 1", imagen())
    analisis.calibrar(Punto(0, 0), Punto(300, 400), 250.0)  # 0.5 mm/px
    return analisis


# --- Poligono ---------------------------------------------------------------
def test_area_cuadrado_10x10() -> None:
    assert cuadrado(0, 0, 10).area() == pytest.approx(100.0, abs=1e-3)


def test_area_igual_en_sentido_horario_y_antihorario() -> None:
    assert cuadrado(0, 0, 10, antihorario=False).area() == pytest.approx(
        cuadrado(0, 0, 10, antihorario=True).area(), abs=1e-3
    )


def test_poligono_con_dos_puntos_lanza_error() -> None:
    with pytest.raises(PoligonoNoValido):
        Poligono((Punto(0, 0), Punto(1, 1)))


def test_poligono_con_puntos_colineales_lanza_error() -> None:
    with pytest.raises(PoligonoNoValido):
        Poligono((Punto(0, 0), Punto(1, 1), Punto(2, 2)))


def test_centroide_de_cuadrado() -> None:
    centro = cuadrado(0, 0, 10).centroide()
    assert (centro.x, centro.y) == (pytest.approx(5.0), pytest.approx(5.0))


def test_centroide_de_triangulo_rectangulo() -> None:
    triangulo = Poligono((Punto(0, 0), Punto(6, 0), Punto(0, 3)))
    centro = triangulo.centroide()
    assert (centro.x, centro.y) == (pytest.approx(2.0), pytest.approx(1.0))


def test_centroide_independiente_del_sentido() -> None:
    centro = cuadrado(0, 0, 10, antihorario=False).centroide()
    assert (centro.x, centro.y) == (pytest.approx(5.0), pytest.approx(5.0))


def test_contiene_punto_interior_y_exterior() -> None:
    poligono = cuadrado(0, 0, 100)
    assert poligono.contiene(Punto(50, 50))
    assert not poligono.contiene(Punto(200, 200))
    assert not poligono.contiene(Punto(-1, 50))


def test_contiene_en_poligono_concavo() -> None:
    forma_l = Poligono(
        (Punto(0, 0), Punto(10, 0), Punto(10, 4), Punto(4, 4), Punto(4, 10), Punto(0, 10))
    )
    assert forma_l.contiene(Punto(2, 8))
    assert not forma_l.contiene(Punto(8, 8))


def test_objetos_de_valor_son_inmutables() -> None:
    with pytest.raises(dataclasses.FrozenInstanceError):
        Punto(0, 0).x = 5  # type: ignore[misc]


# --- Imagen -----------------------------------------------------------------
@pytest.mark.parametrize("formato", ["JPG", "PNG", "png"])
def test_imagen_acepta_jpg_y_png(formato: str) -> None:
    assert Imagen("r", 10, 10, formato).formato == formato


def test_imagen_gif_lanza_formato_no_valido() -> None:
    with pytest.raises(FormatoImagenNoValido):
        Imagen("r", 10, 10, "GIF")


@pytest.mark.parametrize("ancho, alto", [(0, 10), (10, 0), (-5, 10), (10, -5)])
def test_imagen_con_dimensiones_no_positivas_lanza_imagen_no_valida(ancho: int, alto: int) -> None:
    with pytest.raises(ImagenNoValida):
        Imagen("r", ancho, alto, "JPG")


# --- Calibracion ------------------------------------------------------------
def test_factor_mm_por_px_de_calibracion() -> None:
    calibracion = Calibracion(Punto(0, 0), Punto(300, 400), 250.0)
    assert calibracion.factor_mm_por_px() == pytest.approx(0.5, abs=1e-3)


@pytest.mark.parametrize("longitud", [0.0, -5.0])
def test_calibracion_con_longitud_no_positiva_lanza_error(longitud: float) -> None:
    with pytest.raises(CalibracionNoValida):
        Calibracion(Punto(0, 0), Punto(10, 0), longitud)


def test_calibracion_con_puntos_coincidentes_lanza_error() -> None:
    with pytest.raises(CalibracionNoValida):
        Calibracion(Punto(5, 5), Punto(5, 5), 100.0)


# --- Region excluida y fragmento -------------------------------------------
def test_region_excluida_contiene_punto() -> None:
    region = RegionExcluida(cuadrado(0, 0, 100))
    assert region.contiene(Punto(50, 50))
    assert not region.contiene(Punto(200, 200))


def test_fragmento_area_y_diametro_equivalente() -> None:
    fragmento = Fragmento.crear(cuadrado(0, 0, 10), OrigenFragmento.MODELO)
    assert isinstance(fragmento.id, UUID)
    assert fragmento.area_px() == pytest.approx(100.0, abs=1e-3)
    assert fragmento.diametro_equivalente_mm(0.5) == pytest.approx(5.642, abs=1e-3)


# --- Analisis: estados ------------------------------------------------------
def test_crear_analisis_inicia_en_imagen_cargada() -> None:
    analisis = Analisis.crear("pila", imagen())
    assert isinstance(analisis.id, UUID)
    assert analisis.nombre == "pila"
    assert analisis.estado is EstadoAnalisis.IMAGEN_CARGADA
    assert analisis.calibracion is None
    assert analisis.region_excluida is None
    assert analisis.fragmentos == []


def test_registrar_fragmentos_sin_calibrar_lanza_escala_no_calibrada() -> None:
    analisis = Analisis.crear("pila", imagen())
    with pytest.raises(EscalaNoCalibrada):
        analisis.registrar_fragmentos([cuadrado(0, 0, 10)], OrigenFragmento.MODELO)


def test_calibrar_pasa_a_calibrado() -> None:
    analisis = analisis_calibrado()
    assert analisis.estado is EstadoAnalisis.CALIBRADO
    assert analisis.calibracion is not None
    assert analisis.calibracion.factor_mm_por_px() == pytest.approx(0.5)


def test_registrar_fragmentos_pasa_a_segmentado() -> None:
    analisis = analisis_calibrado()
    analisis.registrar_fragmentos([cuadrado(0, 0, 10)], OrigenFragmento.MODELO)
    assert analisis.estado is EstadoAnalisis.SEGMENTADO
    assert len(analisis.fragmentos) == 1


def test_recalibrar_segmentado_mantiene_segmentado() -> None:
    analisis = analisis_calibrado()
    analisis.registrar_fragmentos([cuadrado(0, 0, 10)], OrigenFragmento.MODELO)
    analisis.calibrar(Punto(0, 0), Punto(100, 0), 100.0)
    assert analisis.estado is EstadoAnalisis.SEGMENTADO
    assert analisis.calibracion is not None
    assert analisis.calibracion.factor_mm_por_px() == pytest.approx(1.0)


def test_calibrar_con_datos_invalidos_no_cambia_el_estado() -> None:
    analisis = Analisis.crear("pila", imagen())
    with pytest.raises(CalibracionNoValida):
        analisis.calibrar(Punto(0, 0), Punto(0, 0), 100.0)
    assert analisis.estado is EstadoAnalisis.IMAGEN_CARGADA
    assert analisis.calibracion is None


# --- Analisis: nombre -------------------------------------------------------
def test_crear_recorta_el_nombre() -> None:
    assert Analisis.crear("  pila  ", imagen()).nombre == "pila"


@pytest.mark.parametrize("nombre", ["", "   ", "x" * 151])
def test_crear_con_nombre_no_valido_lanza_datos_no_validos(nombre: str) -> None:
    with pytest.raises(DatosNoValidos):
        Analisis.crear(nombre, imagen())


def test_crear_acepta_nombre_de_150_caracteres() -> None:
    assert len(Analisis.crear("x" * 150, imagen()).nombre) == 150


def test_renombrar_recorta_y_asigna() -> None:
    analisis = Analisis.crear("a", imagen())
    analisis.renombrar("  nuevo ")
    assert analisis.nombre == "nuevo"


@pytest.mark.parametrize("nombre", ["", "  ", "x" * 151])
def test_renombrar_con_nombre_no_valido_no_cambia_el_nombre(nombre: str) -> None:
    analisis = Analisis.crear("a", imagen())
    with pytest.raises(DatosNoValidos):
        analisis.renombrar(nombre)
    assert analisis.nombre == "a"


# --- Analisis: puntos dentro de la imagen (1920x1080) -----------------------
@pytest.mark.parametrize(
    "inicio, fin",
    [
        (Punto(-1, 0), Punto(100, 100)),
        (Punto(0, 0), Punto(1921, 100)),
        (Punto(0, 0), Punto(100, 1081)),
        (Punto(0, -0.5), Punto(100, 100)),
        (Punto(float("nan"), 0), Punto(100, 100)),
    ],
)
def test_calibrar_con_puntos_fuera_de_la_imagen_lanza_error(inicio: Punto, fin: Punto) -> None:
    analisis = Analisis.crear("pila", imagen())
    with pytest.raises(CalibracionNoValida):
        analisis.calibrar(inicio, fin, 100.0)
    assert analisis.calibracion is None
    assert analisis.estado is EstadoAnalisis.IMAGEN_CARGADA


def test_calibrar_con_puntos_justo_en_el_borde_es_valido() -> None:
    analisis = Analisis.crear("pila", imagen())
    analisis.calibrar(Punto(0, 0), Punto(1920, 1080), 100.0)
    assert analisis.estado is EstadoAnalisis.CALIBRADO


def test_excluir_region_con_vertice_fuera_de_la_imagen_lanza_error() -> None:
    analisis = analisis_calibrado()
    analisis.registrar_fragmentos([cuadrado(45, 45, 10)], OrigenFragmento.MODELO)
    with pytest.raises(PoligonoNoValido):
        analisis.excluir_region(cuadrado(1900, 1000, 100))  # llega a x=2000
    assert analisis.region_excluida is None
    assert len(analisis.fragmentos) == 1


def test_excluir_region_con_vertice_negativo_lanza_error() -> None:
    with pytest.raises(PoligonoNoValido):
        analisis_calibrado().excluir_region(cuadrado(-1, 0, 100))


def test_excluir_region_justo_en_el_borde_es_valida() -> None:
    analisis = analisis_calibrado()
    analisis.excluir_region(cuadrado(1820, 980, 100))  # hasta (1920, 1080)
    assert analisis.region_excluida is not None


# --- Analisis: region excluida ---------------------------------------------
def test_fragmento_con_centroide_en_region_excluida_no_se_registra() -> None:
    analisis = analisis_calibrado()
    analisis.excluir_region(cuadrado(0, 0, 100))
    registrados = analisis.registrar_fragmentos(
        [cuadrado(45, 45, 10), cuadrado(195, 195, 10)], OrigenFragmento.MODELO
    )
    assert len(registrados) == 1
    assert len(analisis.fragmentos) == 1
    centro = analisis.fragmentos[0].poligono.centroide()
    assert (centro.x, centro.y) == (pytest.approx(200.0), pytest.approx(200.0))


def test_quitar_region_excluida() -> None:
    analisis = analisis_calibrado()
    analisis.excluir_region(cuadrado(0, 0, 100))
    assert analisis.region_excluida is not None
    analisis.quitar_region_excluida()
    assert analisis.region_excluida is None
    registrados = analisis.registrar_fragmentos([cuadrado(45, 45, 10)], OrigenFragmento.MODELO)
    assert len(registrados) == 1


def test_excluir_region_elimina_fragmentos_existentes_cuyo_centroide_cae_dentro() -> None:
    analisis = analisis_calibrado()
    analisis.registrar_fragmentos([cuadrado(45, 45, 10)], OrigenFragmento.MODELO)
    analisis.agregar_fragmento(cuadrado(10, 10, 10))  # manual, centroide (15, 15)
    fuera = analisis.agregar_fragmento(cuadrado(195, 195, 10))
    analisis.excluir_region(cuadrado(0, 0, 100))
    assert analisis.fragmentos == [fuera]
    assert analisis.region_excluida is not None


def test_registrar_fragmentos_reemplaza_los_existentes() -> None:
    analisis = analisis_calibrado()
    analisis.agregar_fragmento(cuadrado(0, 0, 10))
    analisis.registrar_fragmentos([cuadrado(50, 50, 10)], OrigenFragmento.MODELO)
    nuevos = analisis.registrar_fragmentos(
        [cuadrado(100, 100, 10), cuadrado(200, 200, 10)], OrigenFragmento.MODELO
    )
    assert analisis.fragmentos == nuevos
    assert len(analisis.fragmentos) == 2


def test_registrar_fragmentos_vacio_deja_el_analisis_sin_fragmentos() -> None:
    analisis = analisis_calibrado()
    analisis.agregar_fragmento(cuadrado(0, 0, 10))
    assert analisis.registrar_fragmentos([], OrigenFragmento.MODELO) == []
    assert analisis.fragmentos == []


def test_agregar_fragmento_en_region_excluida_lanza_error() -> None:
    analisis = analisis_calibrado()
    analisis.excluir_region(cuadrado(0, 0, 100))
    with pytest.raises(FragmentoEnRegionExcluida):
        analisis.agregar_fragmento(cuadrado(45, 45, 10))
    assert analisis.fragmentos == []


# --- Analisis: fragmentos manuales y resultado ------------------------------
def test_agregar_fragmento_manual() -> None:
    analisis = analisis_calibrado()
    fragmento = analisis.agregar_fragmento(cuadrado(0, 0, 10))
    assert fragmento.origen is OrigenFragmento.MANUAL
    assert analisis.fragmentos == [fragmento]
    assert analisis.estado is EstadoAnalisis.SEGMENTADO


def test_agregar_fragmento_sin_calibrar_lanza_error() -> None:
    analisis = Analisis.crear("pila", imagen())
    with pytest.raises(EscalaNoCalibrada):
        analisis.agregar_fragmento(cuadrado(0, 0, 10))


def test_eliminar_fragmento() -> None:
    analisis = analisis_calibrado()
    fragmento = analisis.agregar_fragmento(cuadrado(0, 0, 10))
    analisis.eliminar_fragmento(fragmento.id)
    assert analisis.fragmentos == []


def test_eliminar_fragmento_inexistente_lanza_error() -> None:
    analisis = analisis_calibrado()
    with pytest.raises(FragmentoNoEncontrado):
        analisis.eliminar_fragmento(UUID(int=1))


def test_calcular_resultado_sin_calibrar_lanza_escala_no_calibrada() -> None:
    analisis = Analisis.crear("pila", imagen())
    with pytest.raises(EscalaNoCalibrada):
        analisis.calcular_resultado()


def test_calcular_resultado_sin_fragmentos_lanza_datos_insuficientes() -> None:
    with pytest.raises(DatosInsuficientes):
        analisis_calibrado().calcular_resultado()


def test_calcular_resultado_usa_el_factor_de_la_calibracion() -> None:
    analisis = analisis_calibrado()  # 0.5 mm/px
    for lado in (10, 20, 30, 40):
        analisis.agregar_fragmento(cuadrado(0, 0, lado))
    resultado = analisis.calcular_resultado()
    assert isinstance(resultado, ResultadoGranulometrico)
    assert resultado.numero_fragmentos == 4
    # lado 10 px -> 5.642 mm (area 25 mm2); el menor diametro de la curva
    assert resultado.curva[0].diametro_mm == pytest.approx(5.642, abs=1e-3)
    # recalibrar a 1.0 mm/px duplica los diametros
    analisis.calibrar(Punto(0, 0), Punto(100, 0), 100.0)
    nuevo = analisis.calcular_resultado()
    assert nuevo.curva[0].diametro_mm == pytest.approx(2 * 5.642, abs=1e-2)


def test_calcular_resultado_con_dos_fragmentos_lanza_datos_insuficientes() -> None:
    analisis = analisis_calibrado()
    analisis.agregar_fragmento(cuadrado(0, 0, 10))
    analisis.agregar_fragmento(cuadrado(0, 0, 20))
    with pytest.raises(DatosInsuficientes):
        analisis.calcular_resultado()


def test_factor_mm_por_px_del_analisis_calibrado() -> None:
    assert analisis_calibrado().factor_mm_por_px() == pytest.approx(0.5)


def test_factor_mm_por_px_sin_calibrar_lanza_escala_no_calibrada() -> None:
    with pytest.raises(EscalaNoCalibrada):
        Analisis.crear("pila", imagen()).factor_mm_por_px()
