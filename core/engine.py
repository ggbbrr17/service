from core.brain import planner, ask_model, ask_external_model
from core.parser import safe_parse, normalize_steps
from core.executor import plan_to_concrete_steps, execute_step
from core.memory import load_memory, save_memory
from datetime import datetime
import re
import json
import os
import threading
import sys
import time

# Bloqueo para evitar corrupción de memoria al escribir desde hilos
memory_lock = threading.Lock()

def get_relevant_memories(question: str, memories: list, limit: int = 15) -> str:
    """
    Filtra las memorias más relevantes para la pregunta actual.
    Esto permite tener 'memoria ilimitada' seleccionando solo lo necesario.
    """
    if not memories:
        return ""
    
    # Extraer palabras clave de la pregunta (ignorando palabras cortas)
    keywords = [w.lower() for w in question.split() if len(w) > 3]
    if not keywords:
        return "\n".join([f"- {r}" for r in memories[-limit:]])

    # Puntuar memorias según coincidencia de palabras clave
    scored_memories = []
    for m in memories:
        score = sum(1 for k in keywords if k in m.lower())
        scored_memories.append((score, m))
    
    # Ordenar por relevancia y tomar las mejores
    scored_memories.sort(key=lambda x: x[0], reverse=True)
    top_memories = [m for score, m in scored_memories[:limit]]
    return "\n".join([f"- {r}" for r in top_memories])

def _handle_background_tasks(question, active_model, plan, plan_text):
    """Procesa el aprendizaje y la observación sin bloquear la respuesta al usuario."""
    with memory_lock:
        # Recargamos memoria dentro del lock para garantizar frescura absoluta
        mem = load_memory()
        
        # ---------------- LEARNING ----------------
        aprendizaje = plan.get('learn')
        if aprendizaje:
            if "reglas_aprendidas" not in mem:
                mem["reglas_aprendidas"] = []

            mem["reglas_aprendidas"].append(
                f"[{datetime.now().strftime('%d/%m %H:%M')}] {aprendizaje}"
            )
            # Guardamos el rasgo en el string de personalidad de la memoria
            current_p = mem.get("personality_string", "")
            mem["personality_string"] = current_p + f"\n- Rasgo adquirido: {aprendizaje}"
            
            save_memory(mem)
            print(f"🧠 [Async] Glyph aprendió y persistió: {aprendizaje}")

def run(
    question: str, dry_run: bool = False, history: str = "", depth: int = 0, 
    temperature: float = 0.0, is_user: bool = False,
    image: str = None, video: str = None, audio: str = None) -> dict:
    # ---------------- MEMORY ----------------
    mem = load_memory()
    
    # Registrar interacción si viene del usuario
    if is_user:
        with memory_lock:
            mem["last_interaction_at"] = time.time()
            save_memory(mem)
    
    # El contexto ahora solo incluye la base de datos, eliminando la memoria semántica y la auto-introspección.
    context = f"BASE DE DATOS:\n{json.dumps(mem.get('datos', {}))}"
    
    # ÚNICO MODELO: Forzamos gemma4 ignorando cualquier otra configuración
    active_model = mem.get("active_model", "gemma4")

    # ---------------- PRE-PARSE (Vía Rápida para comandos) ----------------
    # Si es un comando de sistema, evitamos llamar a la IA para ahorrar tiempo
    plan = safe_parse("", question)
    plan_text = ""
    tokens = 0
    
    # Solo llamamos al modelo si el parser no devolvió una respuesta clara o pasos
    if plan and (plan.get("message") or plan.get("steps")):
        plan_text = "SYSTEM_COMMAND"
        print(f"\n[DEBUG] Comando de sistema detectado: {question}")
    else:
        # ---------------- MODEL SELECTION ----------------
        # Usamos Gemma 4 (31B) como solicitó el usuario
        target = os.getenv("GLYPH_GEMINI_MODEL", "gemma-4-31b")
        api_key = os.getenv("GLYPH_GEMINI_API_KEY")
        api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{target}:generateContent"

        if not api_key:
            print(f"❌ ERROR CRÍTICO: Falta GLYPH_GEMINI_API_KEY.")
            plan_text = "ERROR_CONNECTION: config_missing (GLYPH_GEMINI_API_KEY)"
        else:
            print(f"🚀 Generando respuesta con {target} (Google API)...")
            ext_res = ask_external_model(
                question, history, context, model_name=target, 
                api_key=api_key, api_url=api_url, temperature=0.7,
                image=image, video=video, audio=audio,
                use_google_search=False
            )
            plan_text = ext_res.get("text", "")
            tokens = ext_res.get("tokens", 0)
        
        # ---------------- PARSE ----------------
        # Parseamos el resultado del modelo único
        plan = safe_parse(plan_text, question) or {}

    # Validar errores solo si no es un comando del sistema (como 'glyph' o 'salir')
    if not plan.get("steps"):
        if not plan_text or plan_text.strip() == "":
            return {
                "error": "empty_response",
                "message": "El modelo no devolvió respuesta"
            }

        if "ERROR_CONNECTION" in plan_text:
            return {
                "error": "connection",
                "message": f"El modelo no pudo responder. Detalles: {plan_text}. "
                           "Asegúrate de haber configurado la variable GLYPH_GEMINI_API_KEY en el panel de Render."
            }

    print("\n[DEBUG] PLAN PARSED:\n", plan)

    # ---------------- ASYNC PROCESSING ----------------
    # Lanzamos el aprendizaje en segundo plano para no demorar la respuesta
    threading.Thread(
        target=_handle_background_tasks, 
        args=(question, active_model, plan, plan_text),
        daemon=True
    ).start()

    # ---------------- STEPS ----------------

    steps = normalize_steps(plan.get('steps', []), question=question)
    concrete = plan_to_concrete_steps(steps)

    print("\n[DEBUG] STEPS NORMALIZED:\n", steps)
    print("\n[DEBUG] STEPS CONCRETE:\n", concrete)

    # ---------------- EXECUTION ----------------
    results = []
    for s in concrete:
        if s.get('action') == 'close_agent' and not dry_run:
            print("🛑 [SISTEMA] Comando de cierre detectado. El proceso terminará en 2 segundos...", flush=True)
            threading.Timer(2.0, lambda: os._exit(0)).start()
            results.append({'action': 'close_agent', 'ok': True, 'msg': 'Apagado programado'})
            continue

        if s.get('action') == 'restart_agent' and not dry_run:
            print("🔄 [SISTEMA] Comando de reinicio detectado. Reiniciando en 2 segundos...", flush=True)
            # Programamos el reinicio: reemplaza el proceso actual con una copia nueva de sí mismo
            threading.Timer(2.0, lambda: os.execv(sys.executable, [sys.executable] + sys.argv)).start()
            results.append({'action': 'restart_agent', 'ok': True, 'msg': 'Reinicio programado'})
            continue

        ok, msg = execute_step(s, dry_run=dry_run)
        
        results.append({
            'action': s.get('action'),
            'ok': ok,
            'msg': msg
        })

    # ---------------- MESSAGE ----------------
    message = plan.get('message')

    # Procesar resultados e inyectar datos de investigación si existen
    for r in results:
        if r.get('action') == 'background_research' and r.get('ok'):
            # Inyectamos el resultado de Tavily directamente para evitar alucinaciones del modelo
            res_info = r.get('msg', '')
            if "🔍" in res_info: # Si es un resultado válido de investigación
                prefix = "Aquí tienes la información actualizada:\n\n" if history else "Hola, Gabriel. Aquí tienes lo que encontré:\n\n"
                message = f"{prefix}{res_info}"
        elif not r.get('ok'):
            print(f"⚠️ Error en acción: {r.get('msg')}")

    # Si alcanzamos el límite de profundidad y no hay pasos o hay errores persistentes
    if depth >= 2:
        if not steps or any(not r.get('ok') for r in results):
            message = "Lo siento, Gabriel, me he quedado bloqueado en un bucle de pensamiento sin poder ejecutar acciones reales. He abortado la tarea para evitar errores mayores."

    if not message:
        # Si la IA no genera un mensaje, el motor ya no inyecta frases prehechas.
        # Se usa el plan raw o se deja que Glyph decida su respuesta final en el siguiente ciclo.
        # Limpiamos posibles tags de pensamiento para que el usuario vea la respuesta limpia.
        message = re.sub(r'<(thought|thinking)>.*?</\1>', '', plan_text, flags=re.DOTALL | re.IGNORECASE).strip() if plan_text else "Procesamiento completado sin mensaje de salida."

    # ---------------- RESPONSE ----------------
    return {
        "question": question,
        "metacognition": plan.get("metacognition", ""),
        "message": message,
        "steps": steps,
        "results": results,
        "learn": plan.get('learn'),
        "suggestions": plan.get('suggestions'),
        "active_model": active_model # Ahora devolverá el modelo nuevo
    }