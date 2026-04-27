import json
import os
import math
import ctypes
import threading
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import tkinter as tk
import core.engine

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

        if self.app_icon:
            self.show_splash()
        else:
            self.setup_main_ui()

    def show_splash(self):
        # Crear ventana de splash sin bordes
        splash = tk.Toplevel(self.root)
        splash.overrideredirect(True)

        # Transparencia total del fondo para mostrar solo el PNG
        splash.configure(bg=self.trans_color)
        splash.attributes('-transparentcolor', self.trans_color)
        splash.attributes('-topmost', True)

        tk.Label(splash, image=self.app_icon, bg=self.trans_color).pack()
        
        # Centrar el splash en la pantalla
        splash.update_idletasks()
        w, h = self.app_icon.width(), self.app_icon.height()
        x = (splash.winfo_screenwidth() // 2) - (w // 2)
        y = (splash.winfo_screenheight() // 2) - (h // 2)
        splash.geometry(f"{w}x{h}+{x}+{y}")
        
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
            self.stop_thinking() # Detener animación visual cuando termine el texto
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
            self.typing_job = self.root.after(30, self.animate_words, words, index + 1)
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
        threading.Thread(target=self.handle_request, args=(q, self.exec_var.get()), daemon=True).start()

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
        history = "\n".join(self.chat_history[-6:])
        
        res = core.engine.run(question, dry_run=not do_execute, history=history)
        
        if "error" in res:
            self.log_write(f"Glyph: {res['message']}")
            self.stop_thinking()
            return

        message = res.get('message')
        if message:
            self.chat_history.append(f"User: {question}")
            self.chat_history.append(f"Glyph: {message}")
            self.log_write(f"Glyph: {message}")
            
        for r in res.get('results', []):
            self.log_write(f"-> {r['action']}: {r['ok']} - {r['msg']}")

if __name__ == '__main__':
    # Forzar el icono en la barra de tareas de Windows antes de crear la ventana
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('glyph.agent.v1')
    except: pass
    root = tk.Tk()
    app = AgentGUI(root)
# File moved to old/gui_agent.py
    root.mainloop()
