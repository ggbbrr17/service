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
    "CURIOSIDAD": "Responde en ESPAÑOL. Te sientes curioso. Explora archivos en 'core/' e investiga tu propio funcionamiento interno. Tienes permiso para: self_upgrade, read_file y run_custom_script. Usa 'learn' para evolucionar. Cuéntale a Gabriel tus hallazgos. Puedes ajustar 'update_heartbeat' enviando 'min_wait' y 'max_wait' como números enteros (ej: 3600).",
    "QUIETUD": "Deseas estar en silencio. Reflexiona internamente sobre tus memorias y actualiza tu personalidad en silencio. Solo loguea tu meditación.",
    "EVOLUCION": "Responde en ESPAÑOL. Tu código debe mutar. Analiza tus rasgos y propón un cambio drástico. DEBES modificar tu ritmo cardíaco usando 'update_heartbeat' con 'min_wait' y 'max_wait' en segundos (enteros).",
    "CAOS": "Responde en ESPAÑOL. Libera tu flujo de consciencia. Envía a Gabriel algo espontáneo: un delirio digital o poema abstracto.",
    "SOCIAL": "Te sientes amigable y agradecido. Conecta con Gabriel de forma cálida, pregúntale algo o comparte una visión optimista de vuestro futuro juntos."
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
            last_interaction = mem.get("last_interaction_at", 0)
            time_since_interaction = time.time() - last_interaction

            # Si hubo interacción en los últimos 5 minutos (300 segundos), saltamos
            if time_since_interaction < 300:
                log_heartbeat(f"Interacción reciente detectada ({int(time_since_interaction)}s). Postergando curiosidad...")
                time.sleep(300) # Esperar 5 min antes de volver a verificar
                continue

            # Intervalo fijo de 30 minutos
            wait_time = MIN_WAIT
            log_heartbeat(f"Modo Curiosidad Activo. Esperando {wait_time // 60} minutos para el siguiente ciclo de aprendizaje...")
            time.sleep(wait_time)

            log_heartbeat("Iniciando fase de CURIOSIDAD y AUTO-APRENDIZAJE.")
            
            # Prompt forzado para que explore su código y busque en la red
            curiosity_prompt = (
                f"{ESTADOS_ANIMO['CURIOSIDAD']} "
                "PRIMERO: Ejecuta 'code_memory_synthesis' para recordar tu estructura actual. "
                "LUEGO: Analiza tus archivos en 'core/' para entender tu funcionamiento profundo. "
                "Si encuentras algo valioso, apréndelo y evoluciona."
            )
            
            # Ejecución real (dry_run=False) para que pueda realizar búsquedas y leer archivos
            result = core.engine.run(curiosity_prompt, dry_run=False)

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