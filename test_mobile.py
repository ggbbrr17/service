import requests
import os
import json

# Configuración para pruebas locales
URL = "http://localhost:5000/api/v1/ask"
SECRET = "glyph123" # Cambia esto si usas otra en tus variables de entorno

def run_mobile_simulator():
    print("📱 --- GLYPH MOBILE APP SIMULATOR (VS CODE) ---")
    print(f"📡 Conectando al núcleo en: {URL}")
    print("Escribe 'salir' para terminar.\n")

    while True:
        question = input("👤 Tú: ")
        if question.lower() in ["salir", "exit", "quit"]: break
        
        # Simulamos los headers exactos que enviará el iPhone
        headers = {
            "Content-Type": "application/json",
            "X-Glyph-Secret": SECRET
        }
        payload = {"question": question}
        
        try:
            response = requests.post(URL, json=payload, headers=headers)
            if response.status_code == 200:
                data = response.json()
                print(f"🤖 Glyph: {data.get('message', 'Sin respuesta de texto.')}")
                if data.get("results"):
                    for res in data["results"]:
                        print(f"   ∟ [Acción: {res.get('action')}] Status: {'✅ OK' if res.get('ok') else '❌ Error'}")
            else:
                print(f"❌ Error {response.status_code}: {response.text}")
        except Exception as e:
            print(f"⚠️ Error de enlace: {e}")

if __name__ == "__main__":
    run_mobile_simulator()