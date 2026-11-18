#!/bin/sh
# Aplica las migraciones pendientes y luego inicia el servidor.
set -e
alembic upgrade head
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
