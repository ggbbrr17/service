import os

def cleanup_empty_elements(root_path):
    """Recorre el proyecto y elimina archivos de 0 bytes y carpetas vacías."""
    print(f"🧹 Iniciando limpieza profunda en: {root_path}")
    exclude = {'.git', '__pycache__', '.venv', '.vscode', '.idea'}

    # Recorremos de abajo hacia arriba (bottom-up)
    for root, dirs, files in os.walk(root_path, topdown=False):

        # Saltar directorios excluidos
        if any(ex in root for ex in exclude):
            continue

        # 1. Identificar y eliminar archivos vacíos
        for file in files:
            if file == ".gitignore": continue
            file_path = os.path.join(root, file)
            try:
                # Verificamos si el archivo tiene tamaño 0
                if os.path.getsize(file_path) == 0:
                    os.remove(file_path)
                    print(f"🗑️ Archivo vacío eliminado: {file_path}")
            except OSError as e:
                print(f"⚠️ Error al acceder a {file_path}: {e}")

        # 2. Identificar y eliminar carpetas vacías
        for dir_name in dirs:
            dir_path = os.path.join(root, dir_name)
            try:
                # Si la carpeta no tiene archivos ni subcarpetas, se borra
                if not os.listdir(dir_path):
                    os.rmdir(dir_path)
                    print(f"📂 Carpeta vacía eliminada: {dir_path}")
            except OSError as e:
                print(f"⚠️ No se pudo eliminar la carpeta {dir_path}: {e}")

    print("✨ Proceso de limpieza finalizado.")

if __name__ == "__main__":
    # Al estar en glyph/tools/cleanup.py, '..' sube a la raíz 'glyph'
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    cleanup_empty_elements(project_root)
