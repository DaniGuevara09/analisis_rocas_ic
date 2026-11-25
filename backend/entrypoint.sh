#!/bin/sh
# Aplica las migraciones pendientes (con reintentos si la red/BD tarda) y luego inicia el servidor.
set -e

intentos=0
max_intentos=10
until alembic upgrade head; do
  intentos=$((intentos + 1))
  if [ "$intentos" -ge "$max_intentos" ]; then
    echo "Error: no se pudieron aplicar las migraciones tras $max_intentos intentos." >&2
    exit 1
  fi
  echo "Base de datos o DNS no disponible; reintentando migraciones ($intentos/$max_intentos)..." >&2
  sleep 3
done

exec uvicorn app.main:app --host 0.0.0.0 --port 8000
