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

app = Flask(__name__)


@app.route('/favicon.ico')
def favicon():
    return send_from_directory(app.static_folder, 'favicon.ico')


CONFIG_PATH = "config.ini"
cfg = configparser.ConfigParser()
cfg.read(CONFIG_PATH, encoding="utf-8")

TUYA_ID = cfg.get("tuya", "device_id", fallback="")
TUYA_IP = cfg.get("tuya", "device_ip", fallback="")
TUYA_KEY = cfg.get("tuya", "local_key", fallback="")
TUYA_VERSION = cfg.getfloat("tuya", "version", fallback=3.4)

JSON_FOLDER = "json"
os.makedirs(JSON_FOLDER, exist_ok=True)

estado_actual = {"estado": "desconocido", "proximo": "", "hora": ""}
ciclo_en_ejecucion = False
ciclo_thread = None
horarios_actuales = None


@app.route("/ciclo")
def ciclo():
    return render_template("ciclo.html")


@app.route('/')
def index():
    return render_template('ciclo.html')


@app.route('/guardar-json', methods=['POST'])
def guardar_json():
    try:
        data = request.get_json()
        if not data:
            return jsonify(success=False, message="Datos JSON vacíos...")

        path = os.path.join(JSON_FOLDER, 'horarios.json')

        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        return jsonify(success=True)
    except Exception as e:
        return jsonify(success=False, message=str(e))


def cargar_horarios():
    try:
        with open(os.path.join(JSON_FOLDER, 'horarios.json'), 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error cargando horarios: {e}")
        return None


def superciclo(horarios):
    global estado_actual, ciclo_en_ejecucion

    ciclo_en_ejecucion = True

    enchufe = tinytuya.OutletDevice(TUYA_ID, TUYA_IP, TUYA_KEY)
    enchufe.set_version(TUYA_VERSION)

    # ⬇️ Si viene el dict completo, quedate sólo con la lista de eventos
    if isinstance(horarios, dict):
        horarios = horarios.get("eventos", [])

    def str_to_time(hora_str):
        h, m = map(int, hora_str.split(':'))
        return h, m

    hoy = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    eventos = []
    for evento in horarios:
        dia = evento['dia']
        h, m = str_to_time(evento['hora'])
        dt_evento = hoy + timedelta(days=dia, hours=h, minutes=m)
        eventos.append((evento['accion'].lower(), dt_evento))

    eventos.sort(key=lambda x: x[1])

    enchufe = tinytuya.OutletDevice(TUYA_ID, TUYA_IP, TUYA_KEY)
    enchufe.set_version(TUYA_VERSION)

    estado_previo = None

    def estado_y_proximo(eventos, ahora):
        n = len(eventos)

        if ahora < eventos[0][1]:
            primer_estado, primer_hora = eventos[0]
            estado_inicial = 'off' if primer_estado == 'on' else 'on'
            return estado_inicial, primer_hora

        for i in range(n):
            accion, hora_evento = eventos[i]
            siguiente_index = (i + 1) % n
            accion_siguiente, hora_siguiente = eventos[siguiente_index]
            if siguiente_index == 0:
                hora_siguiente = hora_siguiente + timedelta(days=1)
            if hora_evento <= ahora < hora_siguiente:
                return accion, hora_siguiente

        # Si no se encuentra un intervalo válido
        ultimo_accion, _ = eventos[-1]
        proximo_accion, proximo_hora = eventos[0]
        estado_resultado = 'off' if ultimo_accion == 'on' else 'on'
        return estado_resultado, proximo_hora

    while ciclo_en_ejecucion:
        ahora = datetime.now()
        estado, proximo_cambio = estado_y_proximo(eventos, ahora)

        if estado != estado_previo:
            estado_previo = estado
            try:
                if estado == 'on':
                    enchufe.turn_on()
                else:
                    enchufe.turn_off()
            except Exception as e:
                print(f"Error controlando el enchufe: {e}")

        estado_actual["estado"] = estado
        estado_actual["proximo"] = proximo_cambio.strftime('%Y-%m-%d %H:%M')
        estado_actual["hora"] = ahora.strftime('%Y-%m-%d %H:%M:%S')

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

    # Detener el ciclo actual si está en ejecución
    if ciclo_en_ejecucion:
        ciclo_en_ejecucion = False
        time.sleep(1)  # dar tiempo a que el ciclo se cierre

    # Guardar los nuevos horarios como referencia
    horarios_actuales = nuevos_horarios

    ciclo_thread = threading.Thread(target=superciclo, args=(nuevos_horarios,))
    ciclo_thread.daemon = True
    ciclo_thread.start()

    return jsonify({"mensaje": "Nuevo SuperCiclo ejecutado..."})


def calcular_estado_y_proximo(horarios, ahora):
    """Devuelve (estado_actual, datetime_proximo_cambio)"""

    def str_to_time(hhmm):
        h, m = map(int, hhmm.split(':'))
        return h, m

    hoy = ahora.replace(hour=0, minute=0, second=0, microsecond=0)
    eventos = []
    for ev in horarios:
        h, m = str_to_time(ev["hora"])
        dt = hoy + timedelta(days=ev["dia"], hours=h, minutes=m)
        eventos.append((ev["accion"].lower(), dt))
    eventos.sort(key=lambda x: x[1])

    n = len(eventos)
    for i, (accion, dt) in enumerate(eventos):
        sig_accion, sig_dt = eventos[(i + 1) % n]
        if i == n - 1:  # último → el siguiente es al día sig.
            sig_dt += timedelta(days=1)
        if dt <= ahora < sig_dt:
            return accion, sig_dt

    # Si la hora es antes del primer evento
    ult_accion, _ = eventos[-1]
    sig_accion, sig_dt = eventos[0]
    return ('off' if ult_accion == 'off' else 'on'), sig_dt


@app.route("/estado_ciclo")
def estado_ciclo():
    ruta_json = os.path.join(JSON_FOLDER, "horarios.json")
    if not os.path.isfile(ruta_json):
        return jsonify({
            "superciclo": "--",
            "estado": "desconocido",
            "proximo": "--",
            "hora": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })

    with open(ruta_json, encoding="utf-8") as f:
        data = json.load(f)

    superciclo = data.get("superciclo", "--")
    horarios = data.get("eventos", [])

    if not horarios or not ciclo_en_ejecucion:
        return jsonify({
            "superciclo": superciclo,
            "estado": "desconocido",
            "proximo": "--",
            "hora": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })

    ahora = datetime.now()
    estado, proximo = calcular_estado_y_proximo(horarios, ahora)

    return jsonify({
        "superciclo": superciclo,
        "estado": estado,
        "proximo": proximo.strftime("%Y-%m-%d %H:%M"),
        "hora": ahora.strftime("%Y-%m-%d %H:%M:%S")
    })


@app.route("/verificar_horarios")
def verificar_horarios():
    ruta = os.path.join(JSON_FOLDER, 'horarios.json')
    return jsonify({"existe": os.path.isfile(ruta), "ejecutando": ciclo_en_ejecucion})


@app.route("/config-ini", methods=["POST"])
def abrir_config_ini():
    """
    Abre config.ini con el editor por defecto del sistema (Notepad en Windows)
    y responde con JSON para que el frontend muestre un toast.
    """
    try:
        if platform.system() == "Windows":
            os.startfile(CONFIG_PATH)  # Bloc de notas
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", CONFIG_PATH])
        else:  # Linux / BSD
            subprocess.Popen(["xdg-open", CONFIG_PATH])

        return jsonify(ok=True)
    except Exception as e:
        return jsonify(ok=False, error=str(e)), 500
