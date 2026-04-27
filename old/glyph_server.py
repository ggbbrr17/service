from flask import Flask, request, jsonify, render_template_string
import json
import subprocess
import os
import pyautogui
import time
import re
from datetime import datetime
import uuid
import sys

app = Flask(__name__)

MEMORY_FILE = "memory.json"
LOG_FILE = "logs.txt"

# ---------------- SAFETY / CONFIG ----------------
# acciones permitidas
WHITELIST = {"open_notepad", "open_browser", "search", "press", "wait", "click_at", "hotkey", "close_agent"}
# acciones que requieren confirmación humana
DANGEROUS_ACTIONS = set()
# pending plans waiting confirmation: id -> {steps, question, created}
PENDING = {}

# ---------------- MEMORY ----------------
def load_memory():
    try:
        with open(MEMORY_FILE, "r") as f:
            return json.load(f)
    except:
        return {"datos": {}, "reglas_aprendidas": [], "plans": []}

def save_memory(data):
    with open(MEMORY_FILE, "w") as f:
        json.dump(data, f, indent=2)


def remember_plan(question, plan):
    mem = load_memory()
    plans = mem.get("plans", [])
    entry = {
        "id": str(uuid.uuid4()),
        "created": str(datetime.now()),
        "question": question,
        "plan": plan
    }
    plans.append(entry)
    # keep bounded memory
    MAX_PLANS = 200
    if len(plans) > MAX_PLANS:
        plans = plans[-MAX_PLANS:]
    mem["plans"] = plans
    save_memory(mem)
    log(f"remember_plan saved id={entry['id']} question={question}")
    return entry["id"]

# ---------------- LOGS ----------------
def log(text):
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now()}] {text}\n")
    except Exception as e:
        # fallback: print to stderr if log file cannot be written
        try:
            sys.stderr.write(f"[{datetime.now()}] {text} (log error: {e})\n")
        except Exception:
            pass

# ---------------- MODEL ----------------
def ask_model(prompt):
    models = ["tinyllama", "tinyllama-pro"]
    for model in models:
        try:
            proc = subprocess.run(
                ["ollama", "run", model],
                input=prompt.encode("utf-8"),
                text=False,
                capture_output=True,
                timeout=30
            )
            if proc.returncode != 0:
                continue

            out_bytes = proc.stdout if isinstance(proc.stdout, bytes) else proc.stdout.encode("utf-8", errors="replace")
            # intentar decodificar como utf-8, si falla intentar cp1252 (Windows)
            try:
                out = out_bytes.decode("utf-8")
                used_enc = "utf-8"
            except Exception:
                try:
                    out = out_bytes.decode("cp1252")
                    used_enc = "cp1252"
                except Exception:
                    out = out_bytes.decode("utf-8", errors="replace")
                    used_enc = "utf-8-replace"

            log(f"ask_model used {model} decoded as {used_enc}")
            return out
        except Exception as e:
            log(f"ask_model error for {model}: {e}")
    return ""

# ---------------- PLANNER ----------------
def planner(question):
    prompt = f"""<|system|>
Eres Glyph, un asistente para Windows con MEMORIA CONTINUA.
REGLA: Responde SIEMPRE en ESPAÑOL y SOLO con JSON.

Estructura:
{{
  "razonamiento": "pensamiento interno",
  "message": "respuesta al usuario",
  "steps": [],
  "learn": "dato o regla para recordar"
}}

Acciones: open_notepad, open_browser, search, run_app, close_agent.

<|user|>
{question}
<|assistant|>"""
    return ask_model(prompt)

# ---------------- SAFE PARSER ----------------
def safe_parse(text):

    try:
        return json.loads(text)
    except:
        pass

    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except:
            pass

    text = text.lower()

    if "notepad" in text:
        return {"steps": [{"action": "open_notepad"}]}

    if "browser" in text or "chrome" in text or "google" in text:
        return {"steps": [{"action": "open_browser"}]}

    if "cerrar" in text or "salir" in text:
        return {"steps": [{"action": "close_agent"}]}

    return {"steps": []}


def normalize_steps(steps):
    """Normalize and repair steps returned by model.

    Fix common misspellings and convert simple strings into step dicts.
    """
    repaired = []
    mapping = {
        'searc': 'search',
        'seach': 'search',
        'searchh': 'search',
        'openbrowser': 'open_browser',
        'open-browser': 'open_browser',
        'open_notepad': 'open_notepad',
        'opennotepad': 'open_notepad',
        'selectaccount': 'select_account',
        'select_account': 'select_account'
    }

    for s in (steps or []):
        if not s:
            continue
        if isinstance(s, str):
            key = s.strip().lower()
            a = mapping.get(key, None)
            if a:
                repaired.append({'action': a})
            else:
                # try to infer
                if 'browser' in key or 'google' in key or 'chrome' in key:
                    repaired.append({'action': 'open_browser'})
                elif 'nota' in key or 'notepad' in key:
                    repaired.append({'action': 'open_notepad'})
                elif 'buscar' in key or 'search' in key:
                    query = key.replace('search', '').replace('buscar', '').strip()
                    repaired.append({'action': 'search', 'params': {'query': query}})
            continue

        if isinstance(s, dict):
            a = s.get('action') or s.get('act') or s.get('searc') or s.get('seach')
            if isinstance(a, str):
                a_norm = a.strip().lower()
                a_norm = mapping.get(a_norm, a_norm)
            else:
                a_norm = None

            # prefer explicit params field
            params = s.get('params') or s.get('param') or {}
            # fallback if step uses 'query' directly
            if 'query' in s and not params:
                params = {'query': s.get('query')}

            if a_norm:
                repaired.append({'action': a_norm, 'params': params} if params else {'action': a_norm})
            else:
                # if dict contains 'searc' typo
                if 'searc' in s or 'seach' in s:
                    repaired.append({'action': 'search', 'params': {'query': s.get('searc') or s.get('seach') or s.get('query', '')}})
                else:
                    # unknown dict - keep as-is if has action
                    if 'action' in s:
                        repaired.append(s)
    return repaired


def plan_to_concrete_steps(steps):
    """Map high-level model steps into concrete executor steps.

    Input: list of steps like [{"action":"select_account","params":{"which":2}}]
    Output: list of low-level steps the executor understands (open_browser, wait, press, hotkey, search, click_at)
    """
    out = []
    for s in steps:
        a = s.get("action") if isinstance(s, dict) else None
        params = s.get("params") if isinstance(s, dict) else {}

        if a == "open_browser":
            out.append({"action": "open_browser"})
            out.append({"action": "wait", "seconds": 1})

        elif a == "select_account":
            # best-effort: try to navigate account chooser via Tab/Down/Enter
            which = params.get("which") if isinstance(params, dict) else None
            if isinstance(which, int) and which > 1:
                # press tab a couple times then navigate down (heuristic)
                out.append({"action": "wait", "seconds": 1})
                out.append({"action": "press", "key": "tab", "count": 2})
                # move down (which-1) times
                down_count = max(1, which - 1)
                out.append({"action": "press", "key": "down", "count": down_count})
                out.append({"action": "press", "key": "enter", "count": 1})
                out.append({"action": "wait", "seconds": 0.8})
            elif isinstance(which, str):
                # if named account, just wait and try Enter (may be visible)
                out.append({"action": "wait", "seconds": 1})
                out.append({"action": "press", "key": "tab", "count": 2})
                out.append({"action": "press", "key": "enter", "count": 1})
                out.append({"action": "wait", "seconds": 0.8})
            else:
                # default heuristic: try to tab/select once
                out.append({"action": "wait", "seconds": 1})
                out.append({"action": "press", "key": "tab", "count": 2})
                out.append({"action": "press", "key": "enter", "count": 1})
                out.append({"action": "wait", "seconds": 0.8})

        elif a == "search":
            q = params.get("query") if isinstance(params, dict) else None
            if not q:
                # fallback: if step has direct 'query' field
                q = s.get("query")
            out.append({"action": "hotkey", "keys": "ctrl+l"})
            out.append({"action": "wait", "seconds": 0.2})
            out.append({"action": "search", "query": q or ""})

        elif a == "open_notepad":
            out.append({"action": "open_notepad"})

        elif a == "close_agent":
            out.append({"action": "close_agent"})

        else:
            # unknown high-level action; ignore or log
            log(f"plan_to_concrete_steps: unknown action {a}")

    return out

# ---------------- EXECUTOR ----------------
def execute_step(step, dry_run=False):
    action = step.get("action", "")

    if action not in WHITELIST:
        log(f"execute_step forbidden action: {action}")
        return False

    if dry_run:
        log(f"DRY_RUN: would execute {action} with {step}")
        return True

    if action == "open_notepad":
        try:
            os.system("start notepad")
            return True
        except Exception as e:
            log(f"execute_step open_notepad error: {e}")
            return False

    elif action == "close_agent":
        try:
            os._exit(0)
            return True
        except Exception as e:
            log(f"execute_step close_agent error: {e}")
            return False

    elif action == "open_browser":
        try:
            os.system("start chrome")
            return True
        except Exception as e:
            log(f"execute_step open_browser error: {e}")
            return False

    elif action == "search":
        try:
            pyautogui.write(step.get("query", ""))
            pyautogui.press("enter")
            return True
        except Exception as e:
            log(f"execute_step search error: {e}")
            return False

    elif action == "press":
        try:
            key = step.get("key")
            count = int(step.get("count", 1))
            if not key:
                return False
            for _ in range(max(1, count)):
                pyautogui.press(key)
                time.sleep(0.1)
            return True
        except Exception as e:
            log(f"execute_step press error: {e}")
            return False

    elif action == "wait":
        try:
            secs = float(step.get("seconds", 0.5))
            time.sleep(max(0, secs))
            return True
        except Exception as e:
            log(f"execute_step wait error: {e}")
            return False

    elif action == "click_at":
        try:
            x = int(step.get("x", 0))
            y = int(step.get("y", 0))
            pyautogui.click(x, y)
            return True
        except Exception as e:
            log(f"execute_step click_at error: {e}")
            return False

    elif action == "hotkey":
        try:
            keys = step.get("keys")
            if not keys:
                return False
            # allow either list or "ctrl+l" style string
            if isinstance(keys, str):
                if "+" in keys:
                    parts = [k.strip() for k in keys.split("+")]
                else:
                    parts = [keys]
            else:
                parts = list(keys)
            pyautogui.hotkey(*parts)
            return True
        except Exception as e:
            log(f"execute_step hotkey error: {e}")
            return False

    return False

# ---------------- API ----------------
@app.route("/ask", methods=["POST"])
def ask():
    data = request.get_json(force=True)
    question = data.get("question", "")
    dry_run = bool(data.get("dry_run", False))
    auto_confirm = bool(data.get("auto_confirm", False))

    log(f"QUESTION: {question}")

    # Primero, pedir al modelo que devuelva un plan en JSON
    plan_text = planner(question)
    log(f"MODEL_PLAN: {plan_text}")
    plan = safe_parse(plan_text)
    steps = plan.get("steps", []) if isinstance(plan, dict) else []
    # try to repair/normalize model steps
    steps = normalize_steps(steps)
    # convert high-level plan from the model into concrete executor steps
    concrete_steps = plan_to_concrete_steps(steps)

    # If model failed to produce a useful plan, use semantic fallback for account selection
    if not concrete_steps:
        ql = question.lower()
        if 'cuenta' in ql or 'account' in ql or 'gabriel' in ql:
            # attempt best-effort plan: open browser, select 2nd account, search query
            # try to extract search query from question
            import re as _re
            m = _re.search(r"escribe\s+([\wñáéíóú ]+)", ql)
            query = None
            if m:
                query = m.group(1).strip()
            else:
                # look for 'escribe gemini' or 'buscar gemini'
                if 'gemini' in ql:
                    query = 'gemini'

            concrete_steps = []
            concrete_steps.append({'action': 'open_browser'})
            concrete_steps.append({'action': 'wait', 'seconds': 1})
            concrete_steps.append({'action': 'press', 'key': 'tab', 'count': 2})
            concrete_steps.append({'action': 'press', 'key': 'down', 'count': 1})
            concrete_steps.append({'action': 'press', 'key': 'enter', 'count': 1})
            concrete_steps.append({'action': 'wait', 'seconds': 0.8})
            concrete_steps.append({'action': 'hotkey', 'keys': 'ctrl+l'})
            concrete_steps.append({'action': 'wait', 'seconds': 0.2})
            concrete_steps.append({'action': 'search', 'query': query or 'gemini'})

    if steps:
        # si alguna acción requiere confirmación y no hay auto_confirm -> crear pending
        requires_confirmation = any(s.get("action") in DANGEROUS_ACTIONS for s in steps)
        if requires_confirmation and not auto_confirm:
            pid = str(uuid.uuid4())
            PENDING[pid] = {"steps": steps, "question": question, "created": str(datetime.now())}
            log(f"PENDING created {pid} for question: {question}")
            return jsonify({"response": "Requiere confirmación humana", "pending_id": pid, "model_output": plan_text})
        # execute the concrete steps derived from model plan
        results = []
        for step in concrete_steps:
            ok = execute_step(step, dry_run=dry_run)
            results.append({"action": step.get("action"), "ok": ok})
        return jsonify({"response": "Ejecutando pasos", "results": results, "model_output": plan_text})

    # Si el modelo no dio pasos pero dio una respuesta amigable (ej: "Hola")
    if plan_text and not plan_text.strip().startswith('{'):
        return jsonify({"response": plan_text.strip(), "model_output": plan_text})

    # Si el modelo no propone pasos, usar detector por palabras clave
    q_lower = question.lower()
    if "bloc de notas" in q_lower or "notepad" in q_lower or "abre bloc de notas" in q_lower:
        execute_step({"action": "open_notepad"})
        return jsonify({"response": "Abriendo bloc de notas"})

    if "navegador" in q_lower or "chrome" in q_lower or "google" in q_lower:
        execute_step({"action": "open_browser"})
        return jsonify({"response": "Abriendo navegador"})

    if "busca" in q_lower:
        query = q_lower.replace("busca", "").strip()
        ok = execute_step({"action": "search", "query": query})
        return jsonify({"response": f"Buscando {query}", "ok": ok})

    return jsonify({"response": "No entendí la acción"})


@app.route("/confirm", methods=["POST"])
def confirm():
    data = request.get_json(force=True)
    pid = data.get("pending_id")
    if not pid or pid not in PENDING:
        return jsonify({"status": "error", "reason": "pending_id not found"}), 404

    entry = PENDING.pop(pid)
    steps = entry.get("steps", [])
    results = []
    for step in steps:
        ok = execute_step(step, dry_run=False)
        results.append({"action": step.get("action"), "ok": ok})

    return jsonify({"status": "executed", "results": results})


@app.route("/pending", methods=["GET"])
def pending_list():
    # return summary of pending plans
    out = []
    for pid, entry in PENDING.items():
        out.append({
            "pending_id": pid,
            "question": entry.get("question"),
            "created": entry.get("created"),
            "steps": entry.get("steps")
        })
    return jsonify({"pending": out})


@app.route("/pending/accept", methods=["POST"])
def pending_accept():
    data = request.get_json(force=True)
    pid = data.get("pending_id")
    execute = bool(data.get("execute", True))
    dry_run = bool(data.get("dry_run", False))
    learn = bool(data.get("learn", False))

    if not pid or pid not in PENDING:
        return jsonify({"status": "error", "reason": "pending_id not found"}), 404

    entry = PENDING.pop(pid)
    steps = entry.get("steps", [])
    q = entry.get("question")

    results = []
    if execute:
        for step in steps:
            ok = execute_step(step, dry_run=dry_run)
            results.append({"action": step.get("action"), "ok": ok})

    if learn:
        remember_plan(q, steps)

    return jsonify({"status": "accepted", "results": results})


@app.route("/pending/reject", methods=["POST"])
def pending_reject():
    data = request.get_json(force=True)
    pid = data.get("pending_id")
    if not pid or pid not in PENDING:
        return jsonify({"status": "error", "reason": "pending_id not found"}), 404
    PENDING.pop(pid)
    return jsonify({"status": "rejected", "pending_id": pid})


@app.route('/ui', methods=['GET'])
def ui():
    html = '''<!doctype html>
<html>
<head>
    <meta charset="utf-8">
    <title>Glyph - Pending Plans</title>
    <style>body{font-family:Arial,Helvetica,sans-serif;padding:18px} .card{border:1px solid #ddd;padding:10px;margin:8px;border-radius:6px}</style>
</head>
<body>
    <h2>Glyph - Pending Plans</h2>
    <div style="margin-bottom:12px;border:1px solid #eee;padding:10px;border-radius:6px">
        <h3>Enviar comando</h3>
        <input id="question" placeholder="Describe lo que quieres que haga (ej: abre el navegador y escribe gemini)" style="width:70%" />
        <label style="margin-left:8px"><input type="checkbox" id="dry"> dry-run</label>
        <button onclick="sendQuestion()" style="margin-left:8px">Enviar</button>
        <div id="ask_result" style="margin-top:8px;color:green"></div>
    </div>
    <div>
        <button onclick="loadPending()">Refrescar</button>
    </div>
    <div id="list"></div>

    <script>
    async function loadPending(){
        const res = await fetch('/pending');
        const j = await res.json();
        const list = document.getElementById('list');
        list.innerHTML = '';
        (j.pending||[]).forEach(function(p){
            const el = document.createElement('div'); el.className='card';
            el.innerHTML = '<b>id:</b> '+p.pending_id+'<br><b>question:</b> '+p.question+'<br><b>steps:</b> <pre>'+JSON.stringify(p.steps,null,2)+'</pre>';
            const acceptBtn = document.createElement('button'); acceptBtn.textContent='Aceptar & Ejecutar';
            acceptBtn.onclick = function(){accept(p.pending_id,false,false)};
            const acceptDryBtn = document.createElement('button'); acceptDryBtn.textContent='Aceptar (dry-run)'; acceptDryBtn.style.marginLeft='6px';
            acceptDryBtn.onclick = function(){accept(p.pending_id,true,false)};
            const acceptLearnBtn = document.createElement('button'); acceptLearnBtn.textContent='Aceptar y Aprender'; acceptLearnBtn.style.marginLeft='6px';
            acceptLearnBtn.onclick = function(){accept(p.pending_id,false,true)};
            const rejectBtn = document.createElement('button'); rejectBtn.textContent='Rechazar'; rejectBtn.style.marginLeft='6px';
            rejectBtn.onclick = function(){reject(p.pending_id)};
            el.appendChild(document.createElement('br'));
            el.appendChild(acceptBtn); el.appendChild(acceptDryBtn); el.appendChild(acceptLearnBtn); el.appendChild(rejectBtn);
            list.appendChild(el);
        });
    }

    async function sendQuestion(){
        const q = document.getElementById('question').value;
        const dry = document.getElementById('dry').checked;
        if(!q) { alert('Escribe una pregunta'); return; }
        const res = await fetch('/ask',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({question:q,dry_run:dry})});
        const j = await res.json();
        const el = document.getElementById('ask_result');
        el.textContent = JSON.stringify(j);
        if(j.pending_id){ el.innerHTML += `<br><a href="/ui">Ir a pendientes</a>` }
        loadPending();
    }

    async function accept(id,dry,learn){
        const body = {pending_id:id, execute:true, dry_run:dry, learn:learn};
        const res = await fetch('/pending/accept',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
        const j = await res.json();
        alert('Respuesta: '+JSON.stringify(j));
        loadPending();
    }

    async function reject(id){
        const res = await fetch('/pending/reject',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({pending_id:id})});
        const j = await res.json();
        alert('Rechazado: '+JSON.stringify(j));
        loadPending();
    }

    loadPending();
    </script>
</body>
</html>'''
    return render_template_string(html)

# ---------------- MEMORY API ----------------
@app.route("/remember", methods=["POST"])
def remember():
    data = request.json
    key = data.get("key")
    value = data.get("value")

    memory = load_memory()
    memory[key] = value
    save_memory(memory)

    return jsonify({"status": "guardado"})


@app.route("/learn", methods=["POST"])
def learn():
    data = request.get_json(force=True)
    # can provide pending_id, or question+plan directly
    pending_id = data.get("pending_id")
    auto = bool(data.get("auto", False))

    if pending_id:
        if pending_id not in PENDING:
            return jsonify({"status": "error", "reason": "pending_id not found"}), 404
        entry = PENDING.pop(pending_id)
        q = entry.get("question")
        plan = entry.get("steps")
        pid = remember_plan(q, plan)
        return jsonify({"status": "saved", "id": pid})

    question = data.get("question")
    plan = data.get("plan")
    if not question or not plan:
        return jsonify({"status": "error", "reason": "question and plan required"}), 400

    if not auto:
        # require explicit confirm param for safety
        confirm = bool(data.get("confirm", False))
        if not confirm:
            return jsonify({"status": "confirm_required"})

    pid = remember_plan(question, plan)
    return jsonify({"status": "saved", "id": pid})


@app.route("/forget", methods=["POST"])
def forget():
    data = request.get_json(force=True)
    pid = data.get("id")
    if not pid:
        return jsonify({"status": "error", "reason": "id required"}), 400
    mem = load_memory()
    plans = mem.get("plans", [])
    new_plans = [p for p in plans if p.get("id") != pid]
    if len(new_plans) == len(plans):
        return jsonify({"status": "error", "reason": "id not found"}), 404
    mem["plans"] = new_plans
    save_memory(mem)
    return jsonify({"status": "forgotten", "id": pid})

@app.route("/memory", methods=["GET"])
def memory():
    return jsonify(load_memory())


@app.route("/exec", methods=["POST"])
def exec_plan():
    data = request.get_json(force=True)
    steps = data.get("steps", [])
    dry_run = bool(data.get("dry_run", False))
    learn = bool(data.get("learn", False))
    question = data.get("question", "manual_exec")

    results = []
    for step in steps:
        ok = execute_step(step, dry_run=dry_run)
        results.append({"action": step.get("action"), "ok": ok})

    if learn:
        remember_plan(question, steps)

    return jsonify({"status": "executed", "results": results})

# ---------------- START ----------------
# File moved to old/glyph_server.py
if __name__ == "__main__":
    app.run(port=5000)