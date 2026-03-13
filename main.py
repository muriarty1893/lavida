import sys
import signal
import logging
from PyQt6.QtWidgets import QApplication
from src.ui.main_window import LavidaApp

logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s %(name)s %(levelname)s: %(message)s'
)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = LavidaApp()

    def graceful_exit(*_):
        window.close_application()

    signal.signal(signal.SIGINT, graceful_exit)

    if window.db.load_setting('start_visible', '0') == '1':
        window.show()

    sys.exit(app.exec())
