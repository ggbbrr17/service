from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS
import sys
import os
import requests
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from core.engine import run

app = Flask(__name__)
CORS(app) # Permitir que a App Móvel acesse a API

# ---------------- CONFIG / AUTH ----------------
WEB_PASSWORD = os.getenv("GLYPH_PASSWORD", "glyph123") # Cambia esto por seguridad
HOME_PC_URL = os.getenv("GLYPH_HOME_URL", "") # URL de tu PC local (ej: de LocalTunnel)

def check_auth(request_data=None):
    """Verifica la contraseña en los headers o en el body."""
    # Primero revisamos el header (estándar para apps móviles)
    auth_header = request.headers.get("X-Glyph-Secret")
    if auth_header == WEB_PASSWORD:
        return True
    
    # Fallback al body (para compatibilidad con la web terminal actual)
    if request_data and request_data.get("password") == WEB_PASSWORD:
        return True
        
    return False

# ---------------- API ----------------
@app.route("/", methods=["GET"])
@app.route("/health", methods=["GET"])
@app.route("/api/v1/status", methods=["GET"])
def health():
    """Endpoint para verificar que el servidor y el motor están operativos."""
    return jsonify({
        "status": "online",
        "entity": "Glyph Autonomous",
        "version": "3.0.0-headless",
        "tunnel_active": bool(HOME_PC_URL)
    }), 200

@app.route("/ask", methods=["POST"])
@app.route("/api/v1/ask", methods=["POST"])
def ask():
    try:
        data = request.get_json(force=True)
    except:
        data = {}

    # Verificación de seguridad
    if not check_auth(data) and os.getenv("GLYPH_PASSWORD"):
        return jsonify({"message": "Acceso denegado. Contraseña incorrecta."}), 403

    question = data.get("question", "")
    if not question:
        return jsonify({"message": "La pregunta no puede estar vacía."}), 400
        
    dry_run = bool(data.get("dry_run", False))
    
    # Extraer campos multimodales enviados desde la App
    image = data.get("base64_image")
    video = data.get("base64_video")
    audio = data.get("base64_audio")
    
    print(f"📱 API Request: {question} (DryRun: {dry_run})")

    # --- MODO TÚNEL (Redirección a PC Local) ---
    if HOME_PC_URL:
        try:
            clean_url = HOME_PC_URL.rstrip('/')
            # Reenviamos la petición a la PC de casa
            r = requests.post(f"{clean_url}/ask", json=data, timeout=30)
            return jsonify(r.json())
        except Exception as e:
            return jsonify({
                "message": f"⚠️ Glyph Cloud: No pude contactar con tu PC local ({e}). Ejecutando en modo limitado...",
                "results": [{"action": "tunnel_error", "ok": False, "msg": str(e)}]
            }), 502

    history = data.get("history", "")
    
    # --- MODO NUBE (Motor local en Render) ---
    res = run(
        question, dry_run=dry_run, 
        history=history,
        image=image, video=video, audio=audio,
        is_user=True
    )
    
    # Si el motor devuelve un error de conexión que en realidad es por falta de GUI
    if "ERROR_CONNECTION" in str(res.get("message", "")) and dry_run is False:
        # Opcional: Podrías añadir lógica aquí para notificar que la acción
        # requiere el modo túnel (Home PC) activo.
        pass
        
    return jsonify(res)

@app.route("/api/v1/notifications", methods=["GET"])
def notifications():
    """Consulta si hay mensajes pendientes de Glyph (asíncronos)."""
    from core.memory import get_notifications
    return jsonify({
        "notifications": get_notifications(clear=True)
    })

@app.route("/api/v1/history", methods=["GET"])
def history():
    """Devuelve el historial de interacciones guardado en memoria."""
    from core.memory import load_memory
    mem = load_memory()
    return jsonify({
        "introspection": mem.get("introspection_history", []),
        "learning": mem.get("reglas_aprendidas", [])
    })

# ---------------- START ----------------
# File moved to old/glyph_server.py
if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
