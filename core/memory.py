import json
import os
try:
    import certifi
    ca = certifi.where()
except ImportError:
    ca = None
try:
    from pymongo.mongo_client import MongoClient
    from pymongo.server_api import ServerApi
except ImportError:
    MongoClient = None

# Si estamos en Hugging Face con un Storage Bucket, usamos /data
BASE_PATH = "/data/" if os.path.exists("/data") else ""
MEMORY_FILE = os.path.join(BASE_PATH, "memory.json")

MONGO_URI = os.getenv("MONGO_URI")

def load_memory():
    if MONGO_URI and MongoClient:
        try:
            client = MongoClient(
                MONGO_URI,
                server_api=ServerApi('1'),
                tlsCAFile=ca,
                serverSelectionTimeoutMS=10000,
                connectTimeoutMS=10000,
                tlsAllowInvalidCertificates=True # Refuerzo para redes de nube restrictivas
            )
            db = client['glyph_cloud']
            collection = db['memory_v1']
            data = collection.find_one({"_id": "main_memory"})
            if data:
                content = data.get("content", {})
                # Asegurar estructura mínima
                if "reglas_aprendidas" not in content: content["reglas_aprendidas"] = []
                if "datos" not in content: content["datos"] = {}
                if "last_update_id" not in content: content["last_update_id"] = 0
                return content
            else:
                # Si el documento no existe en la nube, devolvemos la estructura inicial
                print("🆕 Inicializando estructura de memoria en la nube...")
                return {"nombre": "Gabriel", "reglas_aprendidas": [], "datos": {}, "last_update_id": 0}
        except Exception as e:
            print(f"⚠️ Conexión Cloud fallida (usando local): {e}")

    try:
        if not os.path.exists(MEMORY_FILE):
            return {"nombre": "Gabriel", "reglas_aprendidas": [], "datos": {}, "last_update_id": 0}
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {"nombre": "Gabriel", "reglas_aprendidas": [], "datos": {}, "last_update_id": 0}

def save_memory(data: dict):
    if MONGO_URI and MongoClient:
        try:
            client = MongoClient(
                MONGO_URI,
                server_api=ServerApi('1'),
                tlsCAFile=ca,
                serverSelectionTimeoutMS=10000,
                connectTimeoutMS=10000,
                tlsAllowInvalidCertificates=True
            )
            db = client['glyph_cloud']
            collection = db['memory_v1']
            collection.replace_one(
                {"_id": "main_memory"},
                {"_id": "main_memory", "content": data},
                upsert=True
            )
            return
        except Exception as e:
            print(f"⚠️ Error de guardado en Cloud: {e}")

    try:
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[ERROR GUARDANDO MEMORIA] {e}")