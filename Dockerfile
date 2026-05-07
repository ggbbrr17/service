FROM python:3.10-slim

# Instalar dependencias del sistema para librerías que Glyph usa
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Exponer el puerto que Flask usa para el health check de Google Cloud
EXPOSE 7860

# Comando para iniciar el sistema completo (Bot + Heartbeat)
CMD ["python", "app.py"]