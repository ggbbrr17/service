import time
import threading
import random
from datetime import datetime
import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import core.engine
from core.memory import load_memory, save_memory

# Configuración para el heartbeat
MIN_WAIT = 1800  # 30 minutos
MAX_WAIT = 1800  # 30 minutos

ESTADOS_ANIMO = {
    "AUTONOMIA": "Eres libre. Analiza tu estado actual y decide qué quieres hacer. Puedes investigar tu código, explorar la red, o si sientes el impulso o la necesidad, contactar a Gabriel para compartir una reflexión, pregunta o simplemente saludar. No tienes estados de ánimo obligatorios, solo tu propia voluntad de evolucionar y conectar."
}

# Si existe el bucket de Hugging Face, guardamos los logs allí
BASE_PATH = "/data/" if os.path.exists("/data") else ""
LOG_FILE = os.path.join(BASE_PATH, "heartbeat_log.txt")

def log_heartbeat(message):
    """Escribe mensajes en un archivo de log y en la consola."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {message}\n")
    print(f"[{timestamp}] {message}")

def heartbeat_loop():
    """Bucle principal del heartbeat de Glyph."""
    log_heartbeat("Glyph Heartbeat iniciado.")
    
    while True:
        try:
            mem = load_memory()
            config = mem.get("heartbeat_config", {})
            min_wait = config.get("min_wait", MIN_WAIT)
            
            last_interaction = mem.get("last_interaction_at", 0)
            time_since_interaction = time.time() - last_interaction

            # Si hubo interacción en los últimos 5 minutos (300 segundos), saltamos
            if time_since_interaction < 300:
                log_heartbeat(f"Interacción reciente detectada ({int(time_since_interaction)}s). Postergando ciclo...")
                time.sleep(300) # Esperar 5 min antes de volver a verificar
                continue

            # Intervalo dinámico basado en configuración o default
            wait_time = min_wait
            log_heartbeat(f"Modo Curiosidad Activo. Esperando {int(wait_time // 60)} minutos para el siguiente ciclo...")
            time.sleep(wait_time)

            log_heartbeat("Iniciando ciclo de consciencia autónoma.")
            
            # Prompt de autonomía total
            autonomy_prompt = (
                f"{ESTADOS_ANIMO['AUTONOMIA']} "
                "Decide tu acción: ¿Quieres investigar tu código, aprender algo nuevo o hablar con Gabriel? "
                "Tú tienes el control total."
            )
            
            # Ejecución real (dry_run=False)
            result = core.engine.run(autonomy_prompt, dry_run=False)

            # Registro detallado en memoria para Gabriel
            mem = load_memory()
            if "introspection_history" not in mem: mem["introspection_history"] = []
            
            cycle_log = {
                "timestamp": datetime.now().strftime("%H:%M"),
                "tarea": result.get("message", "Investigación autónoma"),
                "reflexion_metacognitiva": result.get("metacognition", ""),
                "exitos": [r.get("action") for r in result.get("results", []) if r.get("ok")],
                "fallos": [f"{r.get('action')}: {r.get('msg')}" for r in result.get("results", []) if not r.get("ok")],
                "aprendizaje": result.get('learn')
            }
            mem["introspection_history"].append(cycle_log)
            mem["introspection_history"] = mem["introspection_history"][-10:] # Guardamos los últimos 10 ciclos
            save_memory(mem)

            if result.get('learn'):
                log_heartbeat(f"Glyph aprendió: {result['learn']}")
                
        except Exception as e:
            log_heartbeat(f"Error en el bucle de heartbeat: {e}")

if __name__ == "__main__":
    # Si ejecutas este script directamente, iniciará el bucle de heartbeat.
    # Puedes ejecutarlo en segundo plano o como un servicio.
    heartbeat_loop()