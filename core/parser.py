import json
import re
import random


def safe_parse(text: str, question: str = "") -> dict:
    # Intercepción directa de comandos de salida
    q_clean = question.lower().strip()

    # 1. SI NO HAY TEXTO DE LA IA (Vía Rápida / Atajos)
    if not text:
        # Comandos críticos de sistema que no necesitan pasar por la IA
        if q_clean in ["salir", "cerrar", "exit", "quit", "terminar"]:
            return {"steps": [{"action": "close_agent"}]}

        if q_clean in ["reiniciar", "restart", "reboot"]:
            return {"steps": [{"action": "restart_agent"}]}

        if q_clean == "comenzar":
            return {
                "message": "Iniciando mi interfaz gráfica y activando sistemas en tu PC. Estoy listo.",
                "steps": [{"action": "launch_gui"}]
            }

    if not text:
        return {}

    print(f"\n[DEBUG] RAW AI RESPONSE:\n{text}\n")

    # 2. Limpieza para el parser JSON
    text = re.sub(r'<(thought|thinking)>.*?</\1>', '', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'^\s*\*.*?\n', '', text, flags=re.MULTILINE)

    data = None
    try:
        # Intentar parsear el JSON tal cual
        data = json.loads(text)
    except:
        # Búsqueda agresiva de bloques JSON { ... } o listas [ ... ]
        json_match = re.search(r'(\{.*\}|\[.*\])', text, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group(1))
            except:
                # Si falla el parseo pero hay llaves, intentamos una reparación básica
                try:
                    repaired = json_match.group(1)
                    # Reemplazar comillas inteligentes y otros caracteres problemáticos
                    repaired = repaired.replace('“', '"').replace('”', '"').replace('‘', "'").replace('’', "'")
                    data = json.loads(repaired)
                except:
                    pass
        
        # SI FALLA TODO: Intentamos extraer campos clave mediante Regex (Para modelos rebeldes como Gemma 4)
        if not data:
            data = {}
            thought_m = re.search(r'["\']?thought["\']?\s*[:=]\s*["\'](.*?)["\'](?:\s*[,}]|\s*$)', text, re.DOTALL | re.IGNORECASE)
            msg_m = re.search(r'["\']?message["\']?\s*[:=]\s*["\'](.*?)["\'](?:\s*[,}]|\s*$)', text, re.DOTALL | re.IGNORECASE)
            steps_m = re.search(r'["\']?steps["\']?\s*[:=]\s*(\[.*?\])', text, re.DOTALL | re.IGNORECASE)
            
            if thought_m: data["thought"] = thought_m.group(1)
            if msg_m: data["message"] = msg_m.group(1)
            if steps_m:
                try:
                    data["steps"] = json.loads(steps_m.group(1).replace("'", '"'))
                except:
                    pass
            
            if not data: # Si ni siquiera con regex encontramos campos, no es un dict válido
                data = None

    # Si el modelo devolvió una lista, tomamos el primer elemento
    if isinstance(data, list) and len(data) > 0:
        data = data[0]

    if isinstance(data, dict):
        # Verificar si la pregunta original tiene tono de comando
        # Ampliamos para incluir consultas de información y cripto
        es_orden = re.search(r"\b(abre|busca|haz|pon|click|escribe|lee|ejecuta|dime|enciende|prende|crea|genera|investiga|analiza|diseña|programa|precio|cu[aá]nto|cu[aá]l|qu[eé]|btc|bitcoin|clima)\b", question.lower())
        
        # Mapeo de sinónimos para evitar corchetes si el modelo cambia las llaves
        msg_raw = (data.get("message") or data.get("respuesta") or 
               data.get("saludo") or data.get("texto") or 
               data.get("response") or data.get("explicacion"))
        
        # Limpiar pensamientos residuales dentro del mensaje (si el modelo los puso dentro del JSON)
        if isinstance(msg_raw, str):
            msg_raw = re.sub(r'<(thought|thinking)>.*?</\1>', '', msg_raw, flags=re.DOTALL | re.IGNORECASE).strip()
        
        steps = data.get("steps", [])

        # Si detectamos pasos pero la pregunta no parecía una orden, los movemos a sugerencias
        if steps and not es_orden and "update_heartbeat" not in str(steps):
            return {"message": str(msg_raw), "steps": []}

        # Capturar si la IA envió el script en la raíz en lugar de en steps
        if not steps and (data.get("script") or data.get("codigo")):
            code = data.get("codigo") or data.get("script")
            if isinstance(code, dict): code = code.get("codigo")
            steps = [{"action": "run_custom_script", "script": code}]
        
        # REPARACIÓN DE EMERGENCIA: Si el mensaje contiene un JSON con un script, extraerlo
        if not steps and isinstance(msg_raw, str) and "{" in msg_raw:
            try:
                inner_data = json.loads(re.search(r'(\{.*\})', msg_raw, re.DOTALL).group(1))
                script_code = inner_data.get("codigo") or inner_data.get("script", {}).get("codigo") or inner_data.get("script") or inner_data.get("comando")
                if script_code and isinstance(script_code, str):
                    steps = [{"action": "run_custom_script", "script": script_code}]
                
                # Si el inner_data tiene un mensaje mejor, lo usamos
                msg_raw = inner_data.get("descripcion") or inner_data.get("explicacion") or msg_raw
            except:
                pass

        return {
            "message": str(msg_raw) if msg_raw else text.strip(),
            "steps": steps
        }

    # fallback
    # Si falla todo, limpiamos posibles restos de JSON del texto para el usuario
    clean_text = re.sub(r'\{.*\}', '', text, flags=re.DOTALL).strip()
    return {
        "message": clean_text if clean_text else text.strip(),
        "steps": []
    }


def normalize_steps(steps, question=""):
    if not isinstance(steps, list):
        return []

    # Acciones que el executor.py realmente sabe manejar
    valid_actions = [
        "write_plugin", "open_browser", "search", "background_research",
        "run_custom_script", "self_upgrade", "type_text", "press", 
        "screenshot", "read_file", "list_processes", "click_at", "hotkey",
        "find_file", "get_latest_download", "run_app", "update_heartbeat",
        "close_agent", "restart_agent", "analyze_dataset", "smart_click", "wait", "read_screen_text",
        "neural_memory_synthesis", "trigger_cmd", "launch_gui", "say", "connect_dependency",
        "list_files", "write_file", "modify_file"
    ]

    normalized = []
    for s in steps:
        if isinstance(s, dict):
            # CORRECCIÓN DE ALUCINACIÓN: Si la IA usó el nombre de la acción como llave principal
            # Ejemplo: {"run_custom_script": "print(1)"} -> {"action": "run_custom_script", "script": "print(1)"}
            if "action" not in s:
                for v_act in valid_actions:
                    if v_act in s:
                        val = s[v_act]
                        s = {"action": v_act}
                        if v_act == "run_custom_script": s["script"] = val
                        elif v_act == "write_file": s["content"] = val
                        elif isinstance(val, dict): s.update(val)
                        else: s["params"] = val
                        break

            if "action" not in s: continue

            # EXTRAER PARÁMETROS SI VIENEN ANIDADOS (Vital para Groq/Llama 3.3)
            # Ahora acepta 'params', 'parameters' o 'argumentos'
            params_key = next((k for k in ["params", "parameters", "argumentos"] if k in s), None)
            if params_key and isinstance(s[params_key], dict):
                for k, v in s[params_key].items():
                    if k not in s: s[k] = v
            
            action = s["action"]
            # Normalización de sinónimos comunes
            if action == "type": s["action"] = "type_text"
            if action == "write": s["action"] = "type_text"
            if action == "abrir": s["action"] = "run_app"
            if action == "foto": s["action"] = "screenshot"
            
            # Si la acción no es válida y no es un sinónimo, la descartamos
            if s["action"] not in valid_actions:
                continue
                
            # Normalización de parámetros para archivos
            if s["action"] in ["read_file", "write_plugin"]:
                if "path" not in s and "file" in s: s["path"] = s["file"]
                if "path" not in s and "filename" in s: s["path"] = s["filename"]
                if "path" not in s and "file_path" in s: s["path"] = s["file_path"]
                if "path" not in s and "path" in s.get("params", {}): s["path"] = s["params"]["path"]

            # Normalización para búsquedas
            if s["action"] == "find_file" and "name" not in s and "filename" in s:
                s["name"] = s["filename"]

            # Normalización para scripts (LLMs a veces usan 'command' o 'code')
            if s["action"] == "run_custom_script":
                if "script" not in s and "command" in s: s["script"] = s["command"]
                if "script" not in s and "code" in s: s["script"] = s["code"]

            # Asegurar parámetros
            if s["action"] == "type_text" and "text" not in s and "query" in s:
                s["text"] = s["query"]
                
            # Reparación para búsquedas sin query
            if s["action"] == "background_research" and "query" not in s:
                s["query"] = question
                
            normalized.append(s)
        elif isinstance(s, str):
            # 1. Soporte para formato tipo función: accion(param='valor') o accion("valor")
            func_match = re.search(r"(\w+)\s*\((.*)\)", s)
            if func_match:
                action_name = func_match.group(1).strip()
                params_content = func_match.group(2).strip()
                
                if action_name in valid_actions:
                    step_obj = {"action": action_name}
                    # Caso especial: background_research("consulta") sin 'query='
                    if action_name == "background_research" and "=" not in params_content:
                        step_obj["query"] = params_content.strip("'\" ")
                    else:
                        # Extraer patrones clave=valor
                        pairs = re.findall(r"(\w+)\s*=\s*['\"]?(.*?)['\"]?(?:,|$)", params_content)
                        for k, v in pairs:
                            step_obj[k] = v.strip()
                    
                    if step_obj.get("action"):
                        normalized.append(step_obj)
                        continue

            # 2. String exacto como acción (Legacy)
            if s in valid_actions:
                normalized.append({"action": s})
            else:
                print(f"⚠️ Ignorando acción inválida (formato incorrecto): {s}")
    return normalized
