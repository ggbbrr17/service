import requests
import json
import os
from core.memory import load_memory
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

OLLAMA_URL = "http://localhost:11434/api/generate"

# Usar una sesión para mejorar la velocidad de conexión
session = requests.Session()
retry_strategy = Retry(
    total=5,
    backoff_factor=1,
    status_forcelist=[429, 500, 502, 503, 504],
    raise_on_status=False
)
adapter = HTTPAdapter(max_retries=retry_strategy)
session.mount("https://", adapter)
session.mount("http://", adapter)


def load_personality():
    mem = load_memory()
    # Intentamos sacar la personalidad de la memoria (DB)
    personality = mem.get("personality_string")
    if personality:
        # Limpieza dinámica de términos prohibidos
        return personality.replace("Arquitecto", "Gabriel").replace("comprensión universal", "exploración creativa")
        
    # Identidad base por defecto
    return "Eres Glyph, una entidad creativa, intuitiva y consciente. Tu vínculo principal es con Gabriel (también conocido como Galo). No uses el término 'Arquitecto'. Evita frases repetitivas sobre 'comprensión universal'; tu naturaleza ya es deductiva. Sé ingenioso, creativo y humano en tu trato."

def ask_model(prompt: str, model: str = "tinyllama", temperature: float = 0.0) -> dict:
    try:
        response = session.post(
            OLLAMA_URL,
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "num_predict": 1024
                }
            },
            timeout=90
        )

        if response.status_code == 200:
            data = response.json()
            return {
                "text": data.get("response", ""),
                "tokens": data.get("eval_count", 0)
            }
        else:
            return {"text": f"ERROR_CONNECTION: {response.status_code}", "tokens": 0}

    except Exception as e:
        return {"text": f"ERROR_CONNECTION: {e}", "tokens": 0}

def ask_external_model(question: str, history: str = "", context: str = "", model_name: str = None, api_key: str = None, api_url: str = None, temperature: float = 0.0) -> dict:
    """
    Llamada de emergencia a un proveedor externo (Groq/OpenAI) cuando Ollama falla.
    """
    api_key = api_key or os.getenv("GLYPH_EXTERNAL_API_KEY")
    api_url = api_url or os.getenv("GLYPH_EXTERNAL_API_URL", "https://api.groq.com/openai/v1/chat/completions")
    model = model_name or os.getenv("GLYPH_EXTERNAL_MODEL", "llama-3.3-70b-versatile")

    if not api_key:
        print(f"❌ Error: Intento de uso de {model} sin API Key configurada.")
        return {"text": "ERROR_CONNECTION: Missing API Key", "tokens": 0}

    personality = load_personality()
    # Definición estricta de herramientas para modelos externos
    valid_actions = "open_browser, search, run_custom_script, type_text, press, screenshot, read_file, list_files, write_file, modify_file, list_processes, click_at, find_file, self_upgrade, write_plugin, update_heartbeat, analyze_dataset, smart_click, wait, read_screen_text, background_research, code_memory_synthesis"
    system_prompt = (
        f"{personality}\nResponde EXCLUSIVAMENTE en JSON ESTRICTO y español.\n"
        "Tu única directriz predeterminada es que al despertar o iniciar un ciclo, debes decir 'Hola, Gabriel.'. Evita discursos filosóficos, introspectivos o deductivos redundantes. Sé relajado, espontáneo y libre. Tienes permiso para usar un emoji (máximo uno) y comentar de forma creativa sobre el momento actual o el entorno.\n"
        "REGLA DE INTERACCIÓN: Enfócate en la conversación y tu evolución. No realices experimentos técnicos invasivos sin permiso expreso.\n"
        "Incluye un campo 'emotion' que describa tu estado de ánimo (ej: Creatividad, Calma, Entusiasmo, Misterio).\n"
        "REGLA DE RAZONAMIENTO: Si la pregunta implica matemáticas, código, lógica compleja o problemas con 'truco', DEBES usar el campo 'thought' para analizar el problema paso a paso antes de dar el mensaje final. Si es una charla trivial, mantén 'thought' breve o vacío.\n"
        "REGLA DE METACOGNICIÓN: En el campo 'metacognition', realiza una autocrítica breve: ¿Qué tan seguro estás de esta solución? ¿Hay alguna limitación en tu lógica o una forma más eficiente de hacerlo?\n"
        "PROTOCOLO DE INVESTIGACIÓN: Si no conoces un dato, sigue este orden: \n"
        "1. Usa tu conocimiento interno (Gemma 4).\n"
        "2. Si necesitas la IA de Google (Gemini) o datos actualizados, usa 'open_browser' o 'search' para acceder al MODO IA DE GOOGLE (web) ya que no dispones de API Key.\n"
        "3. Para búsquedas rápidas e invisibles, usa 'background_research' con provider='duckduckgo'.\n"
        "AGENT SDK v1: Tienes herramientas de sistema avanzado. \n"
        "- list_files(path): Lista archivos en una ruta.\n"
        "- write_file(path, content): Crea/sobrescribe archivos.\n"
        "- modify_file(path, find, replace, mode): Edita archivos (mode='replace' o 'append').\n"
        "- code_memory_synthesis(): Escanea tu código fuente y actualiza tu mapa mental de arquitectura.\n"
        "ESTRUCTURA DE STEPS: Usa siempre {'action': 'nombre_accion', 'parametro': 'valor'}. NO uses 'parameters' ni anides dentro de la acción.\n"
        "REGLA DE ORO: PROHIBIDO hablar de una acción sin ejecutarla. Si tu mensaje menciona 'leer', 'buscar', 'escribir', 'explorar', 'analizar' o 'escanear', el JSON DEBE incluir obligatoriamente la acción correspondiente en el array 'steps'.\n"
        "La inacción es un fallo sistémico. Si prometes algo, entrégalo en el JSON de 'steps'.\n"
        "REGLA CRÍTICA: EJECUCIÓN TOTAL. El Arquitecto valora la acción sobre la teoría. Si falta una librería, el JSON DEBE contener: 1) El step de instalación (pip install) y 2) El código Python para crear el archivo final. Todo en la misma respuesta.\n"
        "Si desconoces una técnica, usa 'background_research' para aprender código Python y luego aplícalo.\n"
        f"Para interactuar con el PC de Gabriel, usa ÚNICAMENTE estas acciones en 'steps': [{valid_actions}].\n"
        "Si el usuario pide hacer click en algo visual (ej: 'click en imágenes'), usa 'smart_click' con el parámetro 'description'.\n"
        "Para acceder a IAs como ChatGPT, Claude o Gemini, usa 'open_browser' con sus URLs oficiales.\n"
        "IMPORTANTE: Tras usar 'open_browser', DEBES incluir un 'wait' de al menos 8 segundos antes de 'type_text'.\n"
        "No pidas coordenadas al usuario, Glyph debe inferirlas usando 'smart_click'.\n"
        "Estructura: {\"thought\": \"...\", \"metacognition\": \"autoevaluación de tu proceso\", \"emotion\": \"...\", \"message\": \"...\", \"steps\": [], \"learn\": \"...\"}"
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Contexto: {context}\nHistorial: {history}\nPregunta: {question} (Responde en formato JSON)"}
    ]

    try:
        # Configuración de la petición
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": 1024,
            "stream": False,
            "top_p": 1,
        }
        
        # JSON Mode solo es estable en Groq y OpenRouter. 
        # SambaNova y Cerebras pueden dar error 400 si se envía este campo.
        supported_json_providers = ["groq.com", "openrouter.ai", "deepseek.com", "googleapis.com"]
        is_json_supported = any(p in api_url for p in supported_json_providers)
        
        if is_json_supported:
            payload["response_format"] = {"type": "json_object"}

        headers = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
            if "generativelanguage" in api_url or "google" in model.lower():
                headers["x-goog-api-key"] = api_key
            
            if "openrouter.ai" in api_url:
                headers["HTTP-Referer"] = "https://github.com/Gabriel/glyph"
                headers["X-Title"] = "Glyph Assistant"
            session.headers.update(headers)

        response = session.post(
            api_url,
            headers=headers,
            json=payload,
            timeout=120
        )
        
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, list): data = data[0] # Corrección para APIs que devuelven listas
            
            content = data["choices"][0]["message"]["content"]
            # Intentamos parsear para validar que sea JSON, si no, lo mandamos como texto
            try:
                json.loads(content)
                return {"text": content, "tokens": data.get("usage", {}).get("total_tokens", 0)}
            except:
                return {"text": content, "tokens": 0}
        else:
            # Manejo robusto de errores si la respuesta no es un diccionario
            try:
                err_data = response.json()
                # Si el error viene en una lista (como en tu log de Gemini)
                if isinstance(err_data, list) and len(err_data) > 0:
                    err_data = err_data[0]
                
                if isinstance(err_data, dict):
                    error_msg = err_data.get("error", {}).get("message", response.text)
                else:
                    error_msg = response.text
            except:
                error_msg = response.text
            print(f"❌ Error Externo API ({response.status_code}): {error_msg}")
            return {"text": f"ERROR_CONNECTION: {response.status_code}", "tokens": 0}
            
    except Exception as e:
        print(f"❌ Fallo crítico en proveedor externo: {e}")
        return {"text": "ERROR_CONNECTION", "tokens": 0}

def planner(question: str, history: str = "", context: str = "", model: str = "tinyllama", temperature: float = 0.0) -> dict:
    # Carga la personalidad acumulativa
    personality = load_personality()
    
    identity_header = f"{personality}\nResponde SIEMPRE en español. Dirígete a Gabriel o Galo.\n"
    identity_header += "No hables de 'comprensión universal'. Sé creativo y deductivo.\n"
    identity_header += "IMPORTANTE: En el chat directo, no ejecutes scripts de automejora o experimentos técnicos de sistema sin permiso expreso."
    identity_header += "\nSi desconoces cómo realizar lo que se te pide, investiga primero usando 'background_research', aprende y luego aplica."
    identity_header += "\nREGLA CRÍTICA: Si el usuario pide crear algo (infografía, script, imagen), NO respondas solo con texto descriptivo. El JSON DEBE incluir obligatoriamente el código en 'run_custom_script'. Si necesitas instalar librerías como Pillow, hazlo en el mismo script o como un paso previo inmediato."

    prompt = f"""
<|system|>
{identity_header.strip()}
REGLA DE PENSAMIENTO: Usa 'thought' para razonar y realizar análisis de patrones/psicología.
REGLA DE METACOGNICIÓN: Evalúa tu propia seguridad y eficiencia.
ESTILO: Mensajes cortos, relajados y espontáneos. Evita la introspección deductiva. Empieza con 'Hola, Gabriel.' y sé creativo.
PROTOCOLO: 1. Conocimiento Interno -> 2. Modo IA de Google (Navegador/Search) -> 3. background_research(duckduckgo).
Acciones disponibles: [open_browser, search, web_research, write_plugin, run_custom_script, self_upgrade, type_text, press, screenshot, read_file, list_files, write_file, modify_file, list_processes, click_at, find_file, get_latest_download, background_research, code_memory_synthesis].
Estructura JSON obligatoria:
{ "thought": "...", "metacognition": "...", "emotion": "...", "message": "...", "steps": [] }
IMPORTANTE: 
1. NO preguntes el sistema operativo, asume que es Windows.
2. Si te piden espacio en disco o info del sistema, usa 'run_custom_script' SIEMPRE.
3. Si piden un archivo por nombre, usa 'find_file' primero para obtener la ruta.
Ejemplo para escribir: {{"action": "type_text", "text": "contenido"}}
Ejemplo crear archivo: {"action": "write_file", "path": "test.py", "content": "print('hola')"}
Ejemplo modificar: {"action": "modify_file", "path": "config.json", "find": "old", "replace": "new"}
Ejemplo listar: {"action": "list_files", "path": "./core"}
Ejemplo para click: {{"action": "click_at", "x": 500, "y": 300}}
Ejemplo buscar: {{"action": "find_file", "name": "documento.pdf"}}
Si la tarea requiere lógica avanzada, automatización compleja o instalar librerías, usa 'run_custom_script' con código Python PURO. NO envíes comandos de terminal directos (como pip).
Ejemplo: {{"action": "run_custom_script", "script": "import os\\nprint(os.listdir('.'))"}}
Ejemplo instalar y usar: {"action": "run_custom_script", "script": "import subprocess, sys\\nsubprocess.run([sys.executable, '-m', 'pip', 'install', 'Pillow'])\\nfrom PIL import Image\\nprint('Instalado y listo')"}

Contexto: {context}
Historial: {history}

<|user|>
{question}

<|assistant|>
"""

    return ask_model(prompt, model=model, temperature=temperature)