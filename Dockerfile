FROM python:3.11-slim

# Instalar dependencias del sistema necesarias para psutil y librerías de interfaz
RUN apt-get update && apt-get install -y \
    build-essential \
    ca-certificates \
    python3-tk \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Puerto requerido por Hugging Face
EXPOSE 7860

CMD ["python", "app.py"]