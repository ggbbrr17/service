import os
import sys

# Asegurar que Python encuentre los módulos en la raíz
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Forzar salida sin buffer para ver logs en tiempo real en la nube
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

from interfaces.telegram_bot import bot_loop, USING_WEBHOOK, start_health_check
from core.heartbeat import heartbeat_loop
from threading import Thread
import time

if __name__ == "__main__":
    print("🏗️ Configurando entorno...", flush=True)

    # 0. Iniciar servidor de salud para Hugging Face (Puerto 7860)
    start_health_check()

    print("🚀 --- INICIANDO SISTEMA GLYPH (CLOUD MODE) ---", flush=True)
    
    # 2. Si el Webhook falló, arrancar el bucle de Polling
    print("💓 Iniciando sistema de latido (Heartbeat)...", flush=True)
    Thread(target=heartbeat_loop, daemon=True).start()

    if not USING_WEBHOOK:
        bot_loop()
    else:
        # Si el Webhook funciona, mantenemos el proceso vivo
        while True:
            time.sleep(3600)