from flask import Flask, request, jsonify, render_template, send_from_directory
from datetime import datetime, timedelta
from pathlib import Path
import os
import json
import threading
import tinytuya
import time
import configparser
import platform
import subprocess

app = Flask(__name__)


@app.route('/favicon.ico')
def favicon():
    return send_from_directory(app.static_folder, 'favicon.ico')


CONFIG_PATH = "config.ini"
cfg = configparser.ConfigParser()

if not os.path.isfile(CONFIG_PATH):
    raise FileNotFoundError(f"[ERROR] No se encontró el archivo de configuración: {CONFIG_PATH}")

cfg.read(CONFIG_PATH, encoding="utf-8")

# Verifica si la sección 'tuya' está presente
if not cfg.has_section("tuya"):
    raise ValueError(f"[ERROR] El archivo {CONFIG_PATH} no contiene la sección [tuya]")

# Ahora ya puedes acceder con seguridad a las claves:
TUYA_ID = cfg.get("tuya", "device_id")
TUYA_IP = cfg.get("tuya", "device_ip")
TUYA_KEY = cfg.get("tuya", "local_key")
TUYA_VERSION = cfg.getfloat("tuya", "version")


JSON_FOLDER = "json"
os.makedirs(JSON_FOLDER, exist_ok=True)

estado_actual = {"estado": "desconocido", "proximo": "", "hora": ""}
ciclo_en_ejecucion = False
ciclo_thread = None
horarios_actuales = None


@app.route("/")
@app.route("/ciclo")
def ciclo():
    return render_template("ciclo.html")


@app.route("/guardar-json", methods=["POST"])
def guardar_json():
    try:
        data = request.get_json()
        eventos = data.get("eventos")
        superciclo = data.get("superciclo")
        fecha_inicio = data.get("fecha_inicio")

        if not (eventos and superciclo and fecha_inicio):
            return jsonify({"success": False, "message": "Datos incompletos."})

        ruta = os.path.join(JSON_FOLDER, "horarios.json")
        with open(ruta, "w", encoding="utf-8") as f:
            json.dump({
                "eventos": eventos,
                "superciclo": superciclo,
                "fecha_inicio": fecha_inicio
            }, f, ensure_ascii=False, indent=2)

        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})


def cargar_horarios():
    ruta = os.path.join(JSON_FOLDER, "horarios.json")
    try:
        with open(ruta, encoding="utf-8") as f:
            data = json.load(f)
            if "fecha_inicio" in data:
                data["fecha_inicio"] = datetime.fromisoformat(data["fecha_inicio"])
            return data
    except Exception as e:
        print(f"[ERROR] al cargar horarios.json: {e}")
        return None




def construir_eventos_abs(data, ahora):
    ref = data.get("fecha_inicio") or ahora.replace(hour=0, minute=0, second=0, microsecond=0)

    if isinstance(ref, str):
        ref = datetime.fromisoformat(ref)

    # 1. Construimos todos los eventos absolutos iniciales
    eventos_base = []
    for ev in data["eventos"]:
        h, m = map(int, ev["hora"].split(":"))
        dt = ref + timedelta(days=ev["dia"], hours=h, minutes=m)
        eventos_base.append((ev["accion"].lower(), dt))

    # 2. Determinamos el horizonte temporal necesario
    fecha_mas_lejana = max(dt for _, dt in eventos_base)
    horizonte = max(
        (fecha_mas_lejana - ahora).days + 7,  # Cubrir el evento más lejano
        14  # Mínimo 2 semanas de horizonte por seguridad
    )

    # 3. Generamos eventos recurrentes hasta cubrir el horizonte
    eventos_ext = []
    for accion, dt in eventos_base:
        current_dt = dt
        while (current_dt - ahora).days <= horizonte:
            if current_dt >= ahora - timedelta(days=1):  # Ignorar eventos muy pasados
                eventos_ext.append((accion, current_dt))
            current_dt += timedelta(days=7)

    # 4. Ordenamos todos los eventos
    eventos_ext.sort(key=lambda x: x[1])

    return eventos_ext


def superciclo(data):
    global estado_actual, ciclo_en_ejecucion
    ciclo_en_ejecucion = True

    enchufe = tinytuya.OutletDevice(TUYA_ID, TUYA_IP, TUYA_KEY)
    enchufe.set_version(TUYA_VERSION)

    estado_previo = None

    while ciclo_en_ejecucion:
        ahora = datetime.now()
        accion_actual, proximo_dt = calcular_estado_y_proximo(data, ahora)

        if accion_actual != estado_previo:
            estado_previo = accion_actual
            try:
                if accion_actual == "on":
                    enchufe.turn_on()
                else:
                    enchufe.turn_off()
            except Exception as e:
                print(f"[ERROR] Controlando enchufe: {e}")

        estado_actual.update(
            estado=accion_actual,
            proximo=proximo_dt.strftime("%Y-%m-%d %H:%M"),
            hora=ahora.strftime("%Y-%m-%d %H:%M:%S")
        )
        time.sleep(30)

    ciclo_en_ejecucion = False


@app.route("/iniciar_ciclo", methods=["POST"])
def iniciar_ciclo():
    global ciclo_en_ejecucion, ciclo_thread, horarios_actuales

    nuevos_horarios = cargar_horarios()
    if nuevos_horarios is None:
        return jsonify({"mensaje": "No se pudo cargar horarios.json"})

    if ciclo_en_ejecucion and nuevos_horarios == horarios_actuales:
        return jsonify({"mensaje": "SuperCiclo ya generado y ejecutado..."})

    if ciclo_en_ejecucion:
        ciclo_en_ejecucion = False
        time.sleep(1)

    horarios_actuales = nuevos_horarios

    ciclo_thread = threading.Thread(target=superciclo, args=(nuevos_horarios,))  # ✅ pasamos argumento
    ciclo_thread.daemon = True
    ciclo_thread.start()

    return jsonify({"mensaje": "Nuevo SuperCiclo ejecutado..."})


def calcular_estado_y_proximo(data, ahora):
    eventos = construir_eventos_abs(data, ahora)

    estado_actual = None
    proximo_evento = None

    for i, (accion, dt) in enumerate(eventos):
        if dt > ahora:
            estado_actual = eventos[i - 1][0] if i > 0 else eventos[-1][0]
            proximo_evento = dt
            break
    else:
        estado_actual = eventos[-1][0]
        proximo_evento = eventos[0][1] + timedelta(days=7)

    return estado_actual, proximo_evento


@app.route("/estado_ciclo")
def estado_ciclo():
    data = cargar_horarios()
    if not data:
        return jsonify({
            "superciclo": "--",
            "estado": "desconocido",
            "proximo": "--",
            "hora": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })

    ahora = datetime.now()
    estado, proximo_dt = calcular_estado_y_proximo(data, ahora)

    return jsonify({
        "superciclo": data.get("superciclo", "--"),
        "estado": estado,
        "proximo": proximo_dt.strftime("%Y-%m-%d %H:%M"),
        "hora": ahora.strftime("%Y-%m-%d %H:%M:%S")
    })


@app.route("/verificar_horarios")
def verificar_horarios():
    ruta = os.path.join(JSON_FOLDER, 'horarios.json')
    return jsonify({"existe": os.path.isfile(ruta), "ejecutando": ciclo_en_ejecucion})


@app.route("/config-ini", methods=["POST"])
def abrir_config_ini():
    try:
        if platform.system() == "Windows":
            os.startfile(CONFIG_PATH)
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", CONFIG_PATH])
        else:
            subprocess.Popen(["xdg-open", CONFIG_PATH])

        return jsonify(ok=True)
    except Exception as e:
        return jsonify(ok=False, error=str(e)), 500
