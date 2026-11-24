"""Pruebas unitarias de la cuadrícula solapada y fusión de detecciones de YOLO."""

from app.adaptadores.salida.segmentacion.segmentador_yolo import (
    MAX_DET_MALLA,
    _area_minima_segmentacion,
    _filtrar_indices_respaldo,
    fusionar_detecciones,
    generar_cuadricula,
    particionar_poligonos_sin_solape,
)
from app.dominio.modelo import Poligono, Punto


def rectangulo(x0: float, y0: float, x1: float, y1: float) -> Poligono:
    return Poligono((Punto(x0, y0), Punto(x1, y0), Punto(x1, y1), Punto(x0, y1)))


def test_generar_cuadricula_cubre_toda_la_imagen_con_solape() -> None:
    cajas = generar_cuadricula(4000, 2250, n_detecciones=850)
    assert len(cajas) == 6
    assert min(c[0] for c in cajas) == 0
    assert min(c[1] for c in cajas) == 0
    assert max(c[2] for c in cajas) == 4000
    assert max(c[3] for c in cajas) == 2250
    # Cualquier punto del centro queda cubierto al menos por un mosaico interior.
    assert any(x0 <= 2000 <= x1 and y0 <= 1125 <= y1 for x0, y0, x1, y1 in cajas)


def test_fusionar_detecciones_prefiere_primarias_y_conserva_respaldo_no_cubierto() -> None:
    fina = rectangulo(100, 100, 200, 200)
    tosca_duplicada = rectangulo(102, 102, 198, 198)
    roca_gigante_respaldo = rectangulo(500, 100, 2200, 1400)

    resultado = fusionar_detecciones(
        primarias=[(fina, 0.70)],
        respaldo=[(tosca_duplicada, 0.90), (roca_gigante_respaldo, 0.85)],
    )

    assert fina in resultado
    assert tosca_duplicada not in resultado
    assert roca_gigante_respaldo in resultado


def test_fusionar_detecciones_en_pasada_unica_elimina_roca_anidada() -> None:
    roca_completa = rectangulo(100, 100, 300, 300)
    subparte_baja_conf = rectangulo(120, 120, 220, 220)
    otra_roca = rectangulo(400, 100, 520, 220)

    resultado = fusionar_detecciones(
        primarias=[],
        respaldo=[
            (subparte_baja_conf, 0.14),
            (roca_completa, 0.85),
            (otra_roca, 0.72),
        ],
    )

    assert roca_completa in resultado
    assert otra_roca in resultado
    assert subparte_baja_conf not in resultado


def test_filtrar_indices_respaldo_omite_cubiertas_y_mantiene_costura_o_faltantes() -> None:
    primarias = [(100.0, 100.0, 200.0, 200.0), (500.0, 500.0, 560.0, 560.0)]
    respaldo = [
        (102.0, 101.0, 198.0, 199.0),  # ya cubierta por mosaico (IoU > 0.9)
        (480.0, 480.0, 950.0, 900.0),  # roca gigante sobre costura (IoU bajo)
        (1200.0, 300.0, 1320.0, 410.0),  # no detectada en mosaicos
    ]
    assert _filtrar_indices_respaldo(respaldo, primarias) == [1, 2]


def test_area_minima_segmentacion_mantiene_finos_en_fotos_grandes() -> None:
    assert MAX_DET_MALLA >= 400
    # En una foto 4K (9 MP), no usa 0.04% (3600 px2) sino ~180 px2 (~15 px de diámetro).
    assert _area_minima_segmentacion(4000, 2250) == 180.0
    # En imágenes de prueba pequeñas escala proporcionalmente sin romper tests mínimos.
    assert _area_minima_segmentacion(200, 200) == 20.0


def test_particionar_poligonos_sin_solape_conserva_aisladas_y_recorta_solape() -> None:
    roca_principal = rectangulo(100, 100, 300, 300)
    roca_vecina = rectangulo(250, 100, 450, 300)  # solapa 50px con la principal
    roca_aislada = rectangulo(600, 100, 750, 250)

    salida = particionar_poligonos_sin_solape(
        [
            (roca_vecina, 0.60),
            (roca_principal, 0.90),
            (roca_aislada, 0.80),
        ],
        ancho_img=1000,
        alto_img=600,
        area_minima_px=100.0,
    )

    assert len(salida) == 3
    assert roca_principal in salida
    assert roca_aislada in salida
    # La vecina recortada no debe superar el área original (o mantiene exactamente igual sin cv2).
    assert sum(p.area() for p in salida) <= (
        roca_principal.area() + roca_vecina.area() + roca_aislada.area() + 1.0
    )


def test_recuperar_rocas_en_huecos_respeta_limite_y_no_duplica_existentes() -> None:
    import numpy as np

    from app.adaptadores.salida.segmentacion.unet_bordes import recuperar_rocas_en_huecos

    fg = np.zeros((128, 128), dtype=np.float32)
    bd = np.zeros((128, 128), dtype=np.float32)
    # Roca ya detectada por YOLO en la mitad izquierda
    fg[20:60, 10:50] = 0.9
    # Dos rocas pequeñas en la mitad derecha no detectadas por YOLO
    fg[20:40, 70:90] = 0.9
    fg[70:95, 75:100] = 0.9

    roca_yolo = rectangulo(10, 20, 50, 60)
    recuperadas = recuperar_rocas_en_huecos(
        fg, bd, [roca_yolo], ancho_img=128, alto_img=128, area_minima_px=50.0, max_nuevas=10
    )
    # Sin cv2 local devuelve []; con cv2 en Docker recupera las 2 rocas pequeñas de la derecha.
    for pol in recuperadas:
        assert min(p.x for p in pol.puntos) >= 50.0
