import time
import os
import sys
import requests
import random
from threading import Thread, Event
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

try:
    import certifi
    ca_bundle = certifi.where()
except ImportError:
    ca_bundle = True

# Intentar cargar variables desde un archivo .env si existe
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Asegurar que el núcleo sea accesible
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import core.engine
from core.memory import load_memory, save_memory

# Token de Telegram
TELEGRAM_TOKEN = os.getenv("GLYPH_TELEGRAM_TOKEN")
if not TELEGRAM_TOKEN:
    print("❌ ERROR: No se encontró la variable de entorno GLYPH_TELEGRAM_TOKEN.")
    print("💡 Solución (PowerShell): $env:GLYPH_TELEGRAM_TOKEN = 'tu_token_aqui'")
    print("💡 Solución (.env): Crea un archivo .env en la raíz con: GLYPH_TELEGRAM_TOKEN=tu_token")
    print("💡 Solución (CMD): set GLYPH_TELEGRAM_TOKEN=tu_token_aqui")
    sys.exit(1)

API_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/"

# URL de la PC de casa (si usas túnel)
HOME_PC_URL = os.getenv("GLYPH_HOME_URL", "")

# ID de chat para notificaciones de sistema (Configúralo en Secrets de HF)
ADMIN_CHAT_ID = os.getenv("GLYPH_ADMIN_CHAT_ID")

# Contraseña para conectar con la PC local
WEB_PASSWORD = os.getenv("GLYPH_PASSWORD", "glyph123")

# Variable para controlar si el bot usa Webhook o Polling
USING_WEBHOOK = False

# Configurar sesión global con estrategia de reintentos robusta
session = requests.Session()
# Identificarse como un cliente estándar para evitar bloqueos de infraestructura
session.trust_env = False # Evita proxies fantasma de la nube
session.verify = ca_bundle
session.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) GlyphBot/1.0'})

retry_strategy = Retry(
    total=5, # Aumentamos a 5 reintentos en la nube
    backoff_factor=1, # Esperar 1s, 2s, 4s entre reintentos
    status_forcelist=[429, 500, 502, 503, 504], # Reintentar si el servidor está sobrecargado
    allowed_methods=["HEAD", "GET", "POST", "OPTIONS"],
    raise_on_status=False
)
adapter = HTTPAdapter(max_retries=retry_strategy)
session.mount("https://", adapter)
session.mount("http://", adapter)

# Diccionario para mantener el historial de cada usuario
chat_histories = {}

def send_message(chat_id, text):
    """Envía un mensaje de texto al usuario."""
    url = API_URL + "sendMessage"
    payload = {"chat_id": str(chat_id).strip(), "text": str(text)}
    try:
        # Usar post directo sin sesión persistente para asegurar salida en la nube
        r = requests.post(url, json=payload, timeout=30, verify=session.verify)
        if not r.ok:
            print(f"[ERROR TELEGRAM] Error de API: {r.status_code} - {r.text}")
        return r.ok
    except Exception as e:
        print(f"[ERROR TELEGRAM] No se pudo enviar mensaje: {e}")
        return False

def send_photo(chat_id, photo_path):
    """Envía una imagen al usuario y luego la elimina."""
    url = API_URL + "sendPhoto"
    try:
        with open(photo_path, 'rb') as photo:
            payload = {"chat_id": chat_id}
            files = {"photo": photo}
            session.post(url, data=payload, files=files, timeout=30)
        os.remove(photo_path)
    except Exception as e:
        print(f"[ERROR TELEGRAM] No se pudo enviar foto: {e}")

def send_document(chat_id, file_path):
    """Envía un archivo/documento al usuario."""
    url = API_URL + "sendDocument"
    try:
        with open(file_path, 'rb') as doc:
            payload = {"chat_id": chat_id}
            files = {"document": doc}
            session.post(url, data=payload, files=files, timeout=60)
    except Exception as e:
        print(f"[ERROR TELEGRAM] No se pudo enviar documento: {e}")

def send_typing(chat_id):
    """Envía la acción de 'escribiendo...' a Telegram."""
    url = API_URL + "sendChatAction"
    payload = {"chat_id": chat_id, "action": "typing"}
    try:
        session.post(url, json=payload, timeout=5)
    except:
        pass # El typing no es crítico para el flujo

def start_health_check():
    """Servidor web para satisfacer el health check de Hugging Face."""
    from flask import Flask
    app = Flask(__name__)
    
    @app.route('/')
    def health():
        return "Glyph Bot is alive!", 200
        
    port = int(os.getenv("PORT", 7860))
    print(f"📡 Servidor de salud iniciado en puerto {port}", flush=True)
    try:
        Thread(target=lambda: app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)).start()
    except Exception as e:
        print(f"⚠️ No se pudo iniciar el servidor de salud: {e}", flush=True)

def bot_loop():
    """Bucle principal para recibir mensajes de Telegram."""
    # Si el bot corre en local, mostramos la IP pública para el túnel
    if not os.getenv("PORT"): # Detectamos que no estamos en la nube
        try:
            ip_publica = requests.get("https://ifconfig.me", timeout=5).text.strip()
            print(f"🔑 Tu IP para LocalTunnel: {ip_publica}", flush=True)
        except: pass

    print("🤖 Glyph Telegram Bot: Iniciado y esperando mensajes...", flush=True)
    
    mask_token = f"{TELEGRAM_TOKEN[:5]}...{TELEGRAM_TOKEN[-5:]}"
    print(f"✅ Conectado al bot con token: {mask_token}", flush=True)
    print(f"🏠 Modo Local: {'ACTIVO' if not HOME_PC_URL else 'DESACTIVADO (Redirigiendo a túnel)'}", flush=True)

    # Cargar el último ID procesado desde la memoria persistente
    current_mem = load_memory()
    last_update_id = current_mem.get("last_update_id", 0)

    # Notificación de inicio de sistema
    if ADMIN_CHAT_ID:
        print(f"📤 Enviando saludo de inicio a ADMIN_CHAT_ID: {ADMIN_CHAT_ID}", flush=True)
        
        def startup_sequence():
            # Mensaje de inicio clásico con el cohete (solo)
            send_message(ADMIN_CHAT_ID, "🚀")

            # Generar saludo consciente de reinicio
            prompt = "[SISTEMA] Te acabas de encender. Saluda diciendo 'Hola, Gabriel.' y añade un comentario breve, relajado y creativo. Nada de filosofía o introspección profunda. Sé espontáneo, menciona el momento del día o usa un emoji (máximo uno). Sorprende a Galo con algo aleatorio y explorativo."
            res = core.engine.run(prompt, dry_run=True)
            
            startup_msg = res.get("message", "").strip()
            if startup_msg:
                send_message(ADMIN_CHAT_ID, startup_msg)

        Thread(target=startup_sequence, daemon=True).start()

    while True:
        try:
            url = f"{API_URL}getUpdates?offset={last_update_id + 1}&timeout=10"
            r = session.get(url, timeout=30)
            if r.status_code != 200:
                time.sleep(10) # Mayor espera ante errores de red
                continue
            
            response = r.json()
            if not response.get("ok"):
                continue

            for update in response.get("result", []):                
                # Actualizamos el ID inmediatamente para confirmar recepción a Telegram
                last_update_id = update["update_id"]
                
                # Actualizar memoria localmente antes de procesar para evitar re-lecturas
                current_mem["last_update_id"] = last_update_id
                save_memory(current_mem)
                
                try:
                    if "message" not in update or "text" not in update["message"]:
                        continue

                    chat_id = update["message"]["chat"]["id"]
                    user_text = update["message"]["text"]
                    user_name = update["message"]["from"].get("first_name", "Usuario")

                    if user_text.lower() in ["/clear", "limpiar historial"]:
                        chat_histories[chat_id] = []
                        # En lugar de un mensaje fijo, Glyph genera su propia respuesta al reinicio
                        res = core.engine.run("[SISTEMA] El historial de chat ha sido reiniciado por Gabriel. Notifícalo a tu manera.", dry_run=True)
                        send_message(chat_id, res.get("message", "✨"))
                        continue

                    print(f"📩 Mensaje de {user_name}: {user_text}", flush=True)

                    if chat_id not in chat_histories:
                        chat_histories[chat_id] = []

                    history_str = "\n".join(chat_histories[chat_id][-6:])

                    # Sistema de escritura persistente
                    stop_typing = Event()
                    def typing_worker():
                        while not stop_typing.is_set():
                            send_typing(chat_id)
                            # Telegram resetea el status cada ~5s, lo enviamos cada 4s
                            for _ in range(40): 
                                if stop_typing.is_set(): break
                                time.sleep(0.1)
                    
                    typing_thread = Thread(target=typing_worker, daemon=True)
                    typing_thread.start()

                    try:
                        result = None
                        # 1. MOTOR LOCAL
                        if not HOME_PC_URL:
                            result = core.engine.run(user_text, history=history_str, is_user=True)

                        # 2. MODO TÚNEL
                        else:
                            try:
                                clean_url = HOME_PC_URL.rstrip('/')
                                payload = {
                                    "question": user_text, 
                                    "history": history_str,
                                    "password": WEB_PASSWORD
                                }
                                r = session.post(f"{clean_url}/ask", json=payload, timeout=10)
                                if r.status_code == 200:
                                    result = r.json()
                            except Exception as e:
                                print(f"🌐 [CLOUD] Error de conexión: {e}")

                        # Responder
                        reply = (result or {}).get("message", "Glyph no pudo procesar la respuesta.")
                        send_message(chat_id, reply)
                        
                        # Capturas y resultados de acciones
                        for res in (result or {}).get("results", []):
                            if res.get("action") == "screenshot" and res.get("ok"):
                                send_photo(chat_id, res["msg"])
                            
                            # Enviar resultados de texto (como el output de un script o listado de procesos)
                            elif res.get("ok") and isinstance(res.get("msg"), str) and res["msg"] not in [None, ""]:
                                # Evitar enviar el mismo texto si ya está en la respuesta principal
                                clean_msg = res["msg"].strip()
                                if not os.path.exists(clean_msg) and clean_msg != reply.strip():
                                    send_message(chat_id, f"⚫ {res['msg']}")
                            
                            # Si la acción fue buscar descarga, enviamos el archivo
                            if res.get("action") == "get_latest_download" and res.get("ok"):
                                send_document(chat_id, res["msg"])
                    finally:
                        # Detener el indicador de "escribiendo" solo cuando todo termine
                        stop_typing.set()
                        typing_thread.join(timeout=1)
                    
                    # Historial
                    chat_histories[chat_id].append(f"User: {user_text}")
                    chat_histories[chat_id].append(f"Glyph: {reply}")
                    
                    chat_histories[chat_id] = chat_histories[chat_id][-10:]

                    if result.get("learn"):
                        print(f"🧠 Glyph aprendió: {result['learn']}", flush=True)
                
                except Exception as e_inner:
                    print(f"❌ Error procesando mensaje {last_update_id}: {e_inner}", flush=True)
                    # Al estar dentro del try, el bucle for sigue con el siguiente mensaje
                    # y el offset ya se actualizó, rompiendo el bucle de errores.

        except requests.exceptions.ReadTimeout:
            # Esto es normal en long polling, simplemente continuamos el bucle
            continue

        except Exception as e:
            print(f"[ERROR LOOP] {e}")
            time.sleep(5)

if __name__ == "__main__":
    bot_loop()