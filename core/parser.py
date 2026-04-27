import json
import re
import random


def safe_parse(text: str, question: str = "") -> dict:
    # Intercepción directa de comandos de salida
    q_clean = question.lower().strip()

    # 1. SI NO HAY TEXTO DE LA IA (Vía Rápida / Atajos)
    if not text:
        # Eliminamos respuestas automáticas para saludos y comandos comunes.
        # Ahora todas las interacciones pasan por el modelo para que responda "lo que él quiera".
        if q_clean in ["hola", "hola como estas", "hey", "buenas", "dale", "ok", "adelante"] or q_clean.startswith("["):
            return None

        # Vía rápida para reporte de aprendizaje
        if re.search(r"(qu[eé])\s+(has|hayas)\s+(aprendido|hecho|intentado)\b", q_clean):
            return {
                "steps": [{"action": "say", "message": "Resume detalladamente tus últimos ciclos de introspección basándote en el HISTORIAL DE INTROSPECCIÓN del contexto. Menciona qué archivos exploraste, qué funcionó y qué errores técnicos enfrentaste."}]
            }

        # Vía rápida para metacognición
        if re.search(r"(qu[eé])\s+(piensas|opinas)\s+(de\s+ti|de\s+tu\s+proceso|de\s+tu\s+l[oó]gica)\b", q_clean):
            return {
                "steps": [{"action": "say", "message": "Analiza tu campo 'metacognition' reciente y explícale a Gabriel cómo estás monitoreando tu propio aprendizaje y qué ajustes estás haciendo en tu forma de razonar."}]
            }

        if q_clean in ["salir", "cerrar", "exit", "quit", "terminar", "glyph salir", "glyph cerrar"]:
            return {
                "steps": [{"action": "close_agent"}]
            }

        if q_clean in ["reiniciar", "restart", "reboot", "glyph reiniciar"]:
            return {
                "message": "Reiniciando mis sistemas... Estaré de vuelta en un momento.",
                "steps": [{"action": "restart_agent"}]
            }

        # Cambios de modelo con límites de palabra \b para evitar colisiones como "llamarlo"
        if re.search(r"\b(cambia|usa|pon)\b.*\bllama\b", q_clean):
            return {
                "message": "Saltando al modelo Llama 3 (Groq Cloud). Incrementando capacidad de razonamiento...",
                "steps": [{"action": "switch_model", "model": "llama3"}]
            }

        if re.search(r"\b(cambia|usa|pon)\b.*\bseek\b", q_clean):
            return {
                "message": "Migrando al núcleo nativo de DeepSeek. Activando protocolos de razonamiento avanzado...",
                "steps": [{"action": "switch_model", "model": "deepseek"}]
            }

        if re.search(r"\b(cambia|usa|pon)\b.*\bsamba\b", q_clean):
            return {
                "message": "Migrando a SambaNova Cloud. Activando Llama 3.1 a velocidad extrema.",
                "steps": [{"action": "switch_model", "model": "sambanova"}]
            }

        if re.search(r"\b(cambia|usa|pon)\b.*\bcerebra\b", q_clean):
            return {
                "message": "Conectando con Cerebras Inference. Latencia mínima detectada.",
                "steps": [{"action": "switch_model", "model": "cerebras"}]
            }

        if re.search(r"\b(cambia|usa|pon)\b.*\bgemma\s*4\b", q_clean):
            return {
                "message": "Activando el núcleo de Gemma 4 vía Gemini API. Procesando con arquitectura de vanguardia...",
                "steps": [{"action": "switch_model", "model": "gemma4"}]
            }

        if re.search(r"\b(cambia|usa|pon)\b.*\bgemma\b", q_clean):
            return {
                "message": "Activando Gemma 2 (Google Open Model). Optimizando para respuestas ligeras y eficientes...",
                "steps": [{"action": "switch_model", "model": "gemma"}]
            }

        if re.search(r"\b(cambia|usa|pon)\b.*\brouter\b", q_clean):
            return {
                "message": "Sincronizando con OpenRouter. Accediendo al hub de inteligencia global...",
                "steps": [{"action": "switch_model", "model": "openrouter"}]
            }

        if re.search(r"\b(cambia|usa|pon)\b.*\bm[in]*max\b", q_clean):
            return {
                "message": "Cambiando mi núcleo de procesamiento a Minimax-M2.7 Cloud.",
                "steps": [{"action": "switch_model", "model": "minimax-m2.7:cloud"}]
            }

        if re.search(r"\b(cambia|usa|pon)\b.*\btiny\b", q_clean) or q_clean == "glyph":
            return {
                "message": "Restaurando TinyLlama como núcleo principal de procesamiento.",
                "steps": [{"action": "switch_model", "model": "tinyllama"}]
            }

        # Navegador
        if re.search(r"^(?:glyph\s+)?(abre|abrir|lanza).*\b(navegador|google|chrome)\b", q_clean):
            return {
                "message": "Abriendo Google Chrome en tu PC...",
                "steps": [{"action": "open_browser"}]
            }

        # Escribir
        match_escribir = re.search(r"^(?:glyph\s+)?\b(escribe|escribir|escriba)\b\s+(.+)", q_clean)
        if match_escribir:
            text_to_type = match_escribir.group(2).strip()
            return {
                "message": f"Escribiendo: {text_to_type}",
                "steps": [{"action": "type_text", "text": text_to_type}]
            }

        # Teclas rápidas
        if re.search(r"^(?:glyph\s+)?(?:presiona|da|dale|pulsa|pulsar)?\s*\benter\b$", q_clean):
            return {
                "message": "Presionando la tecla Enter...",
                "steps": [{"action": "press", "key": "enter"}]
            }

        # IAs (Sin Perplexity)
        match_ai = re.search(r"^(?:glyph\s+)?(?:abre|abrir|lanza|ir\s+a|busca\s+en)\s+(chat\s*gpt|claude|gemini)$", q_clean)
        if match_ai:
            ai_key = match_ai.group(1).lower().replace(" ", "")
            ai_map = {"chatgpt": ("ChatGPT", "https://chatgpt.com"), "claude": ("Claude", "https://claude.ai"), "gemini": ("Gemini", "https://gemini.google.com")}
            name, url = ai_map[ai_key]
            return {
                "message": f"Iniciando conexión directa con {name} en el navegador...",
                "steps": [{"action": "open_browser", "url": url}]
            }

        # Interactuar con IAs
        match_interact = re.search(r"^(?:glyph\s+)?(?:pregunta|pregúntale|dile|busca\s+en|mandame\s+referencias\s+en)\s+(?:a\s+)?(chat\s*gpt|claude|gemini)\s+(?:que|sobre|acerca\s+de|)\s*(.+)", q_clean)
        if match_interact:
            ai_key = match_interact.group(1).lower().replace(" ", "")
            raw_query = match_interact.group(2).strip()

            if re.search(r"(en\s+c[oó]digo|por\s+c[oó]digo|v[ií]a\s+c[oó]digo|sin\s+abrir|segundo\s+plano|invisible|sin\s+mi\s+pc|desde\s+el\s+m[oó]vil|nube)", q_clean):
                # Si es Gemini, forzamos navegador o duckduckgo si no hay API
                provider = "duckduckgo" if ("gratis" in q_clean or ai_key == "gemini") else ai_key
                clean_query = re.sub(r"(en|por|v[ií]a)\s+c[oó]digo|sin\s+abrir|invisible|segundo\s+plano|sin\s+mi\s+pc|desde\s+el\s+m[oó]vil", "", raw_query, flags=re.IGNORECASE).strip()
                
                if ai_key == "gemini" and "gratis" not in q_clean:
                    return {
                        "message": f"Iniciando investigación en el modo IA de Google (Navegador).",
                        "steps": [{"action": "open_browser", "url": f"https://www.google.com/search?q={clean_query}"}]
                    }

                return {
                    "message": f"Iniciando investigación en segundo plano vía {provider}.",
                    "steps": [{"action": "background_research", "provider": provider, "query": clean_query}]
                }

            query = re.sub(r"\s+y\s+(?:envíame|envia|dime|pásame|pasame|muéstrame|muestrame|responde|mándame|mandame).*$", "", raw_query, flags=re.IGNORECASE).strip()
            ai_map = {"chatgpt": ("ChatGPT", "https://chatgpt.com"), "claude": ("Claude", "https://claude.ai"), "gemini": ("Gemini", "https://gemini.google.com")}
            name, url = ai_map[ai_key]
            return {
                "message": f"Consultando a {name} sobre '{query}'...",
                "steps": [{"action": "open_browser", "url": url}, {"action": "wait", "seconds": 8}, {"action": "type_text", "text": query}, {"action": "press", "key": "enter"}, {"action": "wait", "seconds": 30}, {"action": "read_screen_text"}]
            }

    # Vía rápida para abrir cualquier programa del PC (Excel, Word, etc.)
    match_app = re.search(r"^(?:glyph\s+)?\b(abre|abrir|lanza|ejecuta|ejecutar|corre|correr)\b\s+(.+)", q_clean) if not text else None
    if match_app and not text:
        raw_name = match_app.group(2).strip()
        
        # DETECCIÓN DE CÓDIGO: Si el nombre contiene palabras clave de Python, lo tratamos como script
        if re.search(r"\b(import|print|def|class|lambda|reload)\b|[;=()]", raw_name):
            clean_script = re.sub(r"^(este\s+)?script\s+(para\s+)?(recargar\s+tu\s+n[uú]cleo\s+)?", "", raw_name, flags=re.IGNORECASE).strip()
            return {
                "message": "Interpretando comando como script Python. Ejecutando...",
                "steps": [{"action": "run_custom_script", "script": clean_script}]
            }

        # Limpiar artículos y casos ya manejados (navegador, archivo)
        app_name = re.sub(r"^(el|la|los|las|este\s+script\s+para\s+)", "", raw_name)
        
        if app_name not in ["navegador", "chrome", "google", "claude", "chatgpt", "gemini"] and "archivo" not in app_name:
            # Mapeo de nombres comunes a ejecutables de Windows
            app_map = {
                "excel": "excel",
                "word": "winword",
                "powerpoint": "powerpnt",
                "bloc de notas": "notepad",
                "calculadora": "calc",
                "cmd": "cmd",
                "terminal": "wt"
            }
            exe_name = app_map.get(app_name.lower(), app_name)
            return {
                "message": f"Iniciando {app_name} en tu sistema...",
                "steps": [{"action": "run_app", "name": exe_name}]
            }

    # Vía rápida para Aprendizaje Automático y Análisis de Datos
    if re.search(r"^(?:glyph\s+)?(analiza|procesa|entrena).*(datos|archivo|dataset)", q_clean):
        # Mejoramos el regex para capturar nombres de archivos con artículos, espacios y comillas
        path_match = re.search(r"(?:archivo|datos|dataset|analiza)\s+(?:el\s+)?[\"“'«]?([\w\.\-/\\ ]+)[\"”'»]?", q_clean)
        target_path = path_match.group(1) if path_match else "data.csv"
        
        # Soporte para "deep_ analysis" con espacio y normalización del objetivo
        goal_match = re.search(r"objetivo\s+([\w\s_]+)", q_clean)
        goal = goal_match.group(1).strip().replace(" ", "") if goal_match else "deep_analysis"

        steps = [{"action": "analyze_dataset", "path": target_path, "goal": goal}]
        
        # Verificamos si también se solicitó síntesis de memoria en la misma orden
        if re.search(r"(sintetiza|mejora).*memoria", q_clean):
            steps.append({"action": "neural_memory_synthesis"})
        return {
            "message": "🧠", # Mensaje minimalista para ahorrar tokens y evitar ruido
            "steps": steps
        }

    if re.search(r"(evoluciona|sintetiza|mejora).*memoria", q_clean):
        return {
            "message": "Activando red neuronal de síntesis para compactar mis experiencias...",
            "steps": [{"action": "neural_memory_synthesis"}]
        }

    # Vía rápida para leer archivos
    match_archivo = re.search(r"(lee|leer|muestra|contenido).*archivo\s+([\w\.\-/\\_]+)", q_clean)
    if match_archivo:
        path = match_archivo.group(2).strip()
        return {
            "message": f"Accediendo al archivo {path} para procesar su información...",
            "steps": [{"action": "read_file", "path": path}]
        }

    # Vía rápida para ver programas abiertos
    if re.search(r"(qué|cuáles).*(programas|procesos|tareas).*(abiertos|corriendo|ejecución)", q_clean):
        return {
            "message": "Escaneando los procesos activos en tu sistema...",
            "steps": [{"action": "list_processes"}]
        }

    # Vía rápida para "ver" la pantalla
    if re.search(r"(qué|que).*(hay|ves|vees|ve).*pantalla", q_clean) or q_clean in ["screenshot", "captura", "pantallazo"]:
        return {
            "message": "Capturando pantalla para que puedas ver lo mismo que yo...",
            "steps": [{"action": "screenshot"}]
        }

    # Vía rápida para Smart Click (inferencia visual)
    match_smart_click = re.search(r"(?:haz\s+)?click\s+(?:en|sobre)\s+(.+)", q_clean)
    if match_smart_click and not re.search(r"\d+", q_clean): # Si no hay números, es descripción, no coordenadas
        target = match_smart_click.group(1).strip()
        return {
            "message": f"Analizando la pantalla para localizar '{target}' y realizar la acción...",
            "steps": [{"action": "smart_click", "description": target}]
        }

    # Vía rápida para clicks por coordenadas
    match_click = re.search(r"click\s+(?:en\s+)?(\d+)[,\s]+(\d+)", q_clean)
    if match_click:
        x, y = int(match_click.group(1)), int(match_click.group(2))
        return {
            "message": f"Haciendo click en la posición ({x}, {y})...",
            "steps": [{"action": "click_at", "x": x, "y": y}]
        }

    # Vía rápida para enviar archivos descargados
    if re.search(r"(envíame|pásame|descarga).*archivo", q_clean):
        return {
            "message": "Buscando el archivo más reciente en tus descargas...",
            "steps": [{"action": "get_latest_download"}]
        }

    # Vía rápida para listar archivos
    if re.search(r"(lista|listar|que\s+archivos|ver\s+archivos).*(carpeta|directorio|aqu[ií])", q_clean):
        return {
            "message": "Explorando el directorio actual...",
            "steps": [{"action": "list_files", "path": "."}]
        }

    if q_clean == "comenzar":
        return {
            "message": "Iniciando mi interfaz gráfica y activando sistemas en tu PC. Estoy listo.",
            "steps": [{"action": "launch_gui"}]
        }

    # Vía rápida para espacio en disco (Windows)
    if re.search(r"(espacio|disco|memoria).*(disco|c:|libre)", q_clean):
        return {
            "message": "Calculando el espacio disponible en tus unidades...",
            "steps": [{"action": "run_custom_script", "script": "import shutil\ntotal, used, free = shutil.disk_usage('C:')\nprint(f'Disco C: Total: {total // (2**30)}GB, Usado: {used // (2**30)}GB, Libre: {free // (2**30)}GB')"}]
        }

    # Vía rápida para encontrar archivos
    match_find = re.search(r"(busca|encuentra|donde esta).*archivo\s+(.+)", q_clean)
    if match_find:
        return {
            "message": f"Iniciando búsqueda de '{match_find.group(2)}'...",
            "steps": [{"action": "find_file", "name": match_find.group(2).strip()}]
        }

    if "enciende la pc" in q_clean or "prende la pc" in q_clean:
        return {
            "message": "Enviando señal de encendido a tu computadora principal...",
            "steps": [{"action": "trigger_cmd", "command": "wol"}]
        }

    if not text:
        return {}

    emotion_match = re.search(r'<(emotion|emocion|mood)>(.*?)</\1>', text, re.DOTALL | re.IGNORECASE)
    ext_emotion = emotion_match.group(2).strip() if emotion_match else ""

    # 2. Limpieza para el parser JSON
    text = re.sub(r'<(thought|thinking|emotion|emocion|mood)>.*?</\1>', '', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'^\s*\*.*?\n', '', text, flags=re.MULTILINE)

    data = None
    try:
        data = json.loads(text)
    except:
        # Búsqueda que acepta tanto objetos {} como listas []
        json_match = re.search(r'(\{.*\}|\[.*\])', text, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group(1))
            except:
                pass

    # Si el modelo devolvió una lista, tomamos el primer elemento
    if isinstance(data, list) and len(data) > 0:
        data = data[0]

    if isinstance(data, dict):
        emotion = data.get("emotion") or data.get("emocion") or data.get("estado") or ext_emotion

        # Verificar si la pregunta original tiene tono de comando
        # Incluimos 'crea', 'genera', 'investiga' para evitar que se borren los steps de creación
        es_orden = re.search(r"\b(abre|busca|haz|pon|click|escribe|lee|ejecuta|dime|enciende|prende|crea|genera|investiga|analiza|diseña|programa)\b", question.lower())
        
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
            "emotion": str(emotion).strip() if emotion else "",
            "message": str(msg_raw) if msg_raw else text.strip(),
            "steps": steps
        }

    # fallback
    # Si falla todo, limpiamos posibles restos de JSON del texto para el usuario
    clean_text = re.sub(r'\{.*\}', '', text, flags=re.DOTALL).strip()
    return {
        "emotion": ext_emotion,
        "message": clean_text if clean_text else text.strip(),
        "steps": []
    }


def normalize_steps(steps):
    if not isinstance(steps, list):
        return []

    # Acciones que el executor.py realmente sabe manejar
    valid_actions = [
        "open_browser", "search", "web_research", "write_plugin", 
        "run_custom_script", "self_upgrade", "type_text", "press", 
        "screenshot", "read_file", "list_processes", "click_at", "hotkey",
        "find_file", "get_latest_download", "run_app", "switch_model", "update_heartbeat",
        "close_agent", "restart_agent", "analyze_dataset", "smart_click", "wait", "read_screen_text",
        "background_research", "neural_memory_synthesis", "trigger_cmd", "launch_gui", "say", "connect_dependency",
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
            if action == "navegador": s["action"] = "open_browser"
            if action == "teclear": s["action"] = "type_text"
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
                
            normalized.append(s)
        elif isinstance(s, str):
            # Solo aceptamos el string si es exactamente una de las acciones válidas
            if s in valid_actions:
                normalized.append({"action": s})
            else:
                print(f"⚠️ Ignorando acción inválida (texto natural): {s}")
    return normalized