import threading
import webview
import pystray
from PIL import Image, ImageDraw
import sys
import time
from app import app

# Variable global para controlar el estado de la ventana
window_visible = True


def start_flask():
    app.run(port=8001, debug=False, use_reloader=False)


def create_image():
    try:
        return Image.open("trayicon.ico")
    except FileNotFoundError:
        width = height = 64
        background = (30, 120, 60)  # Verde cannabis
        foreground = (0, 0, 0)  # Negro

        image = Image.new('RGB', (width, height), background)
        dc = ImageDraw.Draw(image)

        size = int(width * 0.8)
        offset = (width - size) // 2

        dc.rectangle(
            (offset, offset, width - offset, height - offset),
            fill=foreground
        )
        return image


def show_window(icon=None, item=None):
    global window_visible
    if window:
        if not window_visible:
            window.show()
            window.restore()  # Asegurarse de que la ventana esté restaurada
            window_visible = True


def hide_window(icon=None, item=None):
    global window_visible
    if window and window_visible:
        window.hide()
        window_visible = False


def on_minimize():
    hide_window()


def quit_app(icon=None, item=None):
    if window:
        window.destroy()
    if icon:
        icon.stop()
    sys.exit(0)


def tray():
    image = create_image()
    image_with_alpha = image.convert('RGBA')

    menu = pystray.Menu(
        pystray.MenuItem('Mostrar', show_window),
        pystray.MenuItem('Ocultar', hide_window),
        pystray.MenuItem('Salir', quit_app)
    )

    icon = pystray.Icon(
        "superciclo",
        image_with_alpha,
        "SuperCiclo - supercannabis.ar",
        menu
    )

    try:
        icon.run()
    except KeyboardInterrupt:
        quit_app()


if __name__ == "__main__":
    flask_thread = threading.Thread(target=start_flask, daemon=True)
    flask_thread.start()
    time.sleep(1)

    window = webview.create_window(
        "SuperCiclo by h4ch3 - supercannabis.ar",
        "http://127.0.0.1:8001",
        width=1230,
        height=850,
        resizable=True
    )
    window.events.minimized += on_minimize

    tray_thread = threading.Thread(target=tray, daemon=True)
    tray_thread.start()

    webview.start()
