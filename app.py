import os
import sys

# Configuración de API Keys críticas
os.environ["TAVILY_API_KEY"] = "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"

# Asegurar que Python encuentre los módulos en la raíz
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Forzar salida sin buffer para ver logs en tiempo real en la nube
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

from interfaces.server import app as flask_app
from core.heartbeat import heartbeat_loop
from threading import Thread
import time
import requests

def keep_alive_loop():
    """Mantiene el servicio despierto realizando pings a su propia URL."""
    # Render proporciona la URL externa en esta variable de entorno
    url = os.getenv("RENDER_EXTERNAL_URL")
    if not url:
        print("⚠️ RENDER_EXTERNAL_URL no configurada. El auto-ping está desactivado.")
        return

    print(f"💓 Iniciando ciclo de auto-ping para: {url}")
    while True:
        try:
            r = requests.get(url, timeout=10)
            print(f"💓 Self-ping exitoso: {r.status_code}")
        except Exception as e:
            print(f"⚠️ Fallo en self-ping: {e}")
        
        # Esperar 10 minutos (600 segundos)
        time.sleep(600)

if __name__ == "__main__":
    print("🏗️ Configurando entorno para RENDER (Modo App Web)...", flush=True)

    print("🚀 --- INICIANDO NÚCLEO GLYPH 24/7 ---", flush=True)
    
    print("💓 Iniciando sistema de latido (Heartbeat)...", flush=True)
    Thread(target=heartbeat_loop, daemon=True).start()

    print("📡 Activando sistema de auto-mantenimiento...", flush=True)
    Thread(target=keep_alive_loop, daemon=True).start()

    # Iniciar el servidor Flask como proceso principal
    port = int(os.getenv("PORT", 5000))
    flask_app.run(host="0.0.0.0", port=port)
