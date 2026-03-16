import sys
import signal
import logging
from PyQt6.QtWidgets import QApplication
from src.ui.main_window import LavidaApp
from src.database import Database
from src.workers import detect_input, activation_key_label, DEFAULT_ACTIVATION_KEY

logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s %(name)s %(levelname)s: %(message)s'
)


def ask_activation_key(db):
    print("\n  Welcome to Lavida!")
    print("  Set your activation key (toggles the window).")
    print("  Press Enter when ready, then press the key you want to use.\n")
    input("  Press Enter to start...")
    print("  Now press any mouse button, scroll, or keyboard key...", end="", flush=True)

    key = detect_input(timeout=30)
    if key is None:
        key = DEFAULT_ACTIVATION_KEY
        print(f" timed out, using default: {activation_key_label(key)}\n")
    else:
        print(f" got it: {activation_key_label(key)}\n")

    db.save_setting('activation_key', key)


if __name__ == "__main__":
    db = Database()
    if db.load_setting('activation_key') is None:
        ask_activation_key(db)
    db.close()

    app = QApplication(sys.argv)
    window = LavidaApp()

    def graceful_exit(*_):
        window.close_application()

    signal.signal(signal.SIGINT, graceful_exit)

    if window.db.load_setting('start_visible', '0') == '1':
        window.show()

    sys.exit(app.exec())
