import subprocess
import json
import re
import time
import os
import math
import shutil
import ctypes
import threading
import sys
import tkinter as tk
from datetime import datetime
import urllib.request
import urllib.parse
import webbrowser
from tkinter import scrolledtext, messagebox
import pyautogui

pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0.02

MEMORY_FILE = os.path.join(os.path.dirname(__file__), "memory.json")

def load_memory():
    if os.path.exists(MEMORY_FILE):
        try:
            with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except: pass
    return {"datos": {}, "reglas_aprendidas": []}

def save_memory(data):
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def ensure_ollama(model="tinyllama"):
    """Asegura que Ollama esté corriendo y el modelo cargado al iniciar."""
    try:
        urllib.request.urlopen("http://127.0.0.1:11434", timeout=2)
    except:
        # Intenta iniciar el servidor de Ollama si no responde
        subprocess.Popen("ollama serve", shell=True, creationflags=subprocess.CREATE_NEW_CONSOLE)
        time.sleep(5) 
    
    # Precarga el modelo enviando una petición vacía
    try:
        url = "http://127.0.0.1:11434/api/generate"
        data = json.dumps({"model": model, "prompt": " ", "stream": False}).encode()
        urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=5)
    except: pass

def ask_model(prompt, models=("tinyllama", "tinyllama-pro"), timeout=30):
    for model in models:
        try:
            # Llamada directa a la API para evitar el retardo de inicio de proceso
            url = "http://127.0.0.1:11434/api/generate"
            payload = {
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "num_predict": 256, # Aumentado para permitir razonamiento completo
                    "temperature": 0.0  # Respuesta más directa y rápida
                }
            }
            req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'))
            with urllib.request.urlopen(req, timeout=timeout) as response:
                res_data = json.loads(response.read().decode('utf-8'))
                return res_data.get("response", "")
        except Exception as e:
            return f"ERROR_CONNECTION: {str(e)}"
    return ""

def planner(question, history="", context=""):
    # Prompt con ejemplo (Few-Shot) para obligar al modelo a seguir el formato
    prompt = f"""<|system|>
Eres Glyph, un asistente inteligente para Windows con MEMORIA CONTINUA.
REGLAS:
1. Responde SIEMPRE en ESPAÑOL.
2. Tu salida debe ser ÚNICAMENTE un objeto JSON.
3. Usa el campo "learn" para guardar datos nuevos o reglas de auto-mejora.

CONTEXTO DE MEMORIA:
{context}

HISTORIAL RECIENTE:
{history}

Acciones: open_notepad(), open_browser(), search(query), run_app(name), type_text(text), close_agent().

Ejemplos:
User: hola como estas
Assistant: {{"razonamiento": "Reviso mi estado interno.", "message": "¡Hola! Mis sistemas están en armonía y mi memoria está lista. ¿Qué haremos hoy?", "steps": [], "learn": "El usuario prefiere saludos enérgicos."}}

User: abre el bloc de notas
Assistant: {{"razonamiento": "Petición de notepad.", "message": "Abriendo el Bloc de notas.", "steps": [{{"action": "open_notepad"}}]}}

<|user|>
{question}
<|assistant|>"""
    return ask_model(prompt)

def safe_parse(text, question=""):
    try:
        parsed_json = json.loads(text)
        if isinstance(parsed_json, list) and parsed_json and isinstance(parsed_json[0], dict):
            return parsed_json[0]
        elif isinstance(parsed_json, dict):
            return parsed_json
    except json.JSONDecodeError:
        pass

    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m: # If a JSON-like string is found
        try:
            extracted_json = json.loads(m.group())
            if isinstance(extracted_json, list) and extracted_json and isinstance(extracted_json[0], dict):
                return extracted_json[0]
            elif isinstance(extracted_json, dict):
                return extracted_json
        except json.JSONDecodeError:
            pass

    text_lower = text.lower()
    q_lower = question.lower()
    if ("notepad" in q_lower or "bloc" in q_lower) and "abre" in q_lower:
        return {"steps":[{"action":"open_notepad"}]}
    if "browser" in q_lower or "chrome" in q_lower or "google" in q_lower:
        return {"steps":[{"action":"open_browser"}]}
    if "cerrar" in q_lower or "salir" in q_lower or "terminar" in q_lower:
        return {"steps":[{"action":"close_agent"}]}
    return {"steps":[]}

def normalize_steps(steps):
    mapping = {
        'searc': 'search','seach':'search','openbrowser':'open_browser','open-notepad':'open_notepad'
        ,'runapp': 'run_app', 'explore': 'explore_path', 'rename': 'rename_path',
        'move': 'move_path', 'type': 'type_text', 'write': 'type_text'
    }
    repaired = []
    for s in (steps or []):
        if isinstance(s, str):
            k = s.strip().lower()
            a = mapping.get(k, None)
            if a:
                repaired.append({'action': a})
            elif 'buscar' in k or 'search' in k or 'google' in k:
                query = k.replace('search', '').replace('buscar', '').strip()
                repaired.append({'action':'search','params':{'query': query}})
            continue
        if isinstance(s, dict):
            a = s.get('action') or s.get('act')
            if isinstance(a, str):
                a = mapping.get(a.strip().lower(), a.strip().lower())
            params = s.get('params') or {}
            if 'query' in s and not params:
                params = {'query': s.get('query')}
            if a:
                repaired.append({'action': a, 'params': params} if params else {'action': a})
    return repaired

def plan_to_concrete_steps(steps):
    out = []
    for s in steps:
        a = s.get('action') if isinstance(s, dict) else None
        params = s.get('params') if isinstance(s, dict) else {}
        if a == 'open_browser':
            out.append({'action':'open_browser'})
            out.append({'action':'wait','seconds':5})
        elif a == 'select_account':
            which = params.get('which')
            out.append({'action':'wait','seconds':1})
            out.append({'action':'press','key':'tab','count':2})
            if isinstance(which,int) and which>1:
                out.append({'action':'press','key':'down','count':which-1})
            out.append({'action':'press','key':'enter','count':1})
            out.append({'action':'wait','seconds':0.8})
        elif a == 'search':
            q = params.get('query') if isinstance(params,dict) else None
            out.append({'action':'search','query': q or ''})
        elif a == 'open_notepad':
            out.append({'action':'open_notepad'})
        elif a == 'close_agent':
            out.append({'action':'close_agent'})
        elif a == 'run_app':
            out.append({'action':'run_app', 'name': params.get('name')})
        elif a == 'explore_path':
            out.append({'action':'explore_path', 'path': params.get('path', '.')})
        elif a == 'move_path' or a == 'rename_path':
            out.append({'action':'move_path', 'src': params.get('src') or params.get('old'), 'dst': params.get('dst') or params.get('new')})
        elif a == 'type_text':
            out.append({'action':'type_text', 'text': params.get('text', '')})
        else:
            pass
    return out

WHITELIST = {
    "open_notepad", "open_browser", "search", "press", "wait", 
    "click_at", "hotkey", "run_app", "explore_path", "move_path", "type_text", "close_agent"
}

def execute_step(step, dry_run=False):
    action = step.get('action','')
    if action not in WHITELIST:
        return False, f"forbidden {action}"
    if dry_run:
        return True, f"DRY_RUN {action}"
    try:
        if action == 'open_notepad':
            os.system('start notepad')
            return True, 'opened notepad'
        if action == 'open_browser':
            os.system('start chrome')
            return True, 'opened browser'
        if action == 'close_agent':
            os._exit(0)
            return True, 'closing'
        if action == 'run_app':
            name = step.get('name', '')
            os.system(f'start {name}')
            return True, f'running app {name}'
        if action == 'explore_path':
            path = step.get('path', '.')
            os.system(f'explorer "{path}"')
            return True, f'exploring {path}'
        if action == 'move_path':
            src = step.get('src')
            dst = step.get('dst')
            if src and dst and os.path.exists(src):
                shutil.move(src, dst)
                return True, f'moved {src} to {dst}'
            return False, f'failed to move {src}'
        if action == 'type_text':
            txt = step.get('text', '')
            pyautogui.write(txt, interval=0.05)
            return True, f'typed text'
        if action == 'search':
            q = step.get('query','')
            url = f"https://www.google.com/search?q={urllib.parse.quote(q)}"
            webbrowser.open(url)
            return True, f'opened search for: {q}'
        if action == 'press':
            key = step.get('key')
            cnt = int(step.get('count',1))
            for _ in range(max(1,cnt)):
                pyautogui.press(key)
                time.sleep(0.1)
            return True, f'pressed {key} x{cnt}'
        if action == 'wait':
            secs = float(step.get('seconds',0.5))
            time.sleep(max(0,secs))
            return True, f'waited {secs}s'
        if action == 'hotkey':
            keys = step.get('keys')
            if isinstance(keys,str) and '+' in keys:
                parts = [k.strip() for k in keys.split('+')]
            elif isinstance(keys,str):
                parts = [keys]
            else:
                parts = list(keys)
            pyautogui.hotkey(*parts)
            return True, f'hotkey {parts}'
        if action == 'click_at':
            x = int(step.get('x',0)); y = int(step.get('y',0))
            pyautogui.click(x,y)
            return True, f'clicked {x},{y}'
    except Exception as e:
        return False, str(e)
    return False, 'unknown'

class CustomBallScrollbar(tk.Canvas):
    """Barra de desplazamiento personalizada con una 'bolita verde'."""
    def __init__(self, parent, target, **kwargs):
        tk.Canvas.__init__(self, parent, width=12, bg='#121212', highlightthickness=0, **kwargs)
        self.target = target
        # Crear la bolita verde
        self.ball = self.create_oval(2, 0, 10, 8, fill='#00ff00', outline='#00ff00')
        self.bind("<B1-Motion>", self.move_scroll)
        self.target.config(yscrollcommand=self.set_scroll)

    def set_scroll(self, first, last):
        f, l = float(first), float(last)
        height = self.winfo_height()
        if height > 20:
            # Posicionar la bolita según el scroll
            y_pos = f * height
            # Evitar que la bolita se salga por abajo
            y_pos = min(y_pos, height - 10)
            self.coords(self.ball, 2, y_pos, 10, y_pos + 8)

    def move_scroll(self, event):
        height = self.winfo_height()
        if height > 0:
            pos = event.y / height
            self.target.yview_moveto(pos)

class AgentGUI:
    def __init__(self, root):
        self.root = root
        self.root.withdraw()
        
        # Ventana Minimalista y Transparente
        self.root.overrideredirect(True)
        self.root.attributes('-topmost', True)
        
        # Color mágico para transparencia de bordes
        self.trans_color = '#000001' 
        self.root.config(bg=self.trans_color)
        self.root.attributes('-alpha', 0.92)
        self.root.attributes('-transparentcolor', self.trans_color)

        # Variables para mover la ventana sin barra de título
        self._offsetx = 0
        self._offsety = 0

        self.typing_job = None
        self.typing_queue = []
        self.is_typing = False
        self.chat_history = []

        # Cargar icono
        self.app_icon = None
        if hasattr(sys, '_MEIPASS'):
            # Ruta cuando se ejecuta como .exe (PyInstaller)
            icon_path = os.path.join(sys._MEIPASS, 'icon.png')
        else:
            icon_path = os.path.join(os.path.dirname(__file__), 'icon.png')
            
        if os.path.exists(icon_path):
            try:
                self.app_icon = tk.PhotoImage(file=icon_path)
                self.root.iconphoto(True, self.app_icon)
            except Exception as e:
                print(f"No se pudo cargar el icono: {e}")

        # Iniciar Ollama en segundo plano mientras se muestra el splash
        threading.Thread(target=ensure_ollama, daemon=True).start()

        if self.app_icon:
            self.show_splash()
        else:
            self.setup_main_ui()

    def show_splash(self):
        # Crear ventana de splash sin bordes
        splash = tk.Toplevel(self.root)
        splash.overrideredirect(True)
        splash.configure(bg='#121212')
        
        tk.Label(splash, image=self.app_icon, bg='#121212').pack()
        
        # Centrar el splash en la pantalla
        splash.update_idletasks()
        x = (splash.winfo_screenwidth() // 2) - (splash.winfo_width() // 2)
        y = (splash.winfo_screenheight() // 2) - (splash.winfo_height() // 2)
        splash.geometry(f"+{x}+{y}")
        
        # Esperar 3 segundos y luego quitar el splash y mostrar la UI
        self.root.after(3000, lambda: self.finish_splash(splash))

    def finish_splash(self, splash):
        splash.destroy()
        self.setup_main_ui()
        self.root.deiconify()

    def center_window(self, win, w, h, y_offset=0):
        ws = win.winfo_screenwidth()
        hs = win.winfo_screenheight()
        x = (ws/2) - (w/2)
        y = (hs/2) - (h/2) + y_offset
        win.geometry('%dx%d+%d+%d' % (w, h, x, y))

    def setup_main_ui(self):
        self.root.title('Glyph')
        self.center_window(self.root, 720, 80, y_offset=-250)

        # Canvas para dibujar bordes redondeados
        self.bg_canvas = tk.Canvas(self.root, width=720, height=80, bg=self.trans_color, highlightthickness=0)
        self.bg_canvas.pack()
        
        # Dibujar fondo redondeado
        self.draw_rounded_rect(self.bg_canvas, 5, 5, 715, 75, 35, fill='#121212', outline='#000000', width=2)

        # Área de Input (Barra de búsqueda)
        input_frm = tk.Frame(self.root, bg='#121212')
        self.bg_canvas.create_window(360, 40, window=input_frm, width=650)

        self.input = tk.Entry(input_frm, bg='#121212', fg='#00ff00', 
                             insertbackground='#00ff00', borderwidth=0,
                             highlightthickness=0,
                             font=('Segoe UI', 16))
        self.input.pack(side='left', fill='x', expand=True)

        self.loading_canvas = tk.Canvas(input_frm, width=40, height=20, bg='#121212', highlightthickness=0)
        self.loading_canvas.pack(side='right')

        self.exec_var = tk.BooleanVar(value=True)

        # Binds para arrastrar y teclado
        self.bg_canvas.bind('<Button-1>', self.start_move)
        self.bg_canvas.bind('<B1-Motion>', self.do_move)
        self.input.bind('<Return>', lambda e: self.on_send())
        self.root.bind('<Escape>', lambda e: self.close_resp())
        self.input.focus_set()

    def draw_rounded_rect(self, canvas, x1, y1, x2, y2, r, **kwargs):
        points = [x1+r, y1, x1+r, y1, x2-r, y1, x2-r, y1, x2, y1, x2, y1+r, x2, y1+r, x2, y2-r, x2, y2-r, x2, y2, x2-r, y2, x2-r, y2, x1+r, y2, x1+r, y2, x1, y2, x1, y2-r, x1, y2-r, x1, y1+r, x1, y1+r, x1, y1]
        return canvas.create_polygon(points, **kwargs, smooth=True)

    def start_move(self, event):
        self._offsetx = event.x
        self._offsety = event.y

    def do_move(self, event):
        x = self.root.winfo_x() + event.x - self._offsetx
        y = self.root.winfo_y() + event.y - self._offsety
        self.root.geometry(f"+{x}+{y}")

    def close_resp(self, event=None):
        """Detiene cualquier animación de escritura actual."""
        if self.typing_job:
            self.root.after_cancel(self.typing_job)
            self.typing_job = None
        self.typing_queue = []
        self.is_typing = False
        self.input.delete(0, 'end') # Eliminar todo el texto de la barra de entrada

    def show_floating_resp(self, text):
        self.typing_queue.append(text)
        if not self.is_typing:
            self.process_typing_queue()

    def process_typing_queue(self):
        if not self.typing_queue:
            self.is_typing = False
            return
        self.is_typing = True
        full_text = self.typing_queue.pop(0)
        words = full_text.split(' ')
        self.animate_words(words, 1)

    def animate_words(self, words, index):
        if index <= len(words):
            current_display = ' '.join(words[:index])
            self.input.delete(0, 'end')
            self.input.insert(0, current_display)
            self.input.xview_moveto(1) # Asegura que el final del texto sea visible
            self.typing_job = self.root.after(80, self.animate_words, words, index + 1)
        else:
            self.process_typing_queue()

    def log_write(self, text):
        self.show_floating_resp(text)
        print(f"LOG: {text}")

    def on_send(self):
        q = self.input.get().strip()
        if not q:
            return
        self.input.delete(0, 'end')
        self.close_resp()
        self.start_thinking()
        threading.Thread(target=self.handle_request, args=(q,self.exec_var.get()), daemon=True).start()

    def start_thinking(self):
        self.is_thinking = True
        self.anim_pos = 0
        self.animate_thinking()

    def stop_thinking(self):
        self.is_thinking = False
        self.loading_canvas.delete("all")

    def animate_thinking(self):
        if not self.is_thinking: return
        self.loading_canvas.delete("all")
        x = 20 + 15 * math.sin(self.anim_pos)
        self.loading_canvas.create_oval(x-4, 6, x+4, 14, fill='#00ff00', outline="")
        self.anim_pos += 0.2
        self.root.after(50, self.animate_thinking)

    def handle_request(self, question, do_execute):
        # Cargar memoria y preparar contexto
        mem = load_memory()
        context = f"Datos: {json.dumps(mem.get('datos', {}))}\nReglas: {'. '.join(mem.get('reglas_aprendidas', []))}"
        history = "\n".join(self.chat_history[-6:])
        
        plan_text = planner(question, history, context)
        self.stop_thinking()
        
        if "ERROR_CONNECTION" in plan_text:
            self.log_write("Glyph: Error al conectar con Ollama. ¿Está abierto el programa?")
            return

        if not plan_text.strip() or plan_text == "":
            self.log_write("Glyph: (Sin respuesta del modelo. Reintentando...)")
            return

        plan = safe_parse(plan_text, question) or {}

        # Lógica de auto-mejora: Guardar lo aprendido
        aprendizaje = plan.get('learn')
        if aprendizaje:
            mem = load_memory()
            if "reglas_aprendidas" not in mem: mem["reglas_aprendidas"] = []
            mem["reglas_aprendidas"].append(f"[{datetime.now().strftime('%H:%M')}] {aprendizaje}")
            # Mantener solo las últimas 20 reglas
            mem["reglas_aprendidas"] = mem["reglas_aprendidas"][-20:]
            save_memory(mem)

        # Priorizar siempre la respuesta del modelo, usando el texto plano si el JSON falla
        message = plan.get('message') or (plan_text.strip() if not plan.get('steps') else "")

        if message:
            # Guardar en historial para memoria continua
            self.chat_history.append(f"User: {question}")
            self.chat_history.append(f"Glyph: {message}")
            self.log_write(f"Glyph: {message}")
            
        steps = plan.get('steps',[]) if isinstance(plan,dict) else []
        steps = normalize_steps(steps)
        concrete = plan_to_concrete_steps(steps)
        
        if not concrete:
            ql = question.lower()
            if 'calculadora' in ql or 'calculator' in ql:
                concrete = [{'action':'run_app', 'params': {'name': 'calc'}}]
                if not message: # If no message from model, add a default for calculator
                    self.log_write("Glyph: Abriendo calculadora.")
            
            # Si no hay pasos técnicos y no hay mensaje en el JSON, 
            # intentamos mostrar el texto plano si el modelo no generó JSON
            if not steps and not message:
                raw_text = plan_text.strip()
                if raw_text and not raw_text.startswith('{'):
                    self.log_write(f"Glyph: {raw_text}")
                else:
                    self.log_write("Glyph: No estoy seguro de cómo procesar esa solicitud.")

        if concrete:
            # Se indenta este bloque para evitar el IndentationError tras comentar el log_write
            results = []
            for s in concrete:
                ok, msg = execute_step(s, dry_run=not do_execute)
                results.append({'action': s.get('action'), 'ok': ok, 'msg': msg})
                self.log_write(f"-> {s.get('action')}: {ok} - {msg}")

if __name__ == '__main__':
    # Forzar el icono en la barra de tareas de Windows antes de crear la ventana
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('glyph.agent.v1')
    except: pass
    root = tk.Tk()
    app = AgentGUI(root)
    root.mainloop()
