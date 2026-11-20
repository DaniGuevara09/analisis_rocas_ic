"""Informe de resultados en Excel (.xlsx): hojas Resumen, Curva y Fragmentos (RF-09, RNF-07).

Los números se guardan como números, así que Excel los muestra bien en cualquier
configuración regional.
"""

from app.adaptadores.entrada.api.esquemas import SUPUESTOS
from app.adaptadores.entrada.api.libro_xlsx import Celda, Hoja, Negrita, generar_libro
from app.dominio import granulometria
from app.dominio.modelo import Analisis, OrigenFragmento, ReporteGranulometrico

NOTA_ESTIMACION = "El resultado es una estimación y no reemplaza el tamizado."


def _datos_generales(analisis: Analisis, reporte: ReporteGranulometrico) -> list[list[Celda]]:
    calibracion = analisis.calibracion
    imagen = analisis.imagen
    return [
        [Negrita("Informe granulométrico"), analisis.nombre],
        ["Fecha del análisis", analisis.fecha_creacion.strftime("%Y-%m-%d %H:%M")],
        ["Resolución de la imagen (px)", f"{imagen.ancho_px} × {imagen.alto_px}"],
        [
            "Longitud del objeto de referencia (mm)",
            calibracion.longitud_real_mm if calibracion else None,
        ],
        ["Escala (mm/px)", round(analisis.factor_mm_por_px(), 6)],
        ["Fragmentos medidos (N)", reporte.resultado.numero_fragmentos],
    ]


def _indicadores(reporte: ReporteGranulometrico) -> list[list[Celda]]:
    r = reporte.resultado
    return [
        [Negrita("Indicador"), Negrita("Valor"), Negrita("Unidad")],
        ["D20", r.d20, "mm"],
        ["D50", r.d50, "mm"],
        ["D60", r.d60, "mm"],
        ["D80", r.d80, "mm"],
        ["D90", r.d90, "mm"],
        ["Tamaño característico x_c (Rosin-Rammler)", r.tamano_caracteristico_mm, "mm"],
        ["Índice de uniformidad n (Rosin-Rammler)", round(r.indice_n, 3), "—"],
    ]


def _rangos(reporte: ReporteGranulometrico) -> list[list[Celda]]:
    filas: list[list[Celda]] = [
        [
            Negrita("Rango"),
            Negrita("Desde (mm)"),
            Negrita("Hasta (mm)"),
            Negrita("Color"),
            Negrita("Fragmentos"),
            Negrita("% en masa"),
        ]
    ]
    for indice, rango in enumerate(reporte.rangos):
        clase = reporte.histograma[indice]
        superior = rango.limite_superior_mm
        filas.append(
            [
                reporte.nombres_rangos[indice],
                rango.limite_inferior_mm,
                "sin límite" if superior is None else superior,
                reporte.colores_rangos[indice],
                clase.numero_fragmentos,
                clase.porcentaje_retenido,
            ]
        )
    return filas


def _hoja_resumen(analisis: Analisis, reporte: ReporteGranulometrico) -> Hoja:
    supuestos: list[list[Celda]] = [[s] for s in [*SUPUESTOS, NOTA_ESTIMACION]]
    filas = [
        *_datos_generales(analisis, reporte),
        [],
        *_indicadores(reporte),
        [],
        *_rangos(reporte),
        [],
        [Negrita("Supuestos y limitaciones")],
        *supuestos,
    ]
    return Hoja("Resumen", filas, anchos=(44, 22, 14, 12, 12, 12))


def _hoja_curva(reporte: ReporteGranulometrico) -> Hoja:
    r = reporte.resultado
    filas: list[list[Celda]] = [
        [
            Negrita("Diámetro (mm)"),
            Negrita("% pasante medido"),
            Negrita("% pasante Rosin-Rammler"),
        ]
    ]
    for punto in r.curva:
        teorico = granulometria.pasante_rosin_rammler(
            punto.diametro_mm, r.indice_n, r.tamano_caracteristico_mm
        )
        filas.append([punto.diametro_mm, punto.pasante_pct, teorico])
    return Hoja("Curva", filas, anchos=(16, 20, 26))


def _hoja_fragmentos(analisis: Analisis, reporte: ReporteGranulometrico) -> Hoja:
    factor = analisis.factor_mm_por_px()
    medidos = {m.id: m for m in reporte.fragmentos}
    filas: list[list[Celda]] = [
        [
            Negrita("N.º"),
            Negrita("Id"),
            Negrita("Origen"),
            Negrita("Área (px²)"),
            Negrita("Área (mm²)"),
            Negrita("Diámetro equivalente (mm)"),
            Negrita("Rango"),
        ]
    ]
    for numero, fragmento in enumerate(analisis.fragmentos, start=1):
        medido = medidos[fragmento.id]
        filas.append(
            [
                numero,
                str(fragmento.id),
                "Modelo" if fragmento.origen is OrigenFragmento.MODELO else "Manual",
                fragmento.area_px(),
                granulometria.area_mm2(fragmento.area_px(), factor),
                medido.diametro_equivalente_mm,
                reporte.nombres_rangos[medido.indice_rango],
            ]
        )
    return Hoja("Fragmentos", filas, anchos=(6, 38, 10, 12, 14, 24, 16))


def generar_xlsx(analisis: Analisis, reporte: ReporteGranulometrico) -> bytes:
    """Bytes del informe .xlsx."""
    return generar_libro(
        [
            _hoja_resumen(analisis, reporte),
            _hoja_curva(reporte),
            _hoja_fragmentos(analisis, reporte),
        ]
    )
