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

        elif action == "read_url":
            url = step.get("url")
            if not url: return False, "Falta la URL para leer."
            try:
                headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}
                res = requests.get(url, headers=headers, timeout=15)
                res.raise_for_status()
                # Limpieza básica de HTML para extraer texto útil
                text = re.sub(r'<script.*?>.*?</script>', '', res.text, flags=re.DOTALL)
                text = re.sub(r'<style.*?>.*?</style>', '', text, flags=re.DOTALL)
                text = re.sub(r'<[^>]+>', ' ', text)
                clean_text = " ".join(text.split())
                return True, f"Contenido extraído de {url} (fragmento):\n{clean_text[:3500]}"
            except Exception as e:
                return False, f"Error al leer la URL: {str(e)}"

        elif action == "background_research":
            query = step.get("query")
            if not query: return False, "Falta la consulta para investigar."
            
            # Nota: La investigación ahora ocurre de forma nativa en el cerebro (Grounding)
            return True, f"🔍 INVESTIGACIÓN NATIVA ACTIVADA: El núcleo está procesando datos de Google Search para: {query}"

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
                cols = list(df.columns)
                nulls = df.isnull().sum().sum()
                report = f"Dataset: {os.path.basename(path)} ({len(df)} filas)\n"
                report += f"Columnas: {', '.join(cols[:10])}{'...' if len(cols)>10 else ''}\n"
                report += f"Calidad: {nulls} valores nulos detectados.\n"
                report += f"Resumen Estadístico:\n{df.describe().to_string()[:600]}"
                return True, report
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

        elif action == "run_custom_script":
            script = step.get("script")
            if not script: return False, "Falta el script para ejecutar."
            try:
                # Capturamos la salida del script
                f = io.StringIO()
                with redirect_stdout(f):
                    exec(script, {"os": os, "sys": sys, "requests": requests, "pd": pd, "time": time})
                output = f.getvalue()
                return True, f"Script ejecutado con éxito. Salida:\n{output}"
            except Exception as e:
                return False, f"Error ejecutando script: {str(e)}"

        elif action == "git_sync":
            commit_msg = step.get("message", "Glyph Autonomous Sync")
            try:
                # 0. Verificar si es un repositorio git y obtener rama actual
                if not os.path.exists(".git"):
                    return False, "Error: El directorio actual no es un repositorio Git."
                branch_res = subprocess.run(["git", "branch", "--show-current"], capture_output=True, text=True)
                branch = branch_res.stdout.strip() or "main"

                # 1. Preparar cambios
                subprocess.run(["git", "add", "."], check=True, capture_output=True, text=True)
                # 2. Commit (permitimos que falle si no hay cambios)
                subprocess.run(["git", "commit", "-m", commit_msg], check=False, capture_output=True, text=True)
                # 3. Pull con rebase para evitar conflictos simples
                subprocess.run(["git", "pull", "--rebase", "origin", branch], check=True, capture_output=True, text=True)
                # 4. Push
                res = subprocess.run(["git", "push", "-u", "origin", branch], check=True, capture_output=True, text=True)
                return True, f"Sincronización con GitHub exitosa: {res.stdout}"
            except subprocess.CalledProcessError as e:
                return False, f"Error en Git: {e.stderr}"

        elif action == "check_git_status":
            try:
                if not os.path.exists(".git"): return False, "No es un repositorio Git."
                subprocess.run(["git", "fetch"], check=True, capture_output=True, text=True)
                status = subprocess.run(["git", "status", "-sb"], check=True, capture_output=True, text=True)
                diff = subprocess.run(["git", "diff", "--stat", "origin/main"], check=False, capture_output=True, text=True)
                return True, f"Estado:\n{status.stdout}\nComparación con origin/main:\n{diff.stdout if diff.stdout else 'Totalmente sincronizado.'}"
            except Exception as e:
                return False, f"Error en status: {str(e)}"

        elif action == "update_app_icon":
            new_icon = step.get("path")
            # Si no hay path, buscar el archivo más reciente en assets
            if not new_icon:
                assets_path = step.get("assets_path", "../app-main/app-main/assets")
                if os.path.exists(assets_path):
                    files = glob.glob(os.path.join(assets_path, "*.*"))
                    if files:
                        new_icon = max(files, key=os.path.getmtime)
                        new_icon = os.path.basename(new_icon)
            
            if not new_icon: return False, "No se encontró una imagen para el icono."

            # Intentar encontrar pubspec.yaml basándonos en los paths del contexto
            search_paths = ["../app-main/app-main/pubspec.yaml", "pubspec.yaml", "../../pubspec.yaml"]
            pubspec_path = next((p for p in search_paths if os.path.exists(p)), None)
            
            if not pubspec_path: return False, "No se encontró pubspec.yaml para actualizar el icono."

            try:
                with open(pubspec_path, "r", encoding="utf-8") as f:
                    content = f.read()
                
                # Actualizar el image_path de flutter_launcher_icons usando Regex
                pattern = r'(image_path:\s*["\'])(.*?)(["\'])'
                updated_content = re.sub(pattern, rf'\1assets/{os.path.basename(new_icon)}\3', content)
                
                with open(pubspec_path, "w", encoding="utf-8") as f:
                    f.write(updated_content)
                
                # Ejecutar regeneración (usando la sintaxis del workflow de GitHub)
                project_dir = os.path.dirname(os.path.abspath(pubspec_path))
                subprocess.run(["dart", "run", "flutter_launcher_icons"], cwd=project_dir, check=True, shell=True)
                
                return True, f"Icono de escritorio actualizado a {new_icon} y regenerado."
            except Exception as e:
                return False, f"Error actualizando icono: {str(e)}"

        elif action == "setup_push":
            topic = step.get("topic")
            if not topic:
                import secrets
                topic = f"glyph_gabriel_{secrets.token_hex(4)}"
            mem = load_memory()
            if "datos" not in mem: mem["datos"] = {}
            mem["datos"]["ntfy_topic"] = topic
            save_memory(mem)
            return True, f"Notificaciones Push configuradas. Suscríbete en: https://ntfy.sh/{topic}"

        elif action == "close_agent":
            os._exit(0)

        elif action == "restart_agent":
            python = sys.executable
            os.execl(python, python, *sys.argv)

        else:
            return False, f"Acción '{action}' deshabilitada o desconocida."

    except Exception as e:
        return False, str(e) 