"""Entorno de Alembic: toma la URL de la base de datos desde DATABASE_URL."""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.adaptadores.salida.persistencia.tablas import Base
from app.config import configuracion

config = context.config
config.set_main_option("sqlalchemy.url", configuracion.database_url.replace("%", "%%"))

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Genera SQL sin conectarse a la base de datos."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Ejecuta las migraciones contra la base de datos."""
    conexion_motor = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with conexion_motor.connect() as conexion:
        context.configure(connection=conexion, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
