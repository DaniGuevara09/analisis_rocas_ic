"""Configuración por variables de entorno."""

from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Configuracion(BaseSettings):
    """Variables de entorno de la aplicación."""

    # hide_input_in_errors: un error de validación nunca imprime los valores (secretos S3).
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", hide_input_in_errors=True)

    postgres_user: str = ""
    postgres_password: str = ""
    postgres_db: str = ""
    database_url: str = "postgresql+psycopg://rocas:rocas@localhost:5432/analisis_rocas"
    ruta_imagenes: str = "/datos/imagenes"
    ruta_modelo: str = "/app/modelos/best.pt"
    ruta_modelo_unet: str = "/app/modelos/unet_best.pth"
    segmentacion_refinar_unet: bool = False
    segmentacion_confianza: float = 0.25
    segmentacion_imgsz: int = 640
    segmentacion_max_det: int = 1000
    almacen_imagenes: Literal["local", "s3"] = "local"
    s3_endpoint_url: str = ""
    s3_bucket: str = ""
    s3_access_key_id: str = ""
    s3_secret_access_key: str = ""
    s3_region: str = "auto"

    @model_validator(mode="after")
    def _exigir_s3_completo(self) -> "Configuracion":
        """Con almacén S3, las cuatro variables de conexión son obligatorias."""
        if self.almacen_imagenes == "s3":
            faltantes = [
                nombre.upper()
                for nombre in (
                    "s3_endpoint_url",
                    "s3_bucket",
                    "s3_access_key_id",
                    "s3_secret_access_key",
                )
                if not getattr(self, nombre)
            ]
            if faltantes:
                raise ValueError("ALMACEN_IMAGENES=s3 requiere definir: " + ", ".join(faltantes))
        return self


configuracion = Configuracion()
