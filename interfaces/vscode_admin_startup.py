import subprocess
import sys
import os

def setup_vscode_admin_startup():
    """Crea una tarea programada para iniciar VS Code como administrador al iniciar sesión."""
    task_name = "Glyph_VSCode_Admin_Startup"
    # Comando PowerShell para crear la tarea con privilegios elevados
    # Usamos 'cmd /c start code' para asegurar que se abra correctamente en el entorno de usuario
    ps_command = f"""
    Import-Module ScheduledTasks -ErrorAction SilentlyContinue
    $action = New-ScheduledTaskAction -Execute 'cmd.exe' -Argument '/c start "" code'
    $trigger = New-ScheduledTaskTrigger -AtLogOn
    $principal = New-ScheduledTaskPrincipal -UserId (WhoAmI) -LogonType Interactive -RunLevel Highest
    $settings = $null
    try {{ $settings = New-ScheduledTaskSettings -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -Priority 4 }} catch {{ }}
    if ($settings) {{ Register-ScheduledTask -TaskName "{task_name}" -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force }}
    else {{ Register-ScheduledTask -TaskName "{task_name}" -Action $action -Trigger $trigger -Principal $principal -Force }}
    """
    
    try:
        subprocess.run(["powershell", "-Command", ps_command], check=True, capture_output=True)
        print(f"✅ Éxito: Tarea '{task_name}' creada. VS Code se iniciará como administrador al encender el PC.")
    except subprocess.CalledProcessError as e:
        print(f"❌ Error al crear la tarea: {e.stderr.decode(errors='ignore')}")

if __name__ == "__main__":
    setup_vscode_admin_startup()