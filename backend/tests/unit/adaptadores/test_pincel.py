"""Pruebas unitarias de la lógica de selección y recorte del pincel mágico."""

from app.adaptadores.salida.segmentacion.pincel import (
    cajas_para_trazo,
    es_trazo_envolvente,
    mejor_poligono_para_trazo,
    toca_borde_recorte,
)
from app.dominio.modelo import Poligono, Punto


def rectangulo(x0: float, y0: float, x1: float, y1: float) -> Poligono:
    return Poligono((Punto(x0, y0), Punto(x1, y0), Punto(x1, y1), Punto(x0, y1)))


def test_toque_unico_genera_ventanas_multiescala_hasta_imagen_completa() -> None:
    cajas = cajas_para_trazo(1200, 900, [Punto(600, 450)], radio_px=10.0)
    assert len(cajas) >= 3
    assert cajas[-1] == (0, 0, 1200, 900)


def test_descarta_mascara_cortada_en_recorte_pequeno() -> None:
    caja = (100, 100, 300, 300)
    # Máscara recortada contra los 4 bordes de la ventana pequeña
    cortada = rectangulo(100, 100, 300, 300)
    assert toca_borde_recorte(cortada, caja, 1000, 1000) is True
    assert (
        mejor_poligono_para_trazo(
            [cortada], [Punto(200, 200)], radio_px=10.0, caja=caja, ancho_img=1000, alto_img=1000
        )
        is None
    )


def test_acepta_roca_completa_en_toque_unico() -> None:
    caja = (0, 0, 600, 600)
    roca = rectangulo(150, 150, 350, 320)
    assert toca_borde_recorte(roca, caja, 1000, 1000) is False
    elegido = mejor_poligono_para_trazo(
        [roca], [Punto(250, 240)], radio_px=10.0, caja=caja, ancho_img=1000, alto_img=1000
    )
    assert elegido == roca


def test_enmarcar_borde_reconoce_toda_la_roca_y_no_solo_el_borde() -> None:
    # Trazo rodeando el borde de una roca de 200x200 (centro en 300,300)
    borde = [
        Punto(200, 200),
        Punto(300, 200),
        Punto(400, 200),
        Punto(400, 300),
        Punto(400, 400),
        Punto(300, 400),
        Punto(200, 400),
        Punto(200, 300),
        Punto(205, 205),
    ]
    assert es_trazo_envolvente(borde, radio_px=10.0) is True
    roca = rectangulo(200, 200, 400, 400)
    elegido = mejor_poligono_para_trazo(
        [roca], borde, radio_px=10.0, caja=(0, 0, 600, 600), ancho_img=1000, alto_img=1000
    )
    assert elegido == roca
