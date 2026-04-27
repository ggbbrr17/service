from flask import Flask, request, jsonify, render_template_string
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from core.engine import run

app = Flask(__name__)

# ---------------- SAFETY / CONFIG ----------------
WEB_PASSWORD = os.getenv("GLYPH_PASSWORD", "glyph123") # Cambia esto por seguridad

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Glyph Web Terminal</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { background: #000; color: #0f0; font-family: 'Segoe UI', sans-serif; display: flex; flex-direction: column; height: 100vh; margin: 0; }
        #chat { flex: 1; overflow-y: auto; padding: 20px; display: flex; flex-direction: column; gap: 10px; }
        .msg { padding: 10px; border-radius: 10px; max-width: 80%; word-wrap: break-word; }
        .user { align-self: flex-end; background: #1a1a1a; color: #fff; border: 1px solid #333; }
        .glyph { align-self: flex-start; background: #001a00; border: 1px solid #0f0; }
        .input-area { background: #121212; padding: 20px; display: flex; gap: 10px; border-top: 1px solid #333; }
        input { flex: 1; background: #000; border: 1px solid #0f0; color: #0f0; padding: 12px; border-radius: 25px; outline: none; }
        button { background: #0f0; color: #000; border: none; padding: 10px 25px; border-radius: 25px; cursor: pointer; font-weight: bold; }
        .info { font-size: 0.7em; color: #444; margin-top: 5px; }
    </style>
</head>
<body>
    <div id="chat"></div>
    <div class="input-area">
        <input type="text" id="userInput" placeholder="Comando para Glyph..." autofocus>
        <button onclick="send()">ENVIAR</button>
    </div>

    <script>
        const chat = document.getElementById('chat');
        const input = document.getElementById('userInput');

        async function send() {
            const text = input.value.trim();
            if (!text) return;
            
            appendMsg('user', text);
            input.value = '';

            try {
                const res = await fetch('/ask', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({question: text, password: "''' + WEB_PASSWORD + '''"})
                });
                const data = await res.json();
                appendMsg('glyph', data.message || data.response, data.token_pct, data.active_model);
            } catch (e) {
                appendMsg('glyph', 'Error: No se pudo conectar con el motor local.');
            }
        }

        function appendMsg(type, text, tokens, model) {
            const div = document.createElement('div');
            div.className = 'msg ' + type;
            div.innerHTML = `<div>${text}</div>`;
            if (tokens !== undefined) {
                div.innerHTML += `<div class="info">${model || 'IA'} | Consciencia: ${tokens}%</div>`;
            }
            chat.appendChild(div);
            chat.scrollTop = chat.scrollHeight;
        }

        input.addEventListener('keypress', (e) => { if(e.key === 'Enter') send(); });
    </script>
</body>
</html>
'''

# ---------------- API ----------------
@app.route("/", methods=["GET"])
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route("/ask", methods=["POST"])
def ask():
    data = request.get_json(force=True)
    
    # Verificación de seguridad básica
    if data.get("password") != WEB_PASSWORD and os.getenv("GLYPH_PASSWORD"):
        return jsonify({"message": "Acceso denegado. Contraseña incorrecta."}), 403

    question = data.get("question", "")
    dry_run = bool(data.get("dry_run", False))
    
    res = run(question, dry_run=dry_run)
    return jsonify(res)

# ---------------- START ----------------
# File moved to old/glyph_server.py
if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)