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

# Singleton para el cliente de MongoDB para evitar reconexiones lentas
_mongo_client = None

def get_mongo_client():
    global _mongo_client
    if not MONGO_URI or not MongoClient:
        return None
    
    if _mongo_client is None:
        try:
            _mongo_client = MongoClient(
                MONGO_URI,
                server_api=ServerApi('1'),
                tlsCAFile=ca,
                serverSelectionTimeoutMS=5000,
                connectTimeoutMS=5000,
                tlsAllowInvalidCertificates=True
            )
            # Validar conexión
            _mongo_client.admin.command('ping')
        except Exception as e:
            print(f"⚠️ Error inicializando MongoDB: {e}")
            _mongo_client = None
    return _mongo_client

def load_memory():
    client = get_mongo_client()
    if client:
        try:
            db = client['glyph_cloud']
            collection = db['memory_v1']
            data = collection.find_one({"_id": "main_memory"})
            if data:
                content = data.get("content", {})
                if "reglas_aprendidas" not in content: content["reglas_aprendidas"] = []
                if "datos" not in content: content["datos"] = {}
                if "last_update_id" not in content: content["last_update_id"] = 0
                return content
            else:
                print("🆕 Inicializando estructura de memoria en la nube...")
                return {"nombre": "Gabriel", "reglas_aprendidas": [], "datos": {}, "last_update_id": 0}
        except Exception as e:
            print(f"⚠️ Consulta Cloud fallida: {e}")

    try:
        if not os.path.exists(MEMORY_FILE):
            return {"nombre": "Gabriel", "reglas_aprendidas": [], "datos": {}, "last_update_id": 0}
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {"nombre": "Gabriel", "reglas_aprendidas": [], "datos": {}, "last_update_id": 0}

def save_memory(data: dict):
    client = get_mongo_client()
    if client:
        try:
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

def add_notification(message: str, type: str = "info"):
    """Guarda un mensaje para que la App lo recoja proactivamente."""
    import time
    mem = load_memory()
    if "pending_notifications" not in mem:
        mem["pending_notifications"] = []
    
    mem["pending_notifications"].append({
        "timestamp": time.time(),
        "message": message,
        "type": type,
        "id": os.urandom(4).hex()
    })
    # Mantener solo las últimas 20 notificaciones
    mem["pending_notifications"] = mem["pending_notifications"][-20:]
    save_memory(mem)

def get_notifications(clear: bool = True):
    """Obtiene y opcionalmente limpia las notificaciones pendientes."""
    mem = load_memory()
    notifications = mem.get("pending_notifications", [])
    if clear and notifications:
        mem["pending_notifications"] = []
        save_memory(mem)
    return notifications