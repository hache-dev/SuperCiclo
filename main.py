import threading
import webview
import pystray
from PIL import Image, ImageDraw
import sys
from app import app


def start_flask():
    app.run(debug=True, port=8001, use_reloader=False)


def create_image():
    return Image.open("static/img/trayicon.png")


def show_window():
    window.show()  # Mostrar ventana
    window.restore()  # Por si estaba minimizada


def hide_window():
    window.hide()


def on_minimize():
    hide_window()


def quit_app(icon):
    icon.stop()
    window.destroy()
    sys.exit()


def tray():
    icon = pystray.Icon(
        "superciclo",
        create_image(),
        "SuperCiclo - supercannabis.ar",
        menu=pystray.Menu(
            pystray.MenuItem("Mostrar", show_window),
            pystray.MenuItem("Ocultar", lambda icon, item: hide_window()),
            pystray.MenuItem("Salir", quit_app),
        ),
    )
    icon.run()


if __name__ == "__main__":
    flask_thread = threading.Thread(target=start_flask, daemon=True)
    flask_thread.start()

    window = webview.create_window("SuperCiclo - supercannabis.ar", "http://127.0.0.1:8001", width=1230, height=850)
    window.events.minimized += on_minimize

    tray_thread = threading.Thread(target=tray, daemon=True)
    tray_thread.start()

    webview.start()
