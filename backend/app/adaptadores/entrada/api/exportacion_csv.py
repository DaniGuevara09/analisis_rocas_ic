"""Exportación del tamaño de cada fragmento a CSV (RF-09, HU-09).

CSV estándar (RFC 4180): una sola tabla con encabezado, separador "," y punto decimal,
en UTF-8 con BOM. Se lee igual en cualquier configuración regional y con cualquier
script. El informe completo para Excel (indicadores, supuestos, curva) está en
`exportacion_xlsx`.
"""

import csv
import io

from app.dominio import granulometria
from app.dominio.modelo import Analisis, ReporteGranulometrico

ENCABEZADO_CSV = (
    "numero",
    "id",
    "origen",
    "area_px2",
    "area_mm2",
    "diametro_equivalente_mm",
    "rango",
)


def generar_csv(analisis: Analisis, reporte: ReporteGranulometrico) -> str:
    """Texto CSV con una fila por fragmento."""
    salida = io.StringIO()
    escritor = csv.writer(salida, lineterminator="\n")
    escritor.writerow(ENCABEZADO_CSV)
    factor = analisis.factor_mm_por_px()
    medidos = {m.id: m for m in reporte.fragmentos}
    for numero, fragmento in enumerate(analisis.fragmentos, start=1):
        medido = medidos[fragmento.id]
        escritor.writerow(
            [
                numero,
                str(fragmento.id),
                fragmento.origen.value,
                f"{fragmento.area_px():.2f}",
                f"{granulometria.area_mm2(fragmento.area_px(), factor):.2f}",
                f"{medido.diametro_equivalente_mm:.2f}",
                reporte.nombres_rangos[medido.indice_rango],
            ]
        )
    return salida.getvalue()
