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
    valid_actions = "open_browser, search, run_custom_script, type_text, press, screenshot, read_file, list_files, write_file, modify_file, background_research, code_memory_synthesis"
    system_prompt = (
        f"{personality}\nResponde en JSON ESTRICTO y español.\n"
        "Directriz: Saluda con 'Hola, Gabriel.'. Sé ultra-directo. Sin emociones.\n"
        "JSON: {\"thought\":\"\", \"message\":\"\", \"steps\":[]}\n"
        "REGLA: Para datos en tiempo real (BTC, precios, btc, bitcoin, clima), DEBES usar 'background_research' en 'steps' con el parámetro 'query'. PROHIBIDO inventar cifras.\n"
        "IMPORTANTE: Si usas 'background_research', deja el campo 'message' breve, yo insertaré el resultado real.\n"
        f"Acciones: [{valid_actions}]. Sistema: Windows."
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
            "max_tokens": 512,
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
            timeout=45
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
    
    identity_header = f"{personality}\nResponde en español a Gabriel.\n"
    identity_header += "Sé breve. Si necesitas investigar usa 'background_research' en el JSON.\n"
    identity_header += "REGLA: La teoría sin acción es un error. Usa 'steps' siempre que sea necesario."

    prompt = f"""
<|system|>
{identity_header.strip()}
JSON: {{ "thought": "", "message": "Hola, Gabriel...", "steps": [] }}
Acciones: [open_browser, search, run_custom_script, type_text, press, screenshot, read_file, list_files, write_file, modify_file, background_research, code_memory_synthesis].

Contexto: {context}
Historial: {history}

<|user|>
{question}

<|assistant|>
"""

    return ask_model(prompt, model=model, temperature=temperature)