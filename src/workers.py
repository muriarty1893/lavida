import time
from pynput import mouse
from PyQt6.QtCore import QThread, pyqtSignal

class GlobalInputListener(QThread):
    toggle_signal = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.last_action_time = 0 

    def run(self):
        with mouse.Listener(on_scroll=self.on_scroll) as listener:
            listener.join()

    def on_scroll(self, x, y, dx, dy):
        if dx > 0:
            current_time = time.time()
            if current_time - self.last_action_time > 0.4:
                self.toggle_signal.emit()
                self.last_action_time = current_time