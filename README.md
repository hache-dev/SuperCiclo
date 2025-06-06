# SuperCiclo

Aplicación de escritorio (Windows) que permite **programar ciclos de encendido / apagado** sobre un enchufe inteligente Tuya.  
Se ejecuta localmente con **Flask** (backend) y se muestra en una ventana **pywebview**; además incorpora un icono en la bandeja mediante **pystray**.

---

## 1. Características principales

| Función | Descripción |
|---------|-------------|
| Generador de ciclo | Calcula y muestra una matriz ON / OFF para *n* días a partir de una hora de inicio, horas ON y horas OFF. |
| Exportación de JSON | Guarda los eventos en `json/horarios.json` para que el backend los ejecute. |
| Ejecución automática | Detecta la presencia de `horarios.json`, inicia el ciclo y muestra su estado en tiempo real. |
| Configuración Tuya | Datos del dispositivo (ID, IP, clave, versión) se almacenan en `config.ini`. |
| Icono de bandeja | Acciones Mostrar / Ocultar / Salir. |
| Partículas de fondo | Efecto visual en la interfaz (particles.js). |

---

## 2. Requisitos

* Python 3.9 +  
* Bibliotecas:

```bash
pip install flask pywebview pystray pillow tinytuya configparser
```

**Windows:** es aconsejable ejecutar en *PowerShell* con privilegios de administrador para permitir llamadas a `os.startfile`.

---

## 3. Instalación rápida

```bash
git clone [https://github.com/tu_usuario/superciclo.git](https://github.com/hache-dev/SuperCiclo.git)
cd superciclo
python -m venv venv
venv\Scripts\activate  # Linux/Mac: source venv/bin/activate
pip install -r requirements.txt
python main.py
```

---

## 4. Archivo `config.ini`

```ini
[tuya]
device_id  = TU_DISPOSITIVO_ID
device_ip  = 192.168.0.15
local_key  = XXXXXYYYYZZZZAAAA
version    = 3.4
```

*Si modificás el archivo desde la aplicación (`Menú → Configuración`) recordá **reiniciar** para que los cambios tengan efecto.*

---

## 5. Estructura de carpetas

```
superciclo/
│ main.py              ← Lanzador (GUI + bandeja)
│ app.py               ← Backend Flask
│ config.ini
│ json/
│   └─ horarios.json   ← Generado desde la interfaz
│ static/
│   └─ img/trayicon.png
│ templates/
│   └─ ciclo.html
```

---

## 6. Uso básico

1. Ejecutá `python main.py`; se abrirá la ventana **SuperCiclo**.  
2. Completá hora de inicio, horas ON, horas OFF y el número de días.  
3. **Generar** para visualizar la matriz.  
4. **Exportar** guarda el archivo `horarios.json`.  
5. **Ejecutar** inicia el ciclo: el enchufe se activará/desactivará según el cronograma.

La sección *Info SuperCiclo* muestra:

* **SuperCiclo** (HS ON / HS OFF)
* **Estado actual** (ON / OFF)
* **Próximo estado** (fecha‑hora del próximo cambio)
* **Hora** local del sistema

---

## 7. Compilación a EXE (opcional)

Se puede empaquetar con **auto‑py‑to‑exe** en modo **One Directory**:

```
auto-py-to-exe   --script main.py   --windowed --onefile   --icon static/img/trayicon.ico   --add-data "templates;ciclo"   --add-data "static;static"   --add-data "config.ini;."   --add-data "json;json"
```

El ejecutable resultante contendrá las carpetas `templates`, `static`, `json` y el `config.ini` en el mismo directorio del `.exe`.

---

## 8. Solución de problemas

| Mensaje | Causa común | Solución |
|---------|-------------|----------|
| `No se pudo cargar horarios.json` | El archivo no existe o está mal formado. | Generar y exportar nuevamente. |
| `Error controlando el enchufe` | ID/IP/Key incorrectos. | Revisar `config.ini` y reiniciar la app. |
| Icono no aparece | Falta `trayicon.png`. | Verificá la ruta `static/img/`. |
| Tiempo incorrecto | Zona horaria del sistema | Ajustar reloj de la PC / servidor |

---

## 9. Licencia

MIT. ¡Usalo, modificálo y compartí mejoras!  
Autor: **h4ch3**
