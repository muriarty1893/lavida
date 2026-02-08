import sys
import sqlite3
import requests
import threading
import webbrowser
import time  # Zaman kilidi için gerekli
from bs4 import BeautifulSoup

# --- Global Mouse Dinleyicisi ---
from pynput import mouse

from PyQt6.QtWidgets import (QApplication, QMainWindow, QListWidget, 
                             QVBoxLayout, QWidget, QLabel, QListWidgetItem)
from PyQt6.QtCore import Qt, pyqtSignal, QThread
from PyQt6.QtGui import QColor

# --- 1. Global Mouse Dinleyicisi (Button 7 Dedektifi) ---
class GlobalInputListener(QThread):
    toggle_signal = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.last_action_time = 0  # Son işlem zamanı

    def run(self):
        # Sadece scroll olayını dinliyoruz
        # Button 6 ve 7 pynput'ta 'on_scroll' olarak gelir
        with mouse.Listener(on_scroll=self.on_scroll) as listener:
            listener.join()

    def on_scroll(self, x, y, dx, dy):
        # dx > 0  => Button 7 (Sağa İtme)
        # dx < 0  => Button 6 (Sola İtme)
        # dy ...  => Button 4/5 (Yukarı/Aşağı)

        # Sadece Button 7 (Sağa İtme) ise işlem yap
        if dx > 0:
            current_time = time.time()
            # Eğer son işlemden bu yana 0.4 saniye geçmediyse YOK SAY (Debounce)
            if current_time - self.last_action_time > 0.4:
                self.toggle_signal.emit()
                self.last_action_time = current_time

# --- 2. Özel Liste Kutusu ---
class VideoListWidget(QListWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent

    def mousePressEvent(self, event):
        item = self.itemAt(event.pos())
        if not item:
            return

        url = item.data(Qt.ItemDataRole.UserRole)
        db_id = item.data(Qt.ItemDataRole.UserRole + 1)

        if event.button() == Qt.MouseButton.LeftButton:
            # Sol Tık: Aç + İzlendi
            if url:
                webbrowser.open(url)
                self.parent_window.mark_as_watched(db_id, item)
            
        elif event.button() == Qt.MouseButton.RightButton:
            # Sağ Tık: İzlenmedi Yap
            self.parent_window.mark_as_unwatched(db_id, item)
            
        elif event.button() == Qt.MouseButton.MiddleButton:
            # Orta Tık: Sil
            self.parent_window.delete_video(db_id, item)

        super().mousePressEvent(event)

# --- 3. Ana Uygulama ---
class LavidaApp(QMainWindow):
    add_video_signal = pyqtSignal(str, str)

    def __init__(self):
        super().__init__()
        
        # --- Pencere Ayarları ---
        self.setWindowTitle("Lavida")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | 
                            Qt.WindowType.WindowStaysOnTopHint | 
                            Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(300, 500)
        self.setAcceptDrops(True)

        self.position_left_center()
        self.init_db()
        self.setup_ui()
        self.load_data()

        self.add_video_signal.connect(self.add_item_to_ui)

        # --- Dinleyiciyi Başlat ---
        self.listener = GlobalInputListener()
        self.listener.toggle_signal.connect(self.toggle_visibility)
        self.listener.start()

    def position_left_center(self):
        screen = QApplication.primaryScreen().geometry()
        new_y = (screen.height() - self.height()) // 2
        self.move(10, new_y)

    def setup_ui(self):
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)
        self.layout.setContentsMargins(5, 5, 5, 5)

        self.setStyleSheet("""
            QWidget {
                background-color: rgba(10, 10, 10, 200);
                border-radius: 12px;
                color: #ffffff;
                font-family: 'Segoe UI', sans-serif;
            }
            QLabel { 
                background: transparent; 
                font-weight: bold; 
                font-size: 14px;
                color: #ff4444; 
                margin-bottom: 5px;
            }
            QListWidget { 
                background: transparent; 
                border: none; 
                outline: none; 
            }
            QListWidget::item { 
                padding: 10px; 
                border-bottom: 1px solid rgba(255,255,255,20); 
            }
            QListWidget::item:hover { 
                background: rgba(255,255,255,30); 
                border-radius: 5px;
            }
        """)

        lbl = QLabel("Lavida List")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(lbl)

        self.list_widget = VideoListWidget(self)
        self.list_widget.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.layout.addWidget(self.list_widget)

    def init_db(self):
        self.conn = sqlite3.connect("lavida.db", check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS videos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT,
                title TEXT,
                watched INTEGER DEFAULT 0
            )
        """)
        self.conn.commit()

    def load_data(self):
        self.list_widget.clear()
        self.cursor.execute("SELECT id, title, url, watched FROM videos ORDER BY id DESC")
        for vid_id, title, url, watched in self.cursor.fetchall():
            self.add_item_ui_raw(vid_id, title, url, watched)

    def add_item_ui_raw(self, vid_id, title, url, watched):
        item = QListWidgetItem(title)
        item.setData(Qt.ItemDataRole.UserRole, url)
        item.setData(Qt.ItemDataRole.UserRole + 1, vid_id)
        
        if watched == 1:
            item.setForeground(QColor("gray"))
            font = item.font()
            font.setStrikeOut(True)
            item.setFont(font)
        else:
            item.setForeground(QColor("white"))
            font = item.font()
            font.setStrikeOut(False)
            item.setFont(font)
            
        self.list_widget.addItem(item)

    def add_item_to_ui(self, title, url):
        self.cursor.execute("INSERT INTO videos (url, title) VALUES (?, ?)", (url, title))
        self.conn.commit()
        last_id = self.cursor.lastrowid
        self.add_item_ui_raw(last_id, title, url, 0)

    def mark_as_watched(self, vid_id, item):
        self.cursor.execute("UPDATE videos SET watched = 1 WHERE id = ?", (vid_id,))
        self.conn.commit()
        item.setForeground(QColor("gray"))
        font = item.font()
        font.setStrikeOut(True)
        item.setFont(font)

    def mark_as_unwatched(self, vid_id, item):
        self.cursor.execute("UPDATE videos SET watched = 0 WHERE id = ?", (vid_id,))
        self.conn.commit()
        item.setForeground(QColor("white"))
        font = item.font()
        font.setStrikeOut(False)
        item.setFont(font)

    def delete_video(self, vid_id, item):
        self.cursor.execute("DELETE FROM videos WHERE id = ?", (vid_id,))
        self.conn.commit()
        row = self.list_widget.row(item)
        self.list_widget.takeItem(row)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls() or event.mimeData().hasText():
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        url = ""
        if event.mimeData().hasUrls():
            url = event.mimeData().urls()[0].toString()
        elif event.mimeData().hasText():
            url = event.mimeData().text()
            
        if "youtube.com" in url or "youtu.be" in url:
            threading.Thread(target=self.fetch_title, args=(url,), daemon=True).start()

    def fetch_title(self, url):
        try:
            headers = {'User-Agent': 'Mozilla/5.0'}
            response = requests.get(url, headers=headers, timeout=5)
            soup = BeautifulSoup(response.text, 'html.parser')
            if soup.title:
                title = soup.title.string.replace("- YouTube", "").strip()
            else:
                title = url
            self.add_video_signal.emit(title, url)
        except:
            self.add_video_signal.emit(url, url)

    # --- Görünürlük ---
    def toggle_visibility(self):
        if self.isHidden():
            self.show()
            self.activateWindow()
        else:
            self.hide()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = LavidaApp()
    
    # window.show()  <-- BUNU SİL VEYA YORUM SATIRI YAP
    # Artık uygulama hayalet gibi başlayacak.
    # Sen mouse'u sağa ittirdiğinde "toggle_visibility" çalışıp onu gösterecek.
    
    sys.exit(app.exec())