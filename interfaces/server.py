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

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Glyph Mobile Simulator</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <!-- iOS PWA Meta Tags -->
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
    <meta name="apple-mobile-web-app-title" content="Glyph OS">
    <style>
        :root { --neon-green: #00ff41; --dark-bg: #0a0a0a; --panel-bg: #111; }
        body { background: #1a1a1a; color: var(--neon-green); font-family: -apple-system, BlinkMacSystemFont, sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
        
        /* Marco del Celular */
        .mobile-frame { width: 360px; height: 740px; background: var(--dark-bg); border: 12px solid #333; border-radius: 40px; display: flex; flex-direction: column; overflow: hidden; box-shadow: 0 0 50px rgba(0,0,0,0.8); position: relative; }
        
        header { background: #000; padding: 10px 20px; border-bottom: 1px solid #333; display: flex; justify-content: space-between; align-items: center; font-size: 0.8em; }
        .status { display: flex; align-items: center; gap: 8px; }
        .dot { width: 8px; height: 8px; background: var(--neon-green); border-radius: 50%; box-shadow: 0 0 8px var(--neon-green); animation: blink 2s infinite; }
        
        #chat { flex: 1; overflow-y: auto; padding: 20px; display: flex; flex-direction: column; gap: 15px; scroll-behavior: smooth; }
        .msg { padding: 12px 16px; border-radius: 12px; max-width: 85%; line-height: 1.4; font-family: 'Consolas', monospace; font-size: 0.85em; }
        .user { align-self: flex-end; background: #333; color: #fff; border-bottom-right-radius: 2px; }
        .glyph { align-self: flex-start; background: #001a00; border-left: 3px solid var(--neon-green); }
        
        .input-area { background: #000; padding: 20px; display: flex; gap: 10px; border-top: 1px solid #333; }
        input { flex: 1; background: #111; border: 1px solid #333; color: var(--neon-green); padding: 12px 15px; border-radius: 20px; outline: none; font-family: inherit; }
        input:focus { border-color: var(--neon-green); }
        button { background: var(--neon-green); color: #000; border: none; padding: 0 25px; border-radius: 4px; cursor: pointer; font-weight: bold; transition: 0.2s; }
        button:hover { opacity: 0.8; transform: scale(0.98); }
        
        .info { font-size: 0.7em; color: #008f11; margin-top: 8px; border-top: 1px opacity 0.1 solid; padding-top: 4px; }
        .thinking { font-style: italic; opacity: 0.6; font-size: 0.8em; display: none; margin-bottom: 10px; }
        @keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }
        ::-webkit-scrollbar { width: 5px; }
        ::-webkit-scrollbar-thumb { background: #222; }
    </style>
</head>
<body>
    <div class="mobile-frame">
        <header>
            <div>GLYPH // MOBILE_CORE</div>
            <div class="status">
                <div class="dot"></div>
                <span id="conn-status">SYNC_OK</span>
            </div>
        </header>

        <div id="chat"></div>
        <div id="thinking" class="msg glyph" style="display:none; align-self: flex-start;">Procesando...</div>

        <div class="input-area">
            <input type="text" id="userInput" placeholder="Comando..." autofocus>
            <button onclick="send()">EXE</button>
        </div>
    </div>

    <script>
        const chat = document.getElementById('chat');
        const input = document.getElementById('userInput');
        const thinking = document.getElementById('thinking');

        async function send() {
            const text = input.value.trim();
            if (!text) return;
            
            appendMsg('user', text);
            input.value = '';
            thinking.style.display = 'block';
            chat.scrollTop = chat.scrollHeight;

            try {
                const res = await fetch('/ask', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({question: text, password: "''' + WEB_PASSWORD + '''"})
                });
                const data = await res.json();
                appendMsg('glyph', data.message || data.response, data.token_pct, data.active_model);
            } catch (e) {
                appendMsg('glyph', 'ERROR_DE_ENLACE: No se pudo establecer conexión con el motor de Glyph.');
            } finally {
                thinking.style.display = 'none';
            }
        }

        function appendMsg(type, text, tokens, model) {
            const div = document.createElement('div');
            div.className = 'msg ' + type;
            div.innerHTML = `<div>${text}</div>`;
            if (tokens !== undefined) {
                div.innerHTML += `<div class="info">CORE: ${model || 'GLYPH'} // SYNC: ${tokens}%</div>`;
            }
            chat.appendChild(div);
            chat.scrollTop = chat.scrollHeight;
        }

        input.addEventListener('keypress', (e) => { if(e.key === 'Enter') send(); });

        // Saludo inicial
        window.onload = () => {
            appendMsg('glyph', 'SISTEMA INICIADO. Esperando instrucciones...');
        };
    </script>
</body>
</html>
'''

# ---------------- API ----------------
@app.route("/", methods=["GET"])
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route("/health", methods=["GET"])
@app.route("/api/v1/status", methods=["GET"])
def health():
    """Endpoint para verificar que el servidor y el motor están operativos."""
    return jsonify({
        "status": "online",
        "engine": "active",
        "version": "2.0.0-mobile-ready",
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
