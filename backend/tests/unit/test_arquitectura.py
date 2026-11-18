"""Protege la regla hexagonal: las dependencias apuntan hacia adentro."""
import ast
from pathlib import Path

RAIZ_APP = Path(__file__).resolve().parents[2] / "app"

PROHIBIDOS_DOMINIO = {
    "fastapi", "sqlalchemy", "pydantic", "pydantic_settings", "ultralytics", "alembic",
    "boto3", "botocore", "os", "pathlib", "app.aplicacion", "app.adaptadores",
}
PROHIBIDOS_APLICACION = {
    "boto3", "botocore", "fastapi", "sqlalchemy", "pydantic", "pydantic_settings",
    "ultralytics", "alembic",
    "app.adaptadores",
}


def _modulos_importados(archivo: Path) -> set[str]:
    arbol = ast.parse(archivo.read_text(encoding="utf-8"))
    modulos: set[str] = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            modulos.update(alias.name for alias in nodo.names)
        elif isinstance(nodo, ast.ImportFrom) and nodo.level == 0 and nodo.module:
            modulos.add(nodo.module)
    return modulos


def _infracciones(carpeta: str, prohibidos: set[str]) -> list[str]:
    encontradas = []
    for archivo in sorted((RAIZ_APP / carpeta).rglob("*.py")):
        for modulo in _modulos_importados(archivo):
            if any(modulo == p or modulo.startswith(p + ".") for p in prohibidos):
                encontradas.append(f"{archivo.relative_to(RAIZ_APP)} importa {modulo}")
    return encontradas


def test_dominio_no_importa_frameworks_ni_otras_capas() -> None:
    assert _infracciones("dominio", PROHIBIDOS_DOMINIO) == []


def test_aplicacion_no_importa_adaptadores_ni_frameworks() -> None:
    assert _infracciones("aplicacion", PROHIBIDOS_APLICACION) == []
