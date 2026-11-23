# Dockerfile es semejante al archivo requirements
# 1. Usamos una versión oficial y ligera de Python como base
FROM python:3.10-slim

# 2. Creamos una carpeta de trabajo dentro de la cajita
WORKDIR /app

# 3. Instalamos FastAPI y Uvicorn (el servidor web)
RUN pip install --no-cache-dir fastapi uvicorn psycopg2-binary sqlalchemy prometheus-fastapi-instrumentator opentelemetry-api opentelemetry-sdk opentelemetry-instrumentation-fastapi opentelemetry-exporter-otlp-proto-grpc

# 4. Copiamos nuestro archivo main.py de la compu adentro de la cajita
COPY . .

# 5. Indicamos el comando para encender la aplicación cuando la cajita cobre vida
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]