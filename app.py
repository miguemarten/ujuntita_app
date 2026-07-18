# -*- coding: utf-8 -*-
"""
🕹️ UJuntita - Backend (Flask + SSE)
========================================
Servidor central de la aplicación UJuntita. Gestiona el estado de los jugadores,
el control de la pantalla proyectada (migración de pantallas), los mini-juegos y persiste los datos.
"""

import os
import json
import time
import random
import threading
from flask import Flask, render_template, request, jsonify, Response, redirect, url_for, send_from_directory
from werkzeug.utils import secure_filename

app = Flask(__name__)

# Configuración de carpetas
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "jugadores.json")
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# ──────────────────────────────────────────────
# ⚙️ PRESETS DE CONCEPTOS Y PREGUNTAS (CARGA DESDE JSON)
# ──────────────────────────────────────────────

PRESETS_DIR = os.path.join(BASE_DIR, "presets")
os.makedirs(PRESETS_DIR, exist_ok=True)

def cargar_preset_archivo(nombre_archivo, por_defecto):
    """Carga un archivo preset en formato JSON o escribe el valor por defecto si no existe."""
    ruta = os.path.join(PRESETS_DIR, nombre_archivo)
    if os.path.exists(ruta):
        try:
            with open(ruta, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error cargando preset {nombre_archivo}: {e}")
    try:
        with open(ruta, "w", encoding="utf-8") as f:
            json.dump(por_defecto, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error guardando preset por defecto {nombre_archivo}: {e}")
    return por_defecto

# Presets por defecto (fallbacks)
DEFAULT_CONCEPTOS = [
    {"concepto": "GRACIA", "definicion": "Regalo inmerecido de Dios para la salvación del hombre."},
    {"concepto": "FE", "definicion": "La certeza de lo que se espera, la convicción de lo que no se ve."},
    {"concepto": "REDENCION", "definicion": "Rescatar o librar a alguien pagando un precio o rescate."},
    {"concepto": "DISCIPULO", "definicion": "Aquel que sigue de cerca y aprende las enseñanzas de su maestro."},
    {"concepto": "APOSTOL", "definicion": "Mensajero enviado con una misión o autoridad especial."},
    {"concepto": "PENTATEUCO", "definicion": "Nombre que reciben los primeros cinco libros de la Biblia."},
    {"concepto": "APOCALIPSIS", "definicion": "Último libro del Nuevo Testamento que habla de revelaciones finales."},
    {"concepto": "SANTIDAD", "definicion": "Estado de estar apartado del pecado y consagrado para el servicio de Dios."},
    {"concepto": "PROJIMO", "definicion": "Cualquier ser humano que nos rodea, a quien se nos manda amar."},
    {"concepto": "SALVACION", "definicion": "Liberación de la condenación eterna del pecado por medio de Jesús."}
]

DEFAULT_PREGUNTAS = {
    "verde": [
        "¿Cuál es tu emoji favorito y en qué momento lo usas más?",
        "Si tuvieras que comer una sola comida por el resto de tu vida, ¿cuál sería?",
        "¿Cuál ha sido tu mayor vergüenza o momento gracioso frente a personas?",
        "Si fueras un superhéroe, ¿cuál sería tu debilidad más ridícula?",
        "¿Cuál es la caricatura o dibujo animado de tu infancia que más recuerdas?"
    ],
    "amarillo": [
        "¿Cuál ha sido uno de los días más felices de tu vida y por qué?",
        "Si pudieras viajar en el tiempo a una época específica, ¿a cuál irías?",
        "¿Quién ha sido un amigo o mentor que ha influido positivamente en ti?",
        "¿Qué meta o sueño personal te gustaría cumplir antes del próximo año?",
        "¿Qué es lo que más valoras o aprecias en una amistad sincera?"
    ],
    "rojo": [
        "¿Cómo describirías tu relación actual con Dios en una sola palabra y por qué?",
        "¿Qué versículo de la Biblia te da paz o fuerza en momentos de dificultad?",
        "¿Qué duda o crisis de fe has experimentado y cómo te ayudó a crecer?",
        "¿En qué área de tu vida sientes que Dios está trabajando o moldeándote más?",
        "¿De qué manera práctica crees que puedes mostrar el amor de Jesús a otros esta semana?"
    ]
}

DEFAULT_PROBABLE = [
    "¿Quién es más probable que se quede dormido orando?",
    "¿Quién es más probable que sobreviva a un apocalipsis zombie?",
    "¿Quién es más probable que se pierda yendo al baño de la iglesia?",
    "¿Quién es más probable que se convierta en pastor o misionero en una isla lejana?",
    "¿Quién es más probable que gaste todos sus ahorros en comida o dulces?",
    "¿Quién es más probable que rompa el control jugando un videojuego?",
    "¿Quién es más probable que empiece a reírse a carcajadas en un momento serio?",
    "¿Quién es más probable que olvide dónde deja su teléfono móvil constantemente?"
]

DEFAULT_MEMORICE = {
    "consolas": ["ATARI", "NES", "GENESIS", "GAMEBOY", "SUPER NES", "N64", "PLAYSTATION", "DREAMCAST", "WII"],
    "juegos": ["PACMAN", "TETRIS", "PONG", "DOOM", "ZELDA", "METROID", "GALAGA", "FROGGER", "ASTEROIDS"],
    "comida": ["PIZZA", "BURGER", "HELADO", "DONA", "NUGGETS", "SUSHI", "TACOS", "PALOMITAS", "HOTDOG"],
    "colores": ["ROJO", "AZUL", "VERDE", "CYAN", "MAGENTA", "AMARILLO", "BLANCO", "NEGRO", "NARANJA"]
}


# ──────────────────────────────────────────────
# ⚙️ ESTADO GLOBAL Y PERSISTENCIA
# ──────────────────────────────────────────────

data_lock = threading.Lock()
data_version = 0

# Estado por defecto
estado_juego = {
    "jugadores": [],
    "active_screen": "start",  # start, scoreboard, winner, game_memorice, game_music, game_ahoracaigo, game_ruleta, game_probable
    "score_goal": 50,          # Puntuación máxima para ganar
    
    # Módulo de Memorice de Palabras (Rediseño 3x3 - 9 Casillas)
    "memorice": {
        "words": ["PIXEL", "ARCADE", "CONSOLA", "MONEDA", "RETRO", "8BITS", "NINTENDO", "PACMAN", "ATARI"],
        "order": [0, 1, 2, 3, 4, 5, 6, 7, 8],
        "current_order_index": 0,
        "revealed_indices": [],
        "error_index": -1,
        "players_ids": [],        # IDs de los 3 participantes elegidos
        "active_player_index": 0, # Quién de los 3 está jugando (0, 1 o 2)
        "timer_active": False,
        "timer_start_time": 0,
        "status": "idle"          # idle, memorizing, playing, completed, gameover
    },
    
    # Módulo de la Pista Musical
    "music": {
        "clues": [
            "Reproducir 1 segundo de audio",
            "Pista de Artista / Banda",
            "Letra de la canción (frase corta)",
            "Año de lanzamiento y género",
            "Nombre oculto (modo ahorcado)"
        ],
        "revealed_level": 0,
        "audio_url": ""
    },

    # Módulo Ahora Caigo (Conceptos y Definiciones en Versus 1v1)
    "ahoracaigo": {
        "concept": "GRACIA",
        "definition": "Regalo inmerecido de Dios para la salvación.",
        "displayed_word": "G _ _ C _ _",
        "player_a_id": None,
        "player_b_id": None,
        "active_player_id": None,  # Jugador cuyo cronómetro está activo
        "timer_active": False,
        "timer_start_time": 0,
        "status": "idle",          # idle, playing, correct, timeout
        "points_awarded": 0
    },

    # Módulo Ruleta Rompehielo
    "ruleta": {
        "selected_player_id": None,
        "spin_trigger": 0,
        "question": "¡Gira la ruleta para comenzar!",
        "level": "verde",          # verde, amarillo, rojo
        "points": 10,
        "status": "idle"           # idle, spinning, selected, answered
    },

    # Módulo ¿Quién es más probable que...?
    "probable": {
        "question": "¿Quién es más probable que se quede dormido orando?",
        "winners_ids": []
    }
}

def generar_mascara(word):
    """Genera la máscara con guiones y algunas letras visibles."""
    word = word.strip().upper()
    chars = []
    for idx, char in enumerate(word):
        if char.isspace():
            chars.append(" ")
        elif idx == 0 or idx == len(word) - 1:
            chars.append(char)
        elif idx % 3 == 0:
            chars.append(char)
        else:
            chars.append("_")
    
    # Si por azar o longitud no hay guiones, tapar al menos una letra
    if "_" not in chars and len(word) > 1:
        chars[len(word) // 2] = "_"
    return " ".join(chars)

def cargar_datos():
    """Carga los datos de jugadores.json o crea el archivo por defecto."""
    global estado_juego
    if os.path.exists(DB_PATH):
        with open(DB_PATH, "r", encoding="utf-8") as f:
            try:
                datos = json.load(f)
                # Normalizar campos por si acaso
                if "jugadores" not in datos:
                    datos["jugadores"] = []
                if "active_screen" not in datos:
                    datos["active_screen"] = "start"
                if "score_goal" not in datos:
                    datos["score_goal"] = 50
                
                # Normalizar memorice fields
                m = datos.get("memorice", {})
                for k, v in estado_juego["memorice"].items():
                    if k not in m:
                        m[k] = v
                # Eliminar campo legacy de versión anterior
                m.pop("reveal_trigger", None)
                # Garantizar que siempre haya exactamente 9 palabras
                if not isinstance(m.get("words"), list) or len(m["words"]) != 9:
                    m["words"] = estado_juego["memorice"]["words"]
                    m["order"] = list(range(9))
                    m["status"] = "idle"
                    m["timer_active"] = False
                datos["memorice"] = m

                # Normalizar otros campos recursivamente/profundamente para evitar inconsistencias
                for module in ["music", "ahoracaigo", "ruleta", "probable"]:
                    if module not in datos:
                        datos[module] = estado_juego[module]
                    else:
                        for k, v in estado_juego[module].items():
                            if k not in datos[module]:
                                datos[module][k] = v
                
                estado_juego = datos
            except Exception as e:
                print(f"Error cargando JSON, usando por defecto: {e}")
                guardar_datos()
    else:
        guardar_datos()

def guardar_datos():
    """Guarda el estado del juego actual en jugadores.json."""
    with open(DB_PATH, "w", encoding="utf-8") as f:
        json.dump(estado_juego, f, ensure_ascii=False, indent=2)

def notificar_cambio():
    """Incrementa la versión para que el SSE detecte el cambio."""
    global data_version
    data_version += 1

# Cargar datos al importar
cargar_datos()

# ──────────────────────────────────────────────
# 🌐 VISTAS DE PANTALLAS Y SERVIR ARCHIVOS
# ──────────────────────────────────────────────

@app.route("/")
def home():
    return redirect(url_for("admin"))

@app.route("/admin")
def admin():
    return render_template("admin.html")

@app.route("/proyector")
def proyector():
    return render_template("proyector.html")

@app.route("/uploads/<path:filename>")
def serve_upload(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# ──────────────────────────────────────────────
# 🔌 API REST GENERAL
# ──────────────────────────────────────────────

@app.route("/api/estado", methods=["GET"])
def get_estado():
    with data_lock:
        return jsonify(estado_juego)

@app.route("/api/config", methods=["POST"])
def post_config():
    body = request.get_json(force=True)
    with data_lock:
        if "active_screen" in body:
            screen = body["active_screen"]
            if screen in ["start", "scoreboard", "winner", "game_memorice", "game_music", "game_ahoracaigo", "game_ruleta", "game_probable"]:
                estado_juego["active_screen"] = screen
        if "score_goal" in body:
            try:
                estado_juego["score_goal"] = max(1, int(body["score_goal"]))
            except ValueError:
                pass
        guardar_datos()
        notificar_cambio()
    return jsonify(estado_juego)

@app.route("/api/jugadores", methods=["POST"])
def add_jugador():
    body = request.get_json(force=True)
    nombre = body.get("nombre", "").strip()
    emoji = body.get("emoji", "👾").strip()

    if not nombre:
        return jsonify({"error": "El nombre es obligatorio"}), 400

    with data_lock:
        jugadores = estado_juego["jugadores"]
        next_id = max([j["id"] for j in jugadores]) + 1 if jugadores else 1
        
        nuevo = {
            "id": next_id,
            "nombre": nombre,
            "puntaje_total": 0,
            "emoji": emoji,
            "ultimo_cambio": 0,
            "timestamp_actualizacion": time.time()
        }
        
        jugadores.append(nuevo)
        guardar_datos()
        notificar_cambio()
    
    return jsonify(nuevo), 201

@app.route("/api/jugadores/<int:jid>/puntos", methods=["POST"])
def update_puntos(jid):
    body = request.get_json(force=True)
    puntos_cambio = body.get("puntos", 0)

    try:
        puntos_cambio = int(puntos_cambio)
    except ValueError:
        return jsonify({"error": "Los puntos deben ser un número entero"}), 400

    with data_lock:
        encontrado = None
        for j in estado_juego["jugadores"]:
            if j["id"] == jid:
                j["puntaje_total"] = max(0, j["puntaje_total"] + puntos_cambio)
                j["ultimo_cambio"] = puntos_cambio
                j["timestamp_actualizacion"] = time.time()
                encontrado = j
                break
        
        if not encontrado:
            return jsonify({"error": "Jugador no encontrado"}), 404

        guardar_datos()
        notificar_cambio()
    
    return jsonify(encontrado)

@app.route("/api/jugadores/<int:jid>/emoji", methods=["PUT"])
def update_emoji(jid):
    body = request.get_json(force=True)
    emoji = body.get("emoji", "👾").strip()

    with data_lock:
        encontrado = None
        for j in estado_juego["jugadores"]:
            if j["id"] == jid:
                j["emoji"] = emoji
                encontrado = j
                break
        
        if not encontrado:
            return jsonify({"error": "Jugador no encontrado"}), 404
        
        guardar_datos()
        notificar_cambio()
        
    return jsonify(encontrado)

@app.route("/api/jugadores/<int:jid>", methods=["DELETE"])
def delete_jugador(jid):
    with data_lock:
        original_len = len(estado_juego["jugadores"])
        estado_juego["jugadores"] = [j for j in estado_juego["jugadores"] if j["id"] != jid]
        
        if len(estado_juego["jugadores"]) == original_len:
            return jsonify({"error": "Jugador no encontrado"}), 404
            
        guardar_datos()
        notificar_cambio()
        
    return jsonify({"ok": True})

@app.route("/api/juego/reiniciar", methods=["POST"])
def reiniciar_juego():
    with data_lock:
        for j in estado_juego["jugadores"]:
            j["puntaje_total"] = 0
            j["ultimo_cambio"] = 0
            j["timestamp_actualizacion"] = time.time()
        estado_juego["active_screen"] = "start"
        estado_juego["music"]["revealed_level"] = 0
        estado_juego["ahoracaigo"]["status"] = "idle"
        estado_juego["ahoracaigo"]["timer_active"] = False
        
        # Reiniciar ruleta por completo
        estado_juego["ruleta"]["selected_player_id"] = None
        estado_juego["ruleta"]["spin_trigger"] = 0
        estado_juego["ruleta"]["question"] = "¡Gira la ruleta para comenzar!"
        estado_juego["ruleta"]["level"] = "verde"
        estado_juego["ruleta"]["points"] = 10
        estado_juego["ruleta"]["status"] = "idle"
        
        estado_juego["probable"]["winners_ids"] = []
        estado_juego["memorice"]["status"] = "idle"
        estado_juego["memorice"]["timer_active"] = False
        guardar_datos()
        notificar_cambio()
    return jsonify(estado_juego)

@app.route("/api/juego/limpiar", methods=["POST"])
def limpiar_juego():
    with data_lock:
        estado_juego["jugadores"] = []
        estado_juego["active_screen"] = "start"
        estado_juego["music"]["revealed_level"] = 0
        estado_juego["music"]["audio_url"] = ""
        estado_juego["ahoracaigo"]["status"] = "idle"
        estado_juego["ahoracaigo"]["timer_active"] = False
        
        # Limpiar ruleta por completo
        estado_juego["ruleta"]["selected_player_id"] = None
        estado_juego["ruleta"]["spin_trigger"] = 0
        estado_juego["ruleta"]["question"] = "¡Gira la ruleta para comenzar!"
        estado_juego["ruleta"]["level"] = "verde"
        estado_juego["ruleta"]["points"] = 10
        estado_juego["ruleta"]["status"] = "idle"
        
        estado_juego["probable"]["winners_ids"] = []
        estado_juego["memorice"]["status"] = "idle"
        estado_juego["memorice"]["timer_active"] = False
        guardar_datos()
        notificar_cambio()
    return jsonify(estado_juego)

# ──────────────────────────────────────────────
# 🔌 APIs ESPECÍFICAS DE MINI-JUEGOS
# ──────────────────────────────────────────────

# --- MEMORICE DE PALABRAS (REDISEÑO 3x3) ---

@app.route("/api/juego/memorice/presets", methods=["GET"])
def memorice_get_presets():
    """Retorna las categorías y palabras predefinidas de Memorice."""
    return jsonify(cargar_preset_archivo("memorice.json", DEFAULT_MEMORICE))

@app.route("/api/juego/memorice/config", methods=["POST"])
def memorice_config():
    body = request.get_json(force=True)
    words = body.get("words", [])
    players_ids = body.get("players_ids", [])
    
    if not isinstance(words, list) or len(words) != 9:
        return jsonify({"error": "La lista de palabras debe contener exactamente 9 palabras"}), 400
        
    with data_lock:
        m = estado_juego["memorice"]
        m["words"] = [w.strip().upper() for w in words if w.strip()]
        m["players_ids"] = [int(p) for p in players_ids if p != ""]
        
        # Resetear variables de juego
        m["current_order_index"] = 0
        m["revealed_indices"] = []
        m["error_index"] = -1
        m["active_player_index"] = 0
        m["status"] = "idle"
        m["timer_active"] = False
        
        guardar_datos()
        notificar_cambio()
    return jsonify(estado_juego["memorice"])

@app.route("/api/juego/memorice/iniciar-memorice", methods=["POST"])
def memorice_iniciar_memorizar():
    with data_lock:
        m = estado_juego["memorice"]
        m["status"] = "memorizing"
        m["timer_active"] = False
        m["current_order_index"] = 0
        m["revealed_indices"] = []
        m["error_index"] = -1
        
        guardar_datos()
        notificar_cambio()
    return jsonify(estado_juego["memorice"])

@app.route("/api/juego/memorice/iniciar-juego", methods=["POST"])
def memorice_iniciar_juego():
    with data_lock:
        m = estado_juego["memorice"]
        m["status"] = "playing"
        m["timer_active"] = True
        m["timer_start_time"] = time.time()
        
        # Generar orden aleatorio del 0 al 8
        order = list(range(9))
        random.shuffle(order)
        m["order"] = order
        
        m["current_order_index"] = 0
        m["revealed_indices"] = []
        m["error_index"] = -1
        m["active_player_index"] = 0
        
        guardar_datos()
        notificar_cambio()
    return jsonify(estado_juego["memorice"])

@app.route("/api/juego/memorice/intentar", methods=["POST"])
def memorice_intentar():
    body = request.get_json(force=True)
    idx = body.get("index")
    
    try:
        idx = int(idx)
    except (ValueError, TypeError):
        return jsonify({"error": "El índice debe ser un entero de 0 a 8"}), 400
        
    if idx < 0 or idx > 8:
        return jsonify({"error": "El índice debe estar en el rango de 0 a 8"}), 400
        
    with data_lock:
        m = estado_juego["memorice"]
        if m["status"] != "playing":
            return jsonify({"error": "El juego no está activo"}), 400
            
        target_idx = m["order"][m["current_order_index"]]
        
        if idx == target_idx:
            # ACIERTO!
            if idx not in m["revealed_indices"]:
                m["revealed_indices"].append(idx)
            m["current_order_index"] += 1
            m["error_index"] = -1
            
            # Ganar si ya se completaron las 9 casillas
            if m["current_order_index"] == 9:
                m["status"] = "completed"
                m["timer_active"] = False
        else:
            # FALLO! → Mostrar casilla errónea en rojo 1 segundo
            m["error_index"] = idx
            
            # Resetear progreso: todas las casillas vuelven a estar tapadas
            # y el siguiente jugador empieza la secuencia desde el principio
            m["revealed_indices"] = []
            m["current_order_index"] = 0
            
            # Rotar turno entre los 3 jugadores registrados
            pids = m["players_ids"]
            if pids:
                m["active_player_index"] = (m["active_player_index"] + 1) % len(pids)
                
        guardar_datos()
        notificar_cambio()
    return jsonify(estado_juego["memorice"])

@app.route("/api/juego/memorice/clear-error", methods=["POST"])
def memorice_clear_error():
    with data_lock:
        estado_juego["memorice"]["error_index"] = -1
        guardar_datos()
        notificar_cambio()
    return jsonify(estado_juego["memorice"])

@app.route("/api/juego/memorice/fallo", methods=["POST"])
def memorice_fallo():
    with data_lock:
        m = estado_juego["memorice"]
        m["status"] = "gameover"
        m["timer_active"] = False
        guardar_datos()
        notificar_cambio()
    return jsonify(estado_juego["memorice"])

# --- PISTA MUSICAL ---

@app.route("/api/audio/upload", methods=["POST"])
def upload_audio():
    if 'audio' not in request.files:
        return jsonify({"error": "No se encontró el archivo de audio"}), 400
        
    file = request.files['audio']
    if file.filename == '':
        return jsonify({"error": "Nombre de archivo inválido"}), 400
        
    filename = secure_filename(file.filename)
    _, ext = os.path.splitext(filename)
    if ext.lower() not in ['.mp3', '.wav', '.ogg', '.m4a']:
        return jsonify({"error": "Formato de audio no permitido (usa MP3, WAV, OGG o M4A)"}), 400
        
    new_filename = f"track_{int(time.time())}{ext}"
    file.save(os.path.join(app.config['UPLOAD_FOLDER'], new_filename))
    url = f"/uploads/{new_filename}"
    
    with data_lock:
        estado_juego["music"]["audio_url"] = url
        estado_juego["music"]["revealed_level"] = 0
        guardar_datos()
        notificar_cambio()
        
    return jsonify({"success": True, "audio_url": url})

@app.route("/api/juego/music/config", methods=["POST"])
def music_config():
    body = request.get_json(force=True)
    clues = body.get("clues", [])
    audio_url = body.get("audio_url", "")
    
    with data_lock:
        if isinstance(clues, list) and len(clues) == 5:
            estado_juego["music"]["clues"] = [c.strip() for c in clues]
        if audio_url is not None:
            estado_juego["music"]["audio_url"] = audio_url.strip()
            
        estado_juego["music"]["revealed_level"] = 0
        guardar_datos()
        notificar_cambio()
    return jsonify(estado_juego["music"])

@app.route("/api/juego/music/revelar", methods=["POST"])
def music_revelar():
    with data_lock:
        level = estado_juego["music"]["revealed_level"]
        if level < 5:
            estado_juego["music"]["revealed_level"] += 1
            guardar_datos()
            notificar_cambio()
    return jsonify(estado_juego["music"])

@app.route("/api/juego/music/nivel", methods=["POST"])
def set_music_level():
    body = request.get_json(force=True)
    level = body.get("level", 0)
    try:
        level = int(level)
    except ValueError:
        return jsonify({"error": "El nivel debe ser numérico"}), 400
        
    if level < 0 or level > 5:
        return jsonify({"error": "Nivel fuera de rango (0-5)"}), 400
        
    with data_lock:
        estado_juego["music"]["revealed_level"] = level
        guardar_datos()
        notificar_cambio()
    return jsonify(estado_juego["music"])

@app.route("/api/juego/music/adivinada", methods=["POST"])
def music_adivinada():
    body = request.get_json(force=True)
    jid = body.get("id")
    if jid is None:
        return jsonify({"error": "Se requiere el ID del jugador"}), 400
        
    with data_lock:
        level = estado_juego["music"]["revealed_level"]
        if level < 1 or level > 5:
            return jsonify({"error": "Debes estar en un nivel de pista activo (1-5) para puntuar"}), 400
            
        puntos = 60 - (level * 10)
        
        encontrado = None
        for j in estado_juego["jugadores"]:
            if j["id"] == jid:
                j["puntaje_total"] = max(0, j["puntaje_total"] + puntos)
                j["ultimo_cambio"] = puntos
                j["timestamp_actualizacion"] = time.time()
                encontrado = j
                break
                
        if not encontrado:
            return jsonify({"error": "Jugador no encontrado"}), 404
            
        guardar_datos()
        notificar_cambio()
        
    return jsonify({"jugador": encontrado, "puntos_asignados": puntos})

# --- JUEGO: AHORA CAIGO ---

@app.route("/api/juego/ahoracaigo/preset", methods=["GET"])
def ahoracaigo_get_presets():
    """Retorna los conceptos predefinidos."""
    return jsonify(cargar_preset_archivo("conceptos.json", DEFAULT_CONCEPTOS))

@app.route("/api/juego/ahoracaigo/config", methods=["POST"])
def ahoracaigo_config():
    """Configura el concepto y definición de Ahora Caigo."""
    body = request.get_json(force=True)
    concept = body.get("concept", "").strip().upper()
    definition = body.get("definition", "").strip()
    
    # Si viene vacío, sacar uno al azar del preset
    if not concept:
        conceptos = cargar_preset_archivo("conceptos.json", DEFAULT_CONCEPTOS)
        item = random.choice(conceptos)
        concept = item["concepto"]
        definition = item["definicion"]
        
    player_a = body.get("player_a_id")
    player_b = body.get("player_b_id")
    active_player = body.get("active_player_id") or player_a
    
    with data_lock:
        ac = estado_juego["ahoracaigo"]
        ac["concept"] = concept
        ac["definition"] = definition
        ac["displayed_word"] = generar_mascara(concept)
        ac["player_a_id"] = player_a
        ac["player_b_id"] = player_b
        ac["active_player_id"] = active_player
        ac["status"] = "idle"
        ac["timer_active"] = False
        ac["points_awarded"] = 0
        
        guardar_datos()
        notificar_cambio()
        
    return jsonify(estado_juego["ahoracaigo"])

@app.route("/api/juego/ahoracaigo/iniciar", methods=["POST"])
def ahoracaigo_iniciar():
    """Inicia el temporizador de Ahora Caigo."""
    body = request.get_json(force=True)
    active_player_id = body.get("active_player_id")
    
    with data_lock:
        ac = estado_juego["ahoracaigo"]
        ac["timer_active"] = True
        ac["timer_start_time"] = time.time()
        ac["status"] = "playing"
        if active_player_id:
            ac["active_player_id"] = int(active_player_id)
            
        guardar_datos()
        notificar_cambio()
        
    return jsonify(estado_juego["ahoracaigo"])

@app.route("/api/juego/ahoracaigo/revelar-letra", methods=["POST"])
def ahoracaigo_revelar_letra():
    """Revela una letra oculta al azar en el proyector."""
    with data_lock:
        ac = estado_juego["ahoracaigo"]
        
        concept_chars = ac["concept"].strip().upper()
        display_list = ac["displayed_word"].split(" ")
        
        hidden_indices = [i for i, char in enumerate(display_list) if char == "_"]
        if hidden_indices:
            idx_to_reveal = random.choice(hidden_indices)
            display_list[idx_to_reveal] = concept_chars[idx_to_reveal]
            ac["displayed_word"] = " ".join(display_list)
            
            guardar_datos()
            notificar_cambio()
            
    return jsonify(estado_juego["ahoracaigo"])

@app.route("/api/juego/ahoracaigo/correcto", methods=["POST"])
def ahoracaigo_correcto():
    """Marca acierto, calcula puntos y los asigna al jugador activo."""
    body = request.get_json(force=True)
    remaining_time = body.get("remaining_time", 0)
    
    try:
        remaining_time = int(remaining_time)
    except ValueError:
        remaining_time = 0
        
    with data_lock:
        ac = estado_juego["ahoracaigo"]
        jid = ac["active_player_id"]
        
        if not jid:
            return jsonify({"error": "No hay un jugador activo asignado"}), 400
            
        # Puntos: >15 seg = 40 pts, <=15 seg = 20 pts
        puntos = 40 if remaining_time >= 15 else 20
        
        encontrado = None
        for j in estado_juego["jugadores"]:
            if j["id"] == jid:
                j["puntaje_total"] = max(0, j["puntaje_total"] + puntos)
                j["ultimo_cambio"] = puntos
                j["timestamp_actualizacion"] = time.time()
                encontrado = j
                break
                
        if not encontrado:
            return jsonify({"error": "Jugador activo no encontrado en la lista"}), 404
            
        ac["status"] = "correct"
        ac["timer_active"] = False
        ac["points_awarded"] = puntos
        # Revelar por completo la palabra en proyector
        ac["displayed_word"] = " ".join(list(ac["concept"]))
        
        guardar_datos()
        notificar_cambio()
        
    return jsonify({"success": True, "puntos_asignados": puntos, "jugador": encontrado})

@app.route("/api/juego/ahoracaigo/fallo", methods=["POST"])
def ahoracaigo_fallo():
    """Registra fallo por tiempo agotado o rendición."""
    with data_lock:
        ac = estado_juego["ahoracaigo"]
        ac["status"] = "timeout"
        ac["timer_active"] = False
        # Revelar por completo el concepto oculto
        ac["displayed_word"] = " ".join(list(ac["concept"]))
        
        guardar_datos()
        notificar_cambio()
        
    return jsonify(estado_juego["ahoracaigo"])


# --- JUEGO: LA RULETA ROMPEHIELO ---

@app.route("/api/juego/ruleta/girar", methods=["POST"])
def ruleta_girar():
    """Selecciona un jugador del scoreboard de forma aleatoria."""
    with data_lock:
        jugadores = estado_juego["jugadores"]
        if not jugadores:
            return jsonify({"error": "No hay jugadores registrados para girar la ruleta"}), 400
            
        elegido = random.choice(jugadores)
        
        ru = estado_juego["ruleta"]
        ru["selected_player_id"] = elegido["id"]
        ru["spin_trigger"] += 1
        ru["status"] = "spinning"
        ru["question"] = "Seleccionando jugador..."
        
        guardar_datos()
        notificar_cambio()
        
    return jsonify(estado_juego["ruleta"])

@app.route("/api/juego/ruleta/pregunta", methods=["POST"])
def ruleta_pregunta():
    """Elige una pregunta aleatoria según el nivel y le asigna el puntaje."""
    body = request.get_json(force=True)
    level = body.get("level", "verde").lower()
    
    if level not in ["verde", "amarillo", "rojo"]:
        level = "verde"
        
    preguntas = cargar_preset_archivo("preguntas_ruleta.json", DEFAULT_PREGUNTAS)
    questions = preguntas.get(level, preguntas.get("verde", []))
    question = random.choice(questions)
    
    # Puntos: Verde = 10, Amarillo = 20, Rojo = 30
    points = 10 if level == "verde" else 20 if level == "amarillo" else 30
    
    with data_lock:
        ru = estado_juego["ruleta"]
        ru["question"] = question
        ru["level"] = level
        ru["points"] = points
        ru["status"] = "selected"
        
        guardar_datos()
        notificar_cambio()
        
    return jsonify(estado_juego["ruleta"])

@app.route("/api/juego/ruleta/premiar", methods=["POST"])
def ruleta_premiar():
    """Otorga los puntos del nivel de pregunta al jugador elegido por la ruleta."""
    with data_lock:
        ru = estado_juego["ruleta"]
        jid = ru["selected_player_id"]
        puntos = ru["points"]
        
        if not jid:
            return jsonify({"error": "No hay un jugador seleccionado por la ruleta"}), 400
            
        encontrado = None
        for j in estado_juego["jugadores"]:
            if j["id"] == jid:
                j["puntaje_total"] = max(0, j["puntaje_total"] + puntos)
                j["ultimo_cambio"] = puntos
                j["timestamp_actualizacion"] = time.time()
                encontrado = j
                break
                
        if not encontrado:
            return jsonify({"error": "El jugador seleccionado ya no existe"}), 404
            
        ru["status"] = "answered"
        
        guardar_datos()
        notificar_cambio()
        
    return jsonify({"success": True, "jugador": encontrado, "puntos_asignados": puntos})


# --- JUEGO: ¿QUIÉN ES MÁS PROBABLE QUE...? ---

@app.route("/api/juego/probable/preset", methods=["GET"])
def probable_get_presets():
    """Retorna las premisas predefinidas."""
    return jsonify(cargar_preset_archivo("probable.json", DEFAULT_PROBABLE))

@app.route("/api/juego/probable/config", methods=["POST"])
def probable_config():
    """Configura la premisa activa de probabilidad."""
    body = request.get_json(force=True)
    question = body.get("question", "").strip()
    
    if not question:
        probables = cargar_preset_archivo("probable.json", DEFAULT_PROBABLE)
        question = random.choice(probables)
        
    with data_lock:
        pr = estado_juego["probable"]
        pr["question"] = question
        pr["winners_ids"] = []
        
        guardar_datos()
        notificar_cambio()
        
    return jsonify(estado_juego["probable"])

@app.route("/api/juego/probable/votar", methods=["POST"])
def probable_votar():
    """Guarda a los ganadores de la premisa y les otorga +20 puntos a cada uno."""
    body = request.get_json(force=True)
    ids = body.get("ids", [])
    
    if not isinstance(ids, list):
        return jsonify({"error": "Los IDs de ganadores deben enviarse en formato de lista"}), 400
        
    with data_lock:
        pr = estado_juego["probable"]
        pr["winners_ids"] = [int(i) for i in ids]
        
        # Cada premisa ganada otorga +20 puntos en el acto a los seleccionados
        puntos = 20
        ganadores_afectados = []
        for jid in pr["winners_ids"]:
            for j in estado_juego["jugadores"]:
                if j["id"] == jid:
                    j["puntaje_total"] = max(0, j["puntaje_total"] + puntos)
                    j["ultimo_cambio"] = puntos
                    j["timestamp_actualizacion"] = time.time()
                    ganadores_afectados.append(j)
                    break
                    
        guardar_datos()
        notificar_cambio()
        
    return jsonify({"success": True, "ganadores": ganadores_afectados, "puntos_asignados": puntos})


# ──────────────────────────────────────────────
# 📡 SERVER-SENT EVENTS (SSE) STREAM
# ──────────────────────────────────────────────

@app.route("/api/stream")
def sse_stream():
    """
    Canal SSE permanente para el proyector.
    Envía actualizaciones completas del estado cuando se notifica un cambio.
    Evita la fuga de hilos mediante el envío de un ping de latido periódico.
    """
    def event_generator():
        last_seen_version = -1
        last_heartbeat = time.time()
        while True:
            now = time.time()
            if data_version != last_seen_version:
                last_seen_version = data_version
                with data_lock:
                    payload = json.dumps(estado_juego, ensure_ascii=False)
                yield f"data: {payload}\n\n"
                last_heartbeat = now
            elif now - last_heartbeat > 5.0:
                # Envía un latido (ping) para mantener la conexión activa
                # y permitir que el servidor detecte disonexiones del cliente.
                yield ": ping\n\n"
                last_heartbeat = now
            time.sleep(0.2)

    return Response(
        event_generator(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive"
        }
    )

# ──────────────────────────────────────────────
# 🚀 EJECUCIÓN
# ──────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 50)
    print("  [INIT] UJUNTITA - RETRO ARCADE SERVER")
    print("   Panel Administrador: http://localhost:5000/admin")
    print("   Pantalla Proyector:  http://localhost:5000/proyector")
    print(f"   Persistencia JSON:   {DB_PATH}")
    print("=" * 50)
    app.run(debug=True, threaded=True, port=5000)
