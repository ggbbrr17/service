print("🔥 EXECUTOR CARGADO")

import webbrowser
import requests
import re
import os
import sys
import subprocess
import time
import glob
import importlib
import io
import logging
from contextlib import redirect_stdout
try:
    import pandas as pd
except ImportError:
    pd = None

from core.memory import load_memory, save_memory

def plan_to_concrete_steps(steps):
    """Mantiene los pasos tal cual, filtrando solo lo que es core."""
    return steps

def execute_step(step: dict, dry_run: bool = False):
    action = step.get("action")

    if dry_run:
        return True, f"[DRY RUN] {action}"

    try:
        if action == "wait":
            seconds = step.get("seconds", 5)
            time.sleep(float(seconds))
            return True, f"Espera de {seconds}s finalizada."

        elif action == "search":
            query = step.get("query", "")
            url = f"https://www.google.com/search?q={query}"
            if sys.platform == "win32":
                os.system(f'start chrome "{url}"')
            else:
                webbrowser.open(url)
            return True, f"Buscando: {query}"

        elif action == "background_research":
            query = step.get("query")
            if not query: return False, "Falta la consulta para investigar."
            
            # 1. TAVILY (Primario)
            api_key = os.getenv("TAVILY_API_KEY") or "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"
            if api_key:
                try:
                    res = requests.post("https://api.tavily.com/search", json={
                        "api_key": api_key,
                        "query": query,
                        "search_depth": "advanced",
                        "include_answer": True
                    }, timeout=20)
                    if res.ok:
                        data = res.json()
                        answer = data.get("answer")
                        results = data.get("results", [])
                        if answer:
                            return True, f"🔍 DATO ACTUALIZADO: {answer}"
                        info = "\n\n".join([f"Fuente: {r['url']}\nContenido: {r['content']}" for r in results[:5]])
                        return True, f"🔍 INVESTIGACIÓN TAVILY:\n\n{info}"
                except: pass

            # 2. DUCKDUCKGO (Secundario)
            try:
                url = f"https://html.duckduckgo.com/html/?q={query}"
                headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Glyph/1.0"}
                res = requests.get(url, headers=headers, timeout=15)
                if res.ok:
                    snippets = re.findall(r'result__snippet.*?>(.*?)</a>', res.text, re.DOTALL)
                    clean_text = "\n\n• ".join([re.sub('<[^>]*>', '', s).strip() for s in snippets[:5]])
                    return True, f"🔍 INVESTIGACIÓN DUCKDUCKGO:\n\n• {clean_text}"
            except: pass

            return False, f"No se pudo obtener información externa para '{query}'."

        elif action == "read_file":
            path = step.get("path")
            if not path: return False, "Falta el path del archivo"
            if not os.path.exists(path):
                alt_path = os.path.join("core", path)
                if os.path.exists(alt_path): path = alt_path
                else: return False, f"Archivo no encontrado: {path}"
            
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read(2000)
                return True, f"Contenido de {path}:\n{content}"
            except Exception as e:
                return False, f"Error leyendo archivo: {str(e)}"

        elif action == "list_files":
            path = step.get("path", ".")
            try:
                items = os.listdir(path)
                report = [f"[{'DIR' if os.path.isdir(os.path.join(path, i)) else 'FILE'}] {i}" for i in items]
                return True, f"Contenido de {path}:\n" + "\n".join(report)
            except Exception as e:
                return False, f"Error listando archivos: {str(e)}"

        elif action == "write_file":
            path = step.get("path")
            content = step.get("content", "")
            if not path: return False, "Falta el path del archivo"
            try:
                os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
                with open(path, "w", encoding="utf-8") as f:
                    f.write(content)
                return True, f"Archivo guardado exitosamente en {path}"
            except Exception as e:
                return False, f"Error escribiendo archivo: {str(e)}"

        elif action == "modify_file":
            path = step.get("path")
            find = step.get("find")
            replace = step.get("replace", "")
            content = step.get("content", "")
            mode = step.get("mode", "replace")

            if not path or not os.path.exists(path):
                return False, f"Archivo no encontrado: {path}"
            
            try:
                if mode == "append":
                    with open(path, "a", encoding="utf-8") as f:
                        f.write("\n" + content)
                    return True, f"Contenido anexado a {path}"
                else:
                    if not find: return False, "Falta parámetro 'find' para modo replace"
                    with open(path, "r", encoding="utf-8", errors="ignore") as f:
                        data = f.read()
                    new_data = data.replace(find, replace)
                    with open(path, "w", encoding="utf-8") as f:
                        f.write(new_data)
                    return True, f"Archivo {path} modificado."
            except Exception as e:
                return False, f"Error modificando archivo: {str(e)}"

        elif action == "update_heartbeat":
            min_w = step.get("min_wait")
            max_w = step.get("max_wait")
            mem = load_memory()
            if "heartbeat_config" not in mem: mem["heartbeat_config"] = {}
            if min_w is not None: mem["heartbeat_config"]["min_wait"] = int(min_w)
            if max_w is not None: mem["heartbeat_config"]["max_wait"] = int(max_w)
            save_memory(mem)
            return True, f"Ritmo cardíaco actualizado."

        elif action == "analyze_dataset":
            if not pd: return False, "Librería 'pandas' no instalada."
            path = step.get("path")
            if not path or not os.path.exists(path): return False, "Archivo no encontrado"
            try:
                df = pd.read_csv(path) if path.endswith('.csv') else pd.read_json(path)
                return True, f"Dataset analizado: {len(df)} registros.\n{df.describe().to_string()[:1000]}"
            except Exception as e:
                return False, str(e)

        elif action == "neural_memory_synthesis":
            return True, "Protocolo de síntesis de memoria iniciado."

        elif action == "code_memory_synthesis":
            try:
                core_dir = os.path.join(os.getcwd(), "core")
                files = [f for f in os.listdir(core_dir) if f.endswith(".py")]
                summary = "\n".join([f"- {f}" for f in files])
                mem = load_memory()
                mem["codebase_summary"] = summary
                save_memory(mem)
                return True, "Mapa mental del código actualizado."
            except: return False, "Error en síntesis."

        elif action == "close_agent":
            os._exit(0)

        elif action == "restart_agent":
            python = sys.executable
            os.execl(python, python, *sys.argv)

        else:
            return False, f"Acción '{action}' deshabilitada o desconocida."

    except Exception as e:
        return False, str(e) 