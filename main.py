import sys
import sqlite3
import requests
import threading
import webbrowser
import time
from bs4 import BeautifulSoup
from pynput import mouse
from PyQt6.QtWidgets import (QApplication, QMainWindow, QListWidget, QVBoxLayout, 
                             QWidget, QLabel, QListWidgetItem, QPushButton, QTabWidget)
from PyQt6.QtCore import Qt, pyqtSignal, QThread
from PyQt6.QtGui import QColor

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

class VideoListWidget(QListWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window

    def mousePressEvent(self, event):
        item = self.itemAt(event.pos())
        if not item:
            return

        url = item.data(Qt.ItemDataRole.UserRole)
        db_id = item.data(Qt.ItemDataRole.UserRole + 1)

        if event.button() == Qt.MouseButton.LeftButton:
            if url:
                webbrowser.open(url)
                self.main_window.mark_as_watched(db_id, item)
            
        elif event.button() == Qt.MouseButton.RightButton:
            self.main_window.mark_as_unwatched(db_id, item)
            
        elif event.button() == Qt.MouseButton.MiddleButton:
            self.main_window.delete_video(db_id, item)

        super().mousePressEvent(event)

class LavidaApp(QMainWindow):
    add_video_signal = pyqtSignal(str, str, int)

    def __init__(self):
        super().__init__()
        
        self.setWindowTitle("Lavida")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | 
                            Qt.WindowType.WindowStaysOnTopHint | 
                            Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(320, 550)
        self.setAcceptDrops(True)

        self.position_left_center()
        self.init_db()
        self.setup_ui()
        self.load_data()

        self.add_video_signal.connect(self.add_item_to_ui)

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
        self.layout.setContentsMargins(10, 10, 10, 10)

        self.setStyleSheet("""
            QWidget {
                background-color: rgba(10, 10, 10, 220);
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
            QTabWidget::pane {
                border: 0;
                background: transparent;
            }
            QTabBar::tab {
                background: rgba(255, 255, 255, 20);
                color: white;
                padding: 8px 15px;
                margin-right: 2px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            QTabBar::tab:selected {
                background: rgba(255, 50, 50, 100);
                font-weight: bold;
            }
            QTabBar::tab:hover {
                background: rgba(255, 255, 255, 40);
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
            QPushButton {
                background-color: rgba(200, 50, 50, 30);
                color: rgba(255, 255, 255, 150);
                border: 1px solid rgba(200, 50, 50, 50);
                border-radius: 8px;
                padding: 5px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: rgba(255, 0, 0, 180);
                color: white;
                border: 1px solid red;
            }
        """)

        lbl = QLabel("Lavida List")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(lbl)

        self.tabs = QTabWidget()
        
        self.list_1 = VideoListWidget(self)
        self.list_2 = VideoListWidget(self)
        self.list_3 = VideoListWidget(self)

        self.tab_lists = [self.list_1, self.list_2, self.list_3]

        self.tabs.addTab(self.list_1, "1")
        self.tabs.addTab(self.list_2, "2")
        self.tabs.addTab(self.list_3, "3")

        self.layout.addWidget(self.tabs)

        self.close_btn = QPushButton("disable")
        self.close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_btn.clicked.connect(self.close_application)
        self.layout.addWidget(self.close_btn)

    def close_application(self):
        QApplication.quit()

    def init_db(self):
        self.conn = sqlite3.connect("lavida.db", check_same_thread=False)
        self.cursor = self.conn.cursor()
        
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS videos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT,
                title TEXT,
                watched INTEGER DEFAULT 0,
                tab_index INTEGER DEFAULT 0
            )
        """)
        
        try:
            self.cursor.execute("ALTER TABLE videos ADD COLUMN tab_index INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass 

        self.conn.commit()

    def load_data(self):
        for lst in self.tab_lists:
            lst.clear()

        self.cursor.execute("SELECT id, title, url, watched, tab_index FROM videos ORDER BY id DESC")
        for vid_id, title, url, watched, tab_index in self.cursor.fetchall():
            target_index = tab_index if tab_index < len(self.tab_lists) else 0
            self.add_item_ui_raw(vid_id, title, url, watched, target_index)

    def add_item_ui_raw(self, vid_id, title, url, watched, tab_index):
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
            
        self.tab_lists[tab_index].addItem(item)

    def add_item_to_ui(self, title, url, tab_index):
        self.cursor.execute("INSERT INTO videos (url, title, tab_index) VALUES (?, ?, ?)", (url, title, tab_index))
        self.conn.commit()
        last_id = self.cursor.lastrowid
        self.add_item_ui_raw(last_id, title, url, 0, tab_index)

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
        
        list_widget = item.listWidget()
        row = list_widget.row(item)
        list_widget.takeItem(row)

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
            current_tab_index = self.tabs.currentIndex()
            threading.Thread(target=self.fetch_title, args=(url, current_tab_index), daemon=True).start()

    def fetch_title(self, url, tab_index):
        try:
            headers = {'User-Agent': 'Mozilla/5.0'}
            response = requests.get(url, headers=headers, timeout=5)
            soup = BeautifulSoup(response.text, 'html.parser')
            if soup.title:
                title = soup.title.string.replace("- YouTube", "").strip()
            else:
                title = url
            self.add_video_signal.emit(title, url, tab_index)
        except:
            self.add_video_signal.emit(url, url, tab_index)

    def toggle_visibility(self):
        if self.isHidden():
            self.show()
            self.activateWindow()
        else:
            self.hide()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = LavidaApp()
    
    # window.show()

    sys.exit(app.exec())