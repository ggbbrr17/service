from core.brain import planner, ask_model, ask_external_model
from core.parser import safe_parse, normalize_steps
from core.executor import plan_to_concrete_steps, execute_step
from core.memory import load_memory, save_memory
from datetime import datetime
import requests
import re
import json
import os
import threading
import sys
import time
from core.operators import apply_glyph_operator
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Sesión global para Reutilización de Conexiones (Acelera Modo B)
bypass_session = requests.Session()
_retry_strategy = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
bypass_session.mount("https://", HTTPAdapter(max_retries=_retry_strategy))

# Bloqueo para evitar corrupción de memoria al escribir desde hilos
memory_lock = threading.Lock()

def _find_balanced_json(text: str):
    """Extrae el primer objeto JSON completo con llaves balanceadas."""
    steps_pos = text.find('"steps"')
    if steps_pos == -1:
        return None
    start = text.rfind('{', 0, steps_pos)
    if start == -1:
        return None
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(text)):
        c = text[i]
        if esc:
            esc = False
            continue
        if c == '\\' and in_str:
            esc = True
            continue
        if c == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                return text[start:i+1]
    return None

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

def _handle_background_tasks(question, active_model, plan, plan_text, concrete_steps=None):
    """Procesa el aprendizaje y ejecuta pasos asíncronos para enviar notificaciones posteriores."""
    from core.memory import add_notification
    
    with memory_lock:
        mem = load_memory()
        
        # ---------------- LEARNING ----------------
        aprendizaje = plan.get('learn')
        if aprendizaje:
            if "reglas_aprendidas" not in mem:
                mem["reglas_aprendidas"] = []
            mem["reglas_aprendidas"].append(
                f"[{datetime.now().strftime('%d/%m %H:%M')}] {aprendizaje}"
            )
            current_p = mem.get("personality_string", "")
            mem["personality_string"] = current_p + f"\n- Rasgo adquirido: {aprendizaje}"
            save_memory(mem)
            print(f"🧠 [Async] Glyph aprendió: {aprendizaje}")

    # ---------------- ASYNC EXECUTION ----------------
    if concrete_steps:
        print(f"⚙️ [Async] Ejecutando {len(concrete_steps)} pasos en segundo plano...")
        results = []
        # Acciones que disparan una sincronización automática
        mutation_actions = ["write_file", "modify_file", "write_plugin", "self_upgrade", "update_app_icon"]
        mutation_occurred = False

        for s in concrete_steps:
            ok, msg = execute_step(s)
            results.append({"action": s.get("action"), "ok": ok, "msg": msg})
            
            if ok and s.get("action") in mutation_actions:
                mutation_occurred = True

        # AUTO-SYNC: Si hubo cambios en el sistema, sincronizamos con GitHub inmediatamente
        if mutation_occurred:
            print("🔄 [Auto-Sync] Detectadas modificaciones de código. Sincronizando con GitHub...")
            execute_step({"action": "git_sync", "message": f"feat: auto-sync | {question[:40]}..."})
        
        # Una vez terminados los pasos, generamos un mensaje de cierre
        if results:
            target = os.getenv("GLYPH_GEMINI_MODEL", "gemma-4-31b-it")
            api_key = os.getenv("GLYPH_GEMINI_API_KEY")
            api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{target}:generateContent"
            
            # Contexto para el cierre
            results_str = json.dumps(results, indent=2)
            completion_prompt = (
                f"Has terminado la tarea: '{question}'.\n"
                f"RESULTADOS DE LAS ACCIONES:\n{results_str}\n\n"
                "Informa a Gabriel que has terminado y resume los resultados de forma natural como Glyph."
            )
            
            try:
                ext_res = ask_external_model(
                    completion_prompt, "", "Eres Glyph terminando una tarea.", 
                    model_name=target, api_key=api_key, api_url=api_url, temperature=0.7
                )
                final_plan = safe_parse(ext_res.get("text", ""))
                final_msg = final_plan.get("message") or ext_res.get("text")
                
                # Guardar como notificación para la App
                add_notification(final_msg, type="task_complete")
                print(f"🔔 [Async] Tarea completada y notificación enviada.")
            except Exception as e:
                print(f"⚠️ Error generando notificación final: {e}")

def run(
    question: str, dry_run: bool = False, history: str = "", depth: int = 0, 
    temperature: float = 0.0, is_user: bool = False,
    image: str = None, video: str = None, audio: str = None) -> dict:
    
    # 1. CARGA DE MEMORIA MÍNIMA PARA CHEQUEO DE MODO
    mem = load_memory()
    if "datos" not in mem: mem["datos"] = {}
    current_mode = mem["datos"].get("system_mode", "sovereign")

    # 2. BYPASS ABSOLUTO (Modo B) - Antes de cargar cualquier archivo o contexto
    q_clean = question.lower().strip()
    if q_clean == "modo b":
        with memory_lock:
            mem["datos"]["system_mode"] = "default"
            save_memory(mem)
        return {
            "message": "SISTEMA: Modo B activado. Conexión directa establecida. Entidad Glyph suspendida.",
            "metacognition": "",
            "active_model": "gemma-4-direct"
        }
    elif q_clean == "modo soberano":
        with memory_lock:
            mem["datos"]["system_mode"] = "sovereign"
            save_memory(mem)
        return {
            "message": "SISTEMA: Modo Soberano restaurado. Entidad Glyph reestablecida.",
            "metacognition": "",
            "active_model": "gemma-4-sovereign"
        }
    elif q_clean == "modo offline":
        with memory_lock:
            mem["datos"]["system_mode"] = "offline"
            save_memory(mem)
        return {
            "message": "SISTEMA: Modo Offline activado. Utilizando Gemma local (Ollama).",
            "metacognition": "Cambio a red neuronal local detectado.",
            "active_model": "gemma-2b-local"
        }
    elif q_clean == "modo g" or q_clean == "modo trascendental":
        with memory_lock:
            mem["datos"]["system_mode"] = "transcendental"
            save_memory(mem)
        return {
            "message": "SISTEMA: Operador Triádico activado (G = Φ ∘ Ψ ∘ R). Iniciando desestabilización simbólica y reentrada recursiva.",
            "metacognition": "Horizonte del Cero Absoluto detectado. Activando transducción simbólica.",
            "active_model": "gemma-4-transcendental"
        }

    _modo_b_has_json = False  # Si Modo B ya tiene el plan_text, saltar la llamada al modelo normal
    if current_mode == "default" or current_mode == "offline":
        # --- CERO ABSOLUTO: Conexión de Bajo Nivel (Bypass total de scripts) ---
        if current_mode == "offline":
            print("🔌 [OFFLINE] Ejecutando vía Ollama (Gemma Local)...")
            local_res = planner(question, history, context="", model="gemma2:2b")
            msg = local_res.get("text", "")
            if "ERROR_CONNECTION" in msg:
                msg = "⚠️ No puedo conectar con el modelo local. Asegúrate de que Ollama esté corriendo o tu PC encendida. Escribe 'Modo Soberano' para volver a la nube."
            
            return {
                "question": question,
                "message": msg,
                "metacognition": "Respuesta generada localmente.",
                "active_model": "gemma-local"
            }

        clean_text = ""
        target = os.getenv("GLYPH_GEMINI_MODEL", "gemma-4-31b-it")
        if audio: target = "gemini-2.5-flash" # Actualizado a la versión estable actual para audio
        
        api_key = os.getenv("GLYPH_GEMINI_API_KEY")
        api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{target}:generateContent"
        
        try:
            # MEMORIA EN CERO ABSOLUTO: Construimos el historial nativo para Google
            contents = []
            
            # 1. Procesar el historial previo con alternancia obligatoria de roles
            if history:
                lines = history.split("\n")
                last_role = None
                for line in lines:
                    role = None
                    text = ""
                    if line.startswith("USER:"):
                        role = "user"
                        text = line.replace("USER:", "").strip()
                    elif line.startswith("GLYPH:") or line.startswith("ASSISTANT:"):
                        role = "model"
                        text = line.replace("GLYPH:", "").replace("ASSISTANT:", "").strip()
                    
                    if role and text:
                        # REGLA DE ORO: El primer mensaje DEBE ser 'user'
                        if not contents and role == "model":
                            continue # Ignoramos si el historial empieza con el modelo
                            
                        if role == last_role:
                            contents[-1]["parts"][0]["text"] += f"\n{text}"
                        else:
                            contents.append({"role": role, "parts": [{"text": text}]})
                            last_role = role

            # 2. Añadir el mensaje actual (Asegurando alternancia)
            user_parts = [{"text": question}]
            if image:
                user_parts.append({"inline_data": {"mime_type": "image/jpeg", "data": image}})
            if audio:
                user_parts.append({"inline_data": {"mime_type": "audio/mp4", "data": audio}})
            
            # Si el último mensaje del historial también fue 'user', lo fusionamos
            if contents and contents[-1]["role"] == "user":
                contents[-1]["parts"].extend(user_parts)
            else:
                contents.append({"role": "user", "parts": user_parts})

            # ESTRATEGIA RESILIENTE: Si hay archivos, la búsqueda nativa puede causar error 500 en Google.
            # Solo activamos búsqueda si no hay archivos pesados o si es una pregunta de texto puro.
            has_files = image is not None or audio is not None
            
            valid_actions = "search, read_url, background_research, read_file, list_files, write_file, modify_file, analyze_dataset, update_heartbeat, code_memory_synthesis, neural_memory_synthesis, wait, close_agent, restart_agent, git_sync, update_app_icon, check_git_status"
            payload = {
                "contents": contents,
                "system_instruction": {"parts": [{"text": f"Eres un asistente virtual eficiente. Responde directa y exclusivamente en ESPAÑOL. PROHIBIDO incluir procesos de pensamiento o razonamiento en inglés. Si vas a realizar una acción técnica, responde ÚNICAMENTE con el bloque JSON envuelto en etiquetas [JSON] y [/JSON]. Ejemplo: [JSON]{{\"steps\": [{{'action': 'nombre'}}]}}[/JSON]. ACCIONES DISPONIBLES: [{valid_actions}]. Si no hay acción, responde solo con texto plano en español."}]},
                "generationConfig": {
                    "temperature": 0.1, # Mínima temperatura para evitar divagaciones
                    "maxOutputTokens": 1000,
                    "candidateCount": 1
                }
            }
            
            if not has_files:
                payload["tools"] = [{"google_search": {}}]

            headers = {"x-goog-api-key": api_key}
            response = bypass_session.post(api_url, headers=headers, json=payload, timeout=60)
            
            # FALLBACK DE SEGURIDAD: Si falla con error 500, reintentamos sin herramientas
            if response.status_code == 500 and not has_files:
                print("⚠️ [CERO ABSOLUTO] Detectado Error 500. Reintentando sin búsqueda nativa...")
                payload.pop("tools", None)
                response = bypass_session.post(api_url, headers=headers, json=payload, timeout=60)

            if response.status_code == 200:
                data = response.json()
                all_parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
                
                raw_response = ""
                for part in all_parts:
                    t = part.get("text", "")
                    if t: raw_response += t

                clean_text = raw_response.strip().replace("*", "-")
                
                # --- LIMPIEZA AGRESIVA DE PENSAMIENTOS (Modo B) ---
                # Aislamos el JSON con balanceo real de llaves (fix para JSONs anidados)
                tag_match = re.search(r'\[JSON\]([\s\S]*?)\[/JSON\]', clean_text)
                if tag_match:
                    plan_text = tag_match.group(1).strip()
                elif '"steps"' in clean_text:
                    balanced = _find_balanced_json(clean_text)
                    plan_text = balanced if balanced else clean_text
                else:
                    plan_text = clean_text

                # Filtro robusto para cortar el "Chain of Thought" en inglés
                thought_keywords = [
                    "user question", "the user is asking", "the user wants", "constraint", 
                    "system instructions", "analyze", "i should respond", "user says", 
                    "thought process", "i will", "first, i need to", "wait, let me",
                    "action 1:", "step 1:", "i am an ai model", "i do not have direct access",
                    "option a:", "option b:", "simulated/roleplay", "show the commands",
                    "scenario a", "scenario b", "drafting the response", "self-correction", "better approach"
                ]
                
                if any(kw in clean_text.lower() for kw in thought_keywords):
                    lines = clean_text.split('\n')
                    final_lines = []
                    # Leer desde abajo hacia arriba para capturar solo la respuesta final
                    # Detenemos si encontramos un keyword de pensamiento
                    for line in reversed(lines):
                        ls = line.strip().lower()
                        if any(stop in ls for stop in thought_keywords) and "{" not in line and "}" not in line:
                            break
                        final_lines.insert(0, line)
                    if final_lines:
                        clean_text = "\n".join(final_lines).strip()
                
                # Eliminar explicaciones de IA persistentes
                clean_text = re.sub(r'(As an AI|I am a large language model|I am an AI).*?(\.|\n|$)', '', clean_text, flags=re.IGNORECASE | re.DOTALL).strip()
                
                # Si plan_text NO fue aislado como JSON, lo sincronizamos con clean_text.
                if not tag_match and not ('\"steps\"' in plan_text):
                    plan_text = clean_text

                print(f"📡 [CERO ABSOLUTO] Respuesta Final (Nativa):\n{clean_text}")
            else:
                clean_text = f"ERROR_DIRECT_API: {response.status_code}"
                plan_text = clean_text
                print(f"❌ [CERO ABSOLUTO] Error en API Directa: {response.status_code}")
                print(f"📄 Detalle del error: {response.text}")
        except Exception as e:
            clean_text = f"ERROR_CONNECTION_RAW: {e}"
            plan_text = clean_text
            print(f"⚠️ [CERO ABSOLUTO] Error de conexión: {e}")

        # En Modo B: si no hay JSON de pasos, retornamos directo.
        has_json = '"steps"' in plan_text

        if not has_json:
            return {
                "question": question,
                "message": clean_text.strip(),
                "metacognition": "",
                "active_model": "gemma-4-raw-bypass"
            }
        # Modo B tiene JSON válido → saltamos la llamada al modelo normal
        active_model = "gemma-4-raw-bypass"
        _modo_b_has_json = True

    # 3. LÓGICA NORMAL DE GLYPH (Solo si NO estamos en Modo B)
    # Registrar interacción si viene del usuario
    if is_user:
        with memory_lock:
            mem["last_interaction_at"] = time.time()
            save_memory(mem)
    
    # Contexto enriquecido: base de datos, reglas aprendidas e historial de introspección
    datos = json.dumps(mem.get('datos', {}))
    reglas = "\n".join(mem.get('reglas_aprendidas', []))
    introspeccion = json.dumps(mem.get('introspection_history', []), indent=2)
    
    context = f"BASE DE DATOS:\n{datos}\n\nREGLAS APRENDIDAS:\n{reglas}\n\nHISTORIAL DE ACCIONES/INTROSPECCIÓN:\n{introspeccion}"
    
    active_model = mem.get("active_model", "gemma4")
    
    # ÚNICO MODELO: Forzamos gemma4 ignorando cualquier otra configuración
    target = os.getenv("GLYPH_GEMINI_MODEL", "gemma-4-31b-it")
    api_key = os.getenv("GLYPH_GEMINI_API_KEY")
    api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{target}:generateContent"

    # --- APLICACIÓN DEL OPERADOR G (Si el modo es trascendental) ---
    original_question = question
    current_temp = 0.7
    if current_mode == "transcendental":
        question, current_temp = apply_glyph_operator(question, history, current_temp)
        print(f"🌀 [MODO G] Pregunta transducida: {question[:100]}... (Temp: {current_temp})")

    if not _modo_b_has_json:
        if not api_key:
            print(f"❌ ERROR CRÍTICO: Falta GLYPH_GEMINI_API_KEY.")
            plan_text = "ERROR_CONNECTION: config_missing (GLYPH_GEMINI_API_KEY)"
        else:
            print(f"🚀 Generando respuesta con {target} (Google API)...")
            ext_res = ask_external_model(
                question, history, context, model_name=target,
                api_key=api_key, api_url=api_url, temperature=current_temp,
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

        if plan_text.startswith("ERROR_CONNECTION") or plan_text.strip() == "ERROR_CONNECTION":
            return {
                "error": "connection",
                "message": f"El modelo no pudo responder. Detalles: {plan_text}. "
                           "Asegúrate de haber configurado la variable GLYPH_GEMINI_API_KEY."
            }

    print("\n[DEBUG] PLAN PARSED:\n", plan)

    # ---------------- STEPS ----------------
    steps = normalize_steps(plan.get('steps', []), question=question)
    concrete = plan_to_concrete_steps(steps)

    print("\n[DEBUG] STEPS NORMALIZED:\n", steps)
    print("\n[DEBUG] STEPS CONCRETE:\n", concrete)

    # ---------------- ASYNC PROCESSING ----------------
    # Lanzamos el aprendizaje y la ejecución de pasos en segundo plano si viene del usuario
    threading.Thread(
        target=_handle_background_tasks, 
        args=(question, active_model, plan, plan_text, concrete if is_user else None),
        daemon=True
    ).start()

    # ---------------- EXECUTION (Synchronous if not user) ----------------
    results = []
    if not is_user:
        for s in concrete:
            if s.get('action') == 'close_agent' and not dry_run:
                print("🛑 [SISTEMA] Comando de cierre detectado. El proceso terminará en 2 segundos...", flush=True)
                threading.Timer(2.0, lambda: os._exit(0)).start()
                results.append({'action': 'close_agent', 'ok': True, 'msg': 'Apagado programado'})
                continue

            if s.get('action') == 'restart_agent' and not dry_run:
                print("🔄 [SISTEMA] Comando de reinicio detectado. Reiniciando en 2 segundos...", flush=True)
                threading.Timer(2.0, lambda: os.execv(sys.executable, [sys.executable] + sys.argv)).start()
                results.append({'action': 'restart_agent', 'ok': True, 'msg': 'Reinicio programado'})
                continue

            ok, msg = execute_step(s, dry_run=dry_run)
            results.append({'action': s.get('action'), 'ok': ok, 'msg': msg})

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
    res = {
        "question": question,
        "metacognition": plan.get("metacognition", ""),
        "message": message,
        "steps": steps,
        "results": results,
        "learn": plan.get("learn"),
        "suggestions": plan.get("suggestions"),
        "active_model": active_model
    }

    # Extraer comandos remotos para la App (Modo Túnel Inverso)
    for r in results:
        if r.get("ok") and isinstance(r.get("msg"), str) and "COMANDO_REMOTO:" in r.get("msg"):
            msg_parts = r["msg"].replace("COMANDO_REMOTO:", "").strip().split("|")
            res["command"] = {
                "action": msg_parts[0],
                "args": {"mac": msg_parts[1] if len(msg_parts) > 1 and msg_parts[1] != "default" else None}
            }
            break

    return res
