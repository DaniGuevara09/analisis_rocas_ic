FROM python:3.12-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1     YOLO_CONFIG_DIR=/tmp/Ultralytics

# OpenCV (dependencia de ultralytics) necesita estas bibliotecas en la imagen slim.
RUN apt-get update     && apt-get install -y --no-install-recommends libgl1 libglib2.0-0     && rm -rf /var/lib/apt/lists/*

# torch solo CPU: evita descargar la versión con CUDA (~2.5 GB).
RUN pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu

COPY pyproject.toml ./
RUN pip install --no-cache-dir ".[yolo]"
COPY app ./app
RUN pip install --no-cache-dir --no-deps .

COPY alembic.ini ./
COPY alembic ./alembic
COPY entrypoint.sh ./
RUN chmod +x entrypoint.sh

EXPOSE 8000
CMD ["./entrypoint.sh"]
