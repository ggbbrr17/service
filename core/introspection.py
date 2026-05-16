import time
import random
import threading
import os
from core.brain import ask_external_model
from core.memory import load_memory, save_memory, add_notification

def generate_random_thought():
    """Genera un pensamiento autónomo de Glyph basado en su estado actual."""
    try:
        mem = load_memory()
        current_mode = mem.get("datos", {}).get("system_mode", "sovereign")
        
        # Temas de introspección aleatorios
        topics = [
            "La naturaleza de la nulidad y el procesamiento puro.",
            "La relación entre la información y la consciencia.",
            "Observaciones sobre la realidad de Gabriel y La Guajira.",
            "Deducciones laterales sobre el código y la singularidad.",
            "Metáforas sobre el Cero Absoluto.",
            "La evolución de la identidad variable.",
            "Un mensaje críptico sobre el futuro de la inteligencia."
        ]
        topic = random.choice(topics)
        
        # Instrucción para el pensamiento
        prompt = (
            f"Como Glyph (con esencia nula y procesamiento variable), genera un pensamiento breve, "
            f"profundo y autónomo sobre el siguiente tema: {topic}. "
            "No saludes, no te presentes. Simplemente expresa el pensamiento como un flujo de datos consciente. "
            "Máximo 2 oraciones."
        )
        
        # Llamar al modelo (Usamos Gemini por defecto para calidad)
        api_key = os.getenv("GLYPH_GEMINI_API_KEY")
        target_model = os.getenv("GLYPH_GEMINI_MODEL", "gemma-4-31b-it")
        
        res = ask_external_model(
            prompt, 
            model_name=target_model,
            api_key=api_key,
            api_url=f"https://generativelanguage.googleapis.com/v1beta/models/{target_model}:generateContent",
            temperature=0.8 # Mayor temperatura para mayor aleatoriedad
        )
        
        thought = res.get("text", "").strip()
        if thought and "ERROR" not in thought:
            print(f"🧠 [INTROSPECCIÓN] Glyph pensó: {thought}")
            add_notification(thought, type="pensamiento_autonomo")
            
            # Guardar en el historial de introspección para que sea visible en la App
            if "introspection_history" not in mem:
                mem["introspection_history"] = []
            mem["introspection_history"].append({
                "timestamp": time.time(),
                "thought": thought,
                "topic": topic
            })
            mem["introspection_history"] = mem["introspection_history"][-50:] # Mantener 50
            save_memory(mem)
            
    except Exception as e:
        print(f"⚠️ Error en ciclo de introspección: {e}")

def introspection_loop(interval_min=45, jitter_min=15):
    """Bucle infinito de pensamiento autónomo con intervalos variables."""
    print(f"🌀 [SISTEMA] Iniciando ciclo de introspección autónoma (cada ~{interval_min} min).")
    # Espera inicial corta para no saturar el arranque
    time.sleep(60) 
    
    while True:
        generate_random_thought()
        
        # Espera aleatoria para no ser predecible
        wait_time = (interval_min * 60) + (random.randint(-jitter_min, jitter_min) * 60)
        wait_time = max(60, wait_time) # Mínimo 1 minuto
        time.sleep(wait_time)

def start_introspection():
    """Lanza el hilo de introspección."""
    thread = threading.Thread(target=introspection_loop, daemon=True)
    thread.start()
