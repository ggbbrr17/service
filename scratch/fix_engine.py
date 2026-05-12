import os

path = 'c:/Users/Gabriel/glyph/core/engine.py'
with open(path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Buscar el final de la función run
# Buscamos la línea que tiene 'return res' o el dict de retorno
for i in range(len(lines)-1, 0, -1):
    if 'return {' in lines[i] or 'res = {' in lines[i]:
        # Encontramos el inicio del bloque de retorno
        start_idx = i
        # Buscar el final del bloque (la línea que tiene '}')
        end_idx = -1
        for j in range(i, len(lines)):
            if '}' in lines[j]:
                end_idx = j
                break
        
        if end_idx != -1:
            # Reemplazar el bloque
            new_lines = lines[:start_idx]
            new_lines.append('    res = {\n')
            new_lines.append('        "question": question,\n')
            new_lines.append('        "metacognition": plan.get("metacognition", ""),\n')
            new_lines.append('        "message": message,\n')
            new_lines.append('        "steps": steps,\n')
            new_lines.append('        "results": results,\n')
            new_lines.append('        "learn": plan.get("learn"),\n')
            new_lines.append('        "suggestions": plan.get("suggestions"),\n')
            new_lines.append('        "active_model": active_model\n')
            new_lines.append('    }\n')
            new_lines.append('\n')
            new_lines.append('    # Extraer comandos remotos para la App (Modo Túnel Inverso)\n')
            new_lines.append('    for r in results:\n')
            new_lines.append('        if r.get("ok") and isinstance(r.get("msg"), str) and "COMANDO_REMOTO:" in r.get("msg"):\n')
            new_lines.append('            msg_parts = r["msg"].replace("COMANDO_REMOTO:", "").strip().split("|")\n')
            new_lines.append('            res["command"] = {\n')
            new_lines.append('                "action": msg_parts[0],\n')
            new_lines.append('                "args": {"mac": msg_parts[1] if len(msg_parts) > 1 and msg_parts[1] != "default" else None}\n')
            new_lines.append('            }\n')
            new_lines.append('            break\n')
            new_lines.append('\n')
            new_lines.append('    return res\n')
            
            with open(path, 'w', encoding='utf-8') as f:
                f.writelines(new_lines)
            print("Fixed!")
            break
else:
    print("Not found")
