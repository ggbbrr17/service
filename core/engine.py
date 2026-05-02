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
    # Recargamos memoria fresca para evitar sobreescribir cambios hechos por el hilo principal
    mem = load_memory()
    
    # ---------------- LEARNING ----------------
    aprendizaje = plan.get('learn')
    if aprendizaje:
        if "reglas_aprendidas" not in mem:
            mem["reglas_aprendidas"] = []

        with memory_lock:
            mem["reglas_aprendidas"].append(
                f"[{datetime.now().strftime('%d/%m %H:%M')}] {aprendizaje}"
            )
            # Guardamos el rasgo en el string de personalidad de la memoria
            current_p = mem.get("personality_string", "")
            mem["personality_string"] = current_p + f"\n- Rasgo adquirido: {aprendizaje}"
            
            save_memory(mem)
        print(f"🧠 [Async] Glyph aprendió: {aprendizaje}")

def run(question: str, dry_run: bool = False, history: str = "", depth: int = 0, temperature: float = 0.0, is_user: bool = False) -> dict:
    # ---------------- MEMORY ----------------
    mem = load_memory()
    
    # Registrar interacción si viene del usuario
    if is_user:
        with memory_lock:
            mem["last_interaction_at"] = time.time()
            save_memory(mem)
    
    # --- SISTEMA DE GESTIÓN DE CUOTAS (CIRCUIT BREAKER) ---
    today = datetime.now().strftime("%Y-%m-%d")
    if mem.get("disabled_date") != today:
        with memory_lock:
            mem["disabled_models"] = {}
            mem["disabled_date"] = today
            save_memory(mem)
            
    disabled_models = mem.get("disabled_models", {})
    
    # Recuperamos memorias relevantes de forma inteligente
    reglas_totales = mem.get('reglas_aprendidas', [])
    evolucion_relevante = get_relevant_memories(question, reglas_totales)
    
    # Cargar historial de introspección para que Glyph sepa qué ha estado haciendo solo
    intro_hist = mem.get("introspection_history", [])
    intro_context = "\n".join([f"- {h['timestamp']}: {h['tarea']} | Éxitos: {h['exitos']} | Fallos: {h['fallos']} | Aprendido: {h['aprendizaje']}" for h in intro_hist])

    # Mapa de arquitectura de código
    code_map = mem.get("codebase_summary", "No indexado.")

    context = f"ESTRUCTURA DE MI NÚCLEO (Código):\n{code_map}\n\nSISTEMA DE EVOLUCIÓN (Aprendizajes):\n{evolucion_relevante}\n\nHISTORIAL DE INTROSPECCIÓN (Actividad autónoma):\n{intro_context}\n\nBASE DE DATOS:\n{json.dumps(mem.get('datos', {}))}"
    
    # PRIORIDAD GEMMA 4: Si no se ha pedido explícitamente otro, forzamos gemma4
    active_model = mem.get("active_model", "gemma4")

    # ---------------- PRE-PARSE (Vía Rápida para comandos) ----------------
    # Si es un comando de sistema, evitamos llamar a la IA para ahorrar tiempo
    plan = safe_parse("", question)
    tokens = 0
    
    if plan:
        plan_text = "SYSTEM_COMMAND"
        print(f"\n[DEBUG] Comando de sistema detectado: {question}")
    else:
        # ---------------- MODEL SELECTION ----------------
        model_res = {"text": "", "tokens": 0}
        target = None
        plan_text = ""
        
        # Modelos Cloud autorizados (Gemini 1.5 eliminado, Gemma 4 prioritario)
        cloud_models = ["llama3", "deepseek", "openrouter", "gemma", "gemma4", "sambanova", "cerebras", "minimax-m2.7:cloud"]

        if active_model in cloud_models:
            # Mapeo de IDs de modelos externos (priorizando variables de entorno)
            if active_model == "llama3":
                target = os.getenv("GLYPH_EXTERNAL_MODEL", "llama-3.3-70b-versatile")
            elif active_model == "deepseek":
                target = os.getenv("GLYPH_DEEPSEEK_MODEL", "deepseek-chat")
            elif active_model == "openrouter":
                # Usamos el modelo universal gratuito de OpenRouter por defecto
                target = os.getenv("GLYPH_OPENROUTER_MODEL", "openrouter/free")
            elif active_model == "sambanova":
                target = os.getenv("GLYPH_SAMBANOVA_MODEL", "Meta-Llama-3.3-70B-Instruct")
            elif active_model == "cerebras":
                target = os.getenv("GLYPH_CEREBRAS_MODEL", "llama3.1-70b")
            elif active_model == "gemma":
                target = os.getenv("GLYPH_GEMMA_MODEL", "google/gemma-2-9b-it:free")
            elif active_model == "gemma4":
                target = os.getenv("GLYPH_GEMMA4_MODEL", "gemma-4-26b-a4b-it")
            else:
                target = active_model
            
            # Verificar si el modelo principal está deshabilitado por cuota
            if target in disabled_models:
                print(f"🚫 El modelo '{active_model}' está en enfriamiento hasta mañana. Activando fallback...")
                plan_text = "ERROR_CONNECTION: 429"
                target = None # Forzar entrada al fallback_chain
                
            # Selección dinámica de credenciales según el modelo solicitado
            if active_model in ["openrouter", "gemma"]:
                env_var_name = "GLYPH_OPENROUTER_API_KEY"
                api_key = os.getenv(env_var_name)
                api_url = "https://openrouter.ai/api/v1/chat/completions"
            elif active_model == "sambanova":
                env_var_name = "GLYPH_SAMBANOVA_API_KEY"
                api_key = os.getenv(env_var_name)
                api_url = "https://api.sambanova.ai/v1/chat/completions"
            elif active_model == "cerebras":
                env_var_name = "GLYPH_CEREBRAS_API_KEY"
                api_key = os.getenv(env_var_name)
                api_url = "https://api.cerebras.ai/v1/chat/completions"
            elif active_model == "deepseek":
                env_var_name = "GLYPH_DEEPSEEK_API_KEY"
                api_key = os.getenv(env_var_name)
                api_url = "https://api.deepseek.com/chat/completions"
            elif active_model == "gemma4":
                env_var_name = "GLYPH_GEMINI_API_KEY"
                api_key = os.getenv(env_var_name)
                api_url = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
            else:
                # Groq y otros
                env_var_name = "GLYPH_EXTERNAL_API_KEY"
                api_key = os.getenv(env_var_name)
                api_url = os.getenv("GLYPH_EXTERNAL_API_URL")

            # Validación de API Key
            if not api_key:
                print(f"❌ ERROR CRÍTICO: Falta la variable '{env_var_name}' en el servidor para usar Gemma 4.")
                plan_text = f"ERROR_CONNECTION: config_missing ({env_var_name})"
            else:
                print(f"🚀 Conexión directa con {target} ({active_model.upper()} Mode)...")
                
                # Si es OpenRouter, implementamos rotación interna de modelos
                if active_model == "openrouter":
                    router_fallback = [
                        target, 
                        "google/gemini-2.0-flash-exp:free",
                        "google/gemini-flash-1.5:free",
                        "meta-llama/llama-3-8b-instruct:free"
                    ]
                    for r_model in router_fallback:
                        print(f"📡 Probando modelo en OpenRouter: {r_model}...")
                        ext_res = ask_external_model(question, history, context, model_name=r_model, api_key=api_key, api_url=api_url, temperature=temperature)
                        plan_text = ext_res.get("text", "")
                        tokens = ext_res.get("tokens", 0)
                        if plan_text and "ERROR_CONNECTION" not in plan_text and "404" not in plan_text:
                            target = r_model
                            break
                elif target:
                    ext_res = ask_external_model(question, history, context, model_name=target, api_key=api_key, api_url=api_url, temperature=temperature)
                    plan_text = ext_res.get("text", "")
                    tokens = ext_res.get("tokens", 0)
                    if "429" in plan_text:
                        disabled_models[target] = True
                    # PERSISTENCIA: Si el modelo principal falla, migramos permanentemente a Gemma 4
                    with memory_lock:
                        mem["active_model"] = "gemma4"
                        save_memory(mem)
                        active_model = "gemma4"

        else:
            # Intento normal con Ollama (Local/Túnel)
            model_res = planner(question, history, context, model=active_model, temperature=temperature)
            plan_text = model_res.get("text", "")
            tokens = model_res.get("tokens", 0)

        # ---------------- FALLBACK CASCADING (SUPERVIVENCIA) ----------------
        # Si el modelo activo falla, saltamos automáticamente por la jerarquía de proveedores
        # MODIFICACIÓN: Si el modelo es gemma4, NO intentamos usar otros modelos para respetar tu preferencia.
        if (not plan_text or "ERROR_CONNECTION" in plan_text or "404" in plan_text or "429" in plan_text) and active_model not in ["tinyllama", "gemma4"]:
            print(f"⚠️ El modelo '{active_model}' ha fallado. Iniciando rotación hacia otros modelos...")
            
            # Cadena de supervivencia actualizada
            deepseek_key = os.getenv("GLYPH_DEEPSEEK_API_KEY")
            gemini_key = os.getenv("GLYPH_GEMINI_API_KEY")
            fallback_chain = [
                {"slug": "gemma4", "name": "Gemma 4 (Google Next Gen)", "model": os.getenv("GLYPH_GEMMA4_MODEL", "gemma-4-26b-a4b-it"), "key": gemini_key, "url": "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"},
                {"slug": "llama3", "name": "Groq Llama 3.3 (Estable)", "model": "llama-3.3-70b-versatile", "key": os.getenv("GLYPH_EXTERNAL_API_KEY"), "url": os.getenv("GLYPH_EXTERNAL_API_URL")},
                {"slug": "deepseek", "name": "DeepSeek (Nativo)", "model": "deepseek-chat", "key": deepseek_key, "url": "https://api.deepseek.com/chat/completions"},
            ]

            for entry in fallback_chain:
                # Saltamos si no hay API Key, si es el que falló o si está deshabilitado hasta mañana
                if not entry["key"] or entry["model"] == target or entry["model"] in disabled_models:
                    continue
                
                print(f"🔄 Intentando con {entry['name']} ({entry['model']})...")
                ext_res = ask_external_model(question, history, context, model_name=entry["model"], api_key=entry["key"], api_url=entry["url"], temperature=temperature)
                plan_text = ext_res.get("text", "")
                tokens = ext_res.get("tokens", 0)
                
                if plan_text and "ERROR_CONNECTION" not in plan_text:
                    if "429" in plan_text:
                        print(f"🚫 {entry['name']} agotado. Deshabilitando temporalmente.")
                        disabled_models[entry["model"]] = True
                        continue
                    print(f"✨ Conexión recuperada con {entry['name']}.")
                    # PERSISTENCIA: Guardamos el modelo recuperado para que sea el nuevo 'active_model'
                    with memory_lock:
                        mem["active_model"] = entry["slug"]
                        save_memory(mem)
                        active_model = entry["slug"]
                    break
            
            # Guardar el estado de los modelos deshabilitados
            mem["disabled_models"] = disabled_models
            save_memory(mem)

            # Última instancia: TinyLlama Local
            if not plan_text or "ERROR_CONNECTION" in plan_text:
                print(f"⚠️ Usando TinyLlama local como último recurso...")
                model_res = planner(question, history, context, model="tinyllama", temperature=temperature)
                plan_text = model_res.get("text", "")
                tokens = model_res.get("tokens", 0)

            print("\n[DEBUG] PLAN RAW (Fallback):\n", plan_text)

        # ---------------- PARSE ----------------
        # Parseamos el resultado del modelo (o del fallback)
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
                "message": f"Gemma 4 no pudo responder. Detalles: {plan_text}. "
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
        
        # Si el paso cambió el modelo, actualizamos la variable local para la respuesta
        if s.get('action') == 'switch_model' and ok:
            active_model = s.get('model', active_model)

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
            message = f"Hola, Gabriel. Aquí tienes la información actualizada:\n\n{res_info}"
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