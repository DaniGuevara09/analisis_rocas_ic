"""Escritor mínimo de libros .xlsx (Office Open XML) con la librería estándar.

Solo lo necesario para el informe: varias hojas, texto, números, negrita y anchos de
columna. Evita agregar una dependencia para tres tablas.
"""

import io
import zipfile
from collections.abc import Sequence
from dataclasses import dataclass
from xml.sax.saxutils import escape

_ESPACIO = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_RELACION = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_PAQUETE = "http://schemas.openxmlformats.org/package/2006/relationships"
_TIPOS = "http://schemas.openxmlformats.org/package/2006/content-types"
_TIPO = "application/vnd.openxmlformats-officedocument.spreadsheetml"
_CABECERA = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'

# Índices de estilo (cellXfs en styles.xml)
_NORMAL, _NEGRITA, _DECIMAL = 0, 1, 2


@dataclass(frozen=True)
class Negrita:
    """Texto en negrita (encabezados)."""

    texto: str


Celda = str | int | float | Negrita | None


@dataclass(frozen=True)
class Hoja:
    """Hoja con nombre (máximo 31 caracteres), filas y anchos de columna."""

    nombre: str
    filas: Sequence[Sequence[Celda]]
    anchos: Sequence[float] = ()


def _columna(indice: int) -> str:
    """Letra de la columna para un índice desde 0 (0 -> A, 26 -> AA)."""
    letras = ""
    indice += 1
    while indice:
        indice, resto = divmod(indice - 1, 26)
        letras = chr(65 + resto) + letras
    return letras


def _texto(referencia: str, texto: str, estilo: int) -> str:
    return (
        f'<c r="{referencia}" t="inlineStr" s="{estilo}">'
        f'<is><t xml:space="preserve">{escape(texto)}</t></is></c>'
    )


def _celda(referencia: str, valor: Celda) -> str:
    if valor is None or valor == "":
        return ""
    if isinstance(valor, Negrita):
        return _texto(referencia, valor.texto, _NEGRITA)
    if isinstance(valor, bool) or not isinstance(valor, int | float):
        return _texto(referencia, str(valor), _NORMAL)
    estilo = _DECIMAL if isinstance(valor, float) else _NORMAL
    return f'<c r="{referencia}" s="{estilo}"><v>{valor!r}</v></c>'


def _hoja_xml(hoja: Hoja) -> str:
    columnas = "".join(
        f'<col min="{i}" max="{i}" width="{ancho}" customWidth="1"/>'
        for i, ancho in enumerate(hoja.anchos, start=1)
    )
    filas = []
    for numero, fila in enumerate(hoja.filas, start=1):
        celdas = "".join(_celda(f"{_columna(i)}{numero}", v) for i, v in enumerate(fila))
        filas.append(f'<row r="{numero}">{celdas}</row>')
    bloque_columnas = f"<cols>{columnas}</cols>" if columnas else ""
    return (
        f'{_CABECERA}<worksheet xmlns="{_ESPACIO}">{bloque_columnas}'
        f"<sheetData>{''.join(filas)}</sheetData></worksheet>"
    )


_ESTILOS = (
    f'{_CABECERA}<styleSheet xmlns="{_ESPACIO}">'
    '<fonts count="2"><font><sz val="11"/><name val="Calibri"/></font>'
    '<font><b/><sz val="11"/><name val="Calibri"/></font></fonts>'
    '<fills count="2"><fill><patternFill patternType="none"/></fill>'
    '<fill><patternFill patternType="gray125"/></fill></fills>'
    '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>'
    '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
    '<cellXfs count="3"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>'
    '<xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1"/>'
    '<xf numFmtId="2" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/>'
    "</cellXfs></styleSheet>"
)


def _partes_fijas(hojas: Sequence[Hoja]) -> dict[str, str]:
    cantidad = len(hojas)
    tipos = "".join(
        f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="{_TIPO}.worksheet+xml"/>'
        for i in range(1, cantidad + 1)
    )
    hojas_libro = "".join(
        f'<sheet name="{escape(h.nombre[:31])}" sheetId="{i}" r:id="rId{i}"/>'
        for i, h in enumerate(hojas, start=1)
    )
    relaciones = "".join(
        f'<Relationship Id="rId{i}" Type="{_RELACION}/worksheet" Target="worksheets/sheet{i}.xml"/>'
        for i in range(1, cantidad + 1)
    )
    return {
        "[Content_Types].xml": (
            f'{_CABECERA}<Types xmlns="{_TIPOS}">'
            '<Default Extension="rels" '
            'ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            f'<Override PartName="/xl/workbook.xml" ContentType="{_TIPO}.sheet.main+xml"/>'
            f'<Override PartName="/xl/styles.xml" ContentType="{_TIPO}.styles+xml"/>'
            f"{tipos}</Types>"
        ),
        "_rels/.rels": (
            f'{_CABECERA}<Relationships xmlns="{_PAQUETE}">'
            f'<Relationship Id="rId1" Type="{_RELACION}/officeDocument" '
            'Target="xl/workbook.xml"/></Relationships>'
        ),
        "xl/workbook.xml": (
            f'{_CABECERA}<workbook xmlns="{_ESPACIO}" xmlns:r="{_RELACION}">'
            f"<sheets>{hojas_libro}</sheets></workbook>"
        ),
        "xl/_rels/workbook.xml.rels": (
            f'{_CABECERA}<Relationships xmlns="{_PAQUETE}">{relaciones}'
            f'<Relationship Id="rId{cantidad + 1}" Type="{_RELACION}/styles" '
            'Target="styles.xml"/></Relationships>'
        ),
        "xl/styles.xml": _ESTILOS,
    }


def generar_libro(hojas: Sequence[Hoja]) -> bytes:
    """Bytes de un archivo .xlsx con las hojas dadas."""
    partes = _partes_fijas(hojas)
    for i, hoja in enumerate(hojas, start=1):
        partes[f"xl/worksheets/sheet{i}.xml"] = _hoja_xml(hoja)
    salida = io.BytesIO()
    with zipfile.ZipFile(salida, "w", zipfile.ZIP_DEFLATED) as archivo:
        for nombre, contenido in partes.items():
            archivo.writestr(nombre, contenido)
    return salida.getvalue()
