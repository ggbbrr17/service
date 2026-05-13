"""
Módulo de diccionario Wayuunaiki ↔ Español para el backend de Glyph.
Funciona 100% offline sin dependencias externas.
"""

import json
import os
import re

_DICT_CACHE = {"way_to_esp": {}, "esp_to_way": {}, "loaded": False}

# Glosario médico/nutricional prioritario
MEDICAL_GLOSSARY = {
    "anasü": "salud, estar bien",
    "ayuulii": "enfermedad, estar enfermo",
    "tepichi": "niño",
    "jintüt": "nombre",
    "jintü": "niña",
    "kachon": "edad en meses",
    "nutuma": "peso",
    "nütüjülü": "talla, estatura",
    "eküülü": "comida, alimento",
    "jawata": "fiebre",
    "ayollee": "dolor",
    "asha": "sangre",
    "wüin": "agua",
    "kasachiki": "sal",
    "süchii": "azúcar",
    "katsinshi": "fuerte, sano",
    "aürülaa": "flaco",
    "o'u": "barriga, estómago",
    "muac": "perímetro braquial",
    "apünajaa": "sembrar",
    "wunu'u": "árbol, planta",
    "juya": "lluvia, invierno",
    "wayuu": "persona, gente",
    "pütchi": "palabra, mensaje",
    "ekirajaa": "enseñar, aprender",
    "ekaa": "comer",
    "asaa": "beber",
    "piichi": "casa",
    "ka'i": "sol, día",
    "kashi": "luna, mes",
    "taya": "yo",
    "pia": "tú",
    "wayuunaiki": "idioma wayuu",
}

# Diccionario extendido
BASE_DICT = {
    "aa'in": "corazón, alma", "aalijaa": "ver, mirar", "aapaa": "recibir",
    "achikii": "perro", "achon": "hijo", "ainküin": "querer, amar",
    "ajapü": "boca", "ajattaa": "pensar", "ajünaa": "cocinar",
    "akaliijaa": "ayudar", "akumajaa": "hacer, construir",
    "alaainjaa": "trabajar", "alaülaa": "cacique, jefe",
    "aliikaa": "llorar", "aliina": "muela, diente",
    "alijuna": "persona no wayuu", "amaa": "comprar",
    "anaajaa": "cuidar", "anasü": "bueno, sano",
    "apanai": "hoja", "asalaa": "carne", "ashuku": "huevo",
    "asii": "flor", "atüjaa": "conocer, saber", "atüna": "brazo",
    "ayonnajaa": "dormir", "ee": "sí", "eesü": "hay, existe",
    "ei": "madre", "eirükü": "leche", "ekirajüi": "profesor",
    "ipa": "tierra", "ja'yaa": "caminar", "jayaa": "ir",
    "jootoo": "noche", "joutai": "viento",
    "jülüja aa'in": "precaución", "ka'ruwarai": "estrella",
    "kaasha": "monte, selva", "kaleena": "cabra",
    "kamüshii": "rico, sabroso", "karaloüta": "libro, carta",
    "maiki": "maíz", "maleiwa": "Dios", "masaa": "hambre",
    "miichi": "casa", "mojuü": "malo, feo",
    "nüla": "perro", "oütsü": "médico tradicional",
    "palaa": "mar", "pasiewa": "amigo",
    "pülaa": "grande", "pülashii": "gordo",
    "pütchipü'ü": "vocero, mensajero",
    "süi": "chinchorro, hamaca", "sümaa": "con",
    "süpüla": "para que", "süpüshua": "todo, completo",
    "waima": "mucho, bastante", "wanee": "uno",
    "yoonna": "baile tradicional yonna",
}


def _ensure_loaded():
    """Carga el diccionario combinado (JSON + base + médico)."""
    if _DICT_CACHE["loaded"]:
        return

    way_to_esp = {}
    esp_to_way = {}

    # 1. Intentar cargar JSON extendido
    json_path = os.path.join(os.path.dirname(__file__), "..", "data", "wayuu_dictionary.json")
    if os.path.exists(json_path):
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                for k, v in data.items():
                    way_to_esp[k.lower().strip()] = v.strip()
        except Exception as e:
            print(f"[wayuu] Error cargando JSON: {e}")

    # 2. Diccionario base
    for k, v in BASE_DICT.items():
        way_to_esp[k.lower()] = v

    # 3. Glosario médico (prioridad)
    for k, v in MEDICAL_GLOSSARY.items():
        way_to_esp[k.lower()] = v

    # 4. Construir reverso
    for way, esp in way_to_esp.items():
        main_word = re.sub(r'^(v\.[a-z.]+|n\.|adj\.?|adv\.?)\s*', '', esp, flags=re.I)
        main_word = re.split(r'[,;.(]', main_word)[0].strip().lower()
        if main_word:
            esp_to_way[main_word] = way

    _DICT_CACHE["way_to_esp"] = way_to_esp
    _DICT_CACHE["esp_to_way"] = esp_to_way
    _DICT_CACHE["loaded"] = True
    print(f"[wayuu] Diccionario cargado: {len(way_to_esp)} entradas")


def lookup(word: str) -> dict:
    """Búsqueda bidireccional."""
    _ensure_loaded()
    w = word.lower().strip()
    
    esp = _DICT_CACHE["way_to_esp"].get(w)
    if esp:
        return {"wayuunaiki": word, "español": esp, "direction": "way→esp"}
    
    way = _DICT_CACHE["esp_to_way"].get(w)
    if way:
        return {"wayuunaiki": way, "español": word, "direction": "esp→way"}
    
    return {}


def fuzzy_search(query: str, limit: int = 10) -> list:
    """Búsqueda difusa."""
    _ensure_loaded()
    q = query.lower().strip()
    results = []
    
    for way, esp in _DICT_CACHE["way_to_esp"].items():
        if q in way or q in esp.lower():
            results.append({"wayuunaiki": way, "español": esp})
            if len(results) >= limit:
                break
    
    return results


def translate(text: str) -> str:
    """Traducción automática bidireccional."""
    _ensure_loaded()
    words = text.lower().split()
    
    # Detectar idioma
    way_hits = sum(1 for w in words if w in _DICT_CACHE["way_to_esp"])
    esp_hits = sum(1 for w in words if w in _DICT_CACHE["esp_to_way"])
    
    if way_hits >= esp_hits:
        # Wayuunaiki → Español
        translated = []
        for word in words:
            clean = re.sub(r'[^\w\'áéíóúüñ]', '', word)
            result = _DICT_CACHE["way_to_esp"].get(clean)
            if result:
                main = re.split(r'[,;]', result)[0].strip()
                translated.append(main)
            else:
                translated.append(f"[{clean}]")
        return f"🇪🇸 Español: {' '.join(translated)}"
    else:
        # Español → Wayuunaiki
        translated = []
        for word in words:
            clean = re.sub(r'[^\wáéíóúüñ]', '', word)
            result = _DICT_CACHE["esp_to_way"].get(clean)
            if result:
                translated.append(result)
            else:
                # Buscar en definiciones
                found = None
                for way, esp in _DICT_CACHE["way_to_esp"].items():
                    if clean in esp.lower():
                        found = way
                        break
                translated.append(found or f"[{clean}]")
        return f"🌵 Wayuunaiki: {' '.join(translated)}"


def get_medical_glossary_text() -> str:
    """Devuelve el glosario médico formateado."""
    lines = ["📋 GLOSARIO MÉDICO WAYUUNAIKI", "━" * 30]
    for way, esp in MEDICAL_GLOSSARY.items():
        lines.append(f"  {way}  →  {esp}")
    return "\n".join(lines)


def get_full_dictionary_json() -> str:
    """Devuelve el diccionario completo en formato JSON para el modelo."""
    _ensure_loaded()
    return json.dumps(_DICT_CACHE["way_to_esp"], ensure_ascii=False, indent=2)

