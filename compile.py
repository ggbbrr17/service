import PyInstaller.__main__
import os
import sys

def build_glyph():
    # Definir rutas base
    entry_point = os.path.join('interfaces', 'gui.py')
    icon_path = os.path.join('interfaces', 'icon.png')
    
    # Parámetros de PyInstaller
    # Usamos ';' como separador en add-data porque estamos en Windows
    params = [
        entry_point,
        '--name=Glyph',
        '--onefile',
        '--noconsole',
        f'--add-data={icon_path};.', # Copia el icono a la raíz del directorio temporal del EXE
        '--paths=.',                 # Añade la raíz al PATH para resolver importaciones de 'core'
        '--clean'
    ]
    
    # Añadir icono al archivo .exe si existe
    if os.path.exists(icon_path):
        params.append(f'--icon={icon_path}')

    print(f"🚀 Compilando Glyph desde {entry_point}...")
    PyInstaller.__main__.run(params)
    print("\n✅ Proceso completado. El ejecutable está en la carpeta 'dist'.")

if __name__ == "__main__":
    build_glyph()