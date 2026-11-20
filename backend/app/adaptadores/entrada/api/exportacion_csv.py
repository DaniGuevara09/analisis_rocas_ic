"""Exportación de resultados a CSV (RF-09, HU-09, RNF-07).

Formato pensado para Excel en español: separador ";", coma decimal y UTF-8 con BOM.
"""

import csv
import io

from app.adaptadores.entrada.api.esquemas import SUPUESTOS
from app.dominio import granulometria
from app.dominio.modelo import Analisis, ReporteGranulometrico


def _numero(valor: float, decimales: int = 2) -> str:
    return f"{valor:.{decimales}f}".replace(".", ",")


def _limite(valor: float | None) -> str:
    return "sin limite" if valor is None else _numero(valor)


def generar_csv(analisis: Analisis, reporte: ReporteGranulometrico) -> str:
    """Texto CSV con datos del análisis, indicadores, supuestos, rangos y fragmentos."""
    salida = io.StringIO()
    escritor = csv.writer(salida, delimiter=";", lineterminator="\n")
    r = reporte.resultado
    factor = analisis.factor_mm_por_px()

    escritor.writerow(["Informe granulometrico", analisis.nombre])
    escritor.writerow(["Fecha", analisis.fecha_creacion.strftime("%Y-%m-%d %H:%M")])
    escritor.writerow(["Imagen (px)", f"{analisis.imagen.ancho_px}x{analisis.imagen.alto_px}"])
    escritor.writerow(["Factor de escala (mm/px)", _numero(factor, 6)])
    escritor.writerow(["Numero de fragmentos", r.numero_fragmentos])
    escritor.writerow([])

    escritor.writerow(["Indicador", "Valor"])
    for nombre, valor in (
        ("D20 (mm)", r.d20),
        ("D50 (mm)", r.d50),
        ("D60 (mm)", r.d60),
        ("D80 (mm)", r.d80),
        ("D90 (mm)", r.d90),
    ):
        escritor.writerow([nombre, _numero(valor)])
    escritor.writerow(["Indice de uniformidad n (Rosin-Rammler)", _numero(r.indice_n, 3)])
    escritor.writerow([])

    escritor.writerow(["Supuestos"])
    for supuesto in [*SUPUESTOS, "El resultado es una estimacion y no reemplaza el tamizado."]:
        escritor.writerow([supuesto])
    escritor.writerow([])

    escritor.writerow(["Rango", "Desde (mm)", "Hasta (mm)", "Color", "Fragmentos"])
    for indice, rango in enumerate(reporte.rangos):
        cantidad = sum(1 for m in reporte.fragmentos if m.indice_rango == indice)
        escritor.writerow(
            [
                reporte.nombres_rangos[indice],
                _numero(rango.limite_inferior_mm),
                _limite(rango.limite_superior_mm),
                reporte.colores_rangos[indice],
                cantidad,
            ]
        )
    escritor.writerow([])

    escritor.writerow(["Curva granulometrica", "Diametro (mm)", "% pasante"])
    for punto in r.curva:
        escritor.writerow(["", _numero(punto.diametro_mm), _numero(punto.pasante_pct)])
    escritor.writerow([])

    escritor.writerow(
        [
            "N",
            "Id",
            "Origen",
            "Area (px2)",
            "Area (mm2)",
            "Diametro equivalente (mm)",
            "Rango",
        ]
    )
    medidos = {m.id: m for m in reporte.fragmentos}
    for numero, fragmento in enumerate(analisis.fragmentos, start=1):
        medido = medidos[fragmento.id]
        escritor.writerow(
            [
                numero,
                str(fragmento.id),
                fragmento.origen.value,
                _numero(fragmento.area_px()),
                _numero(granulometria.area_mm2(fragmento.area_px(), factor)),
                _numero(medido.diametro_equivalente_mm),
                reporte.nombres_rangos[medido.indice_rango],
            ]
        )
    return salida.getvalue()
