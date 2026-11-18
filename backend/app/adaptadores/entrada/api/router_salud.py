"""Ruta de salud."""
from fastapi import APIRouter

router = APIRouter()


@router.get("/salud")
def salud() -> dict[str, str]:
    """Indica que el servicio está activo."""
    return {"estado": "ok"}
