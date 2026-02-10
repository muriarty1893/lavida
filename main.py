import sys
import sqlite3
import requests
import threading
import webbrowser
import time
from bs4 import BeautifulSoup
from pynput import mouse
from PyQt6.QtWidgets import (QApplication, QMainWindow, QListWidget, QVBoxLayout, 
                             QWidget, QLabel, QListWidgetItem, QPushButton, QTabWidget, QHBoxLayout, QFrame)
from PyQt6.QtCore import Qt, pyqtSignal, QThread, QSize
from PyQt6.QtGui import QColor, QCursor, QFont

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

class VideoCard(QWidget):
    def __init__(self, vid_id, title, url, watched, parent_window, list_item):
        super().__init__()
        self.vid_id = vid_id
        self.url = url
        self.watched = watched
        self.parent_window = parent_window
        self.list_item = list_item

        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(10, 8, 10, 8)
        self.layout.setSpacing(10)

        self.title_lbl = QLabel(title)
        self.title_lbl.setStyleSheet("border: none; background: transparent; color: white;")
        if watched:
            self.set_watched_style()
        
        self.layout.addWidget(self.title_lbl, stretch=1)

        self.del_btn = QPushButton("✕")
        self.del_btn.setFixedSize(24, 24)
        self.del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.del_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 50, 50, 20);
                color: #ff5555;
                border-radius: 12px;
                border: 1px solid rgba(255, 50, 50, 50);
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #ff5555;
                color: white;
            }
        """)
        self.del_btn.clicked.connect(self.delete_clicked)
        self.layout.addWidget(self.del_btn)

        self.setStyleSheet("""
            VideoCard {
                background-color: rgba(255, 255, 255, 10);
                border-radius: 8px;
                border: 1px solid rgba(255, 255, 255, 5);
            }
            VideoCard:hover {
                background-color: rgba(255, 255, 255, 20);
                border: 1px solid rgba(255, 255, 255, 20);
            }
        """)

    def set_watched_style(self):
        font = self.title_lbl.font()
        font.setStrikeOut(True)
        self.title_lbl.setFont(font)
        self.title_lbl.setStyleSheet("border: none; background: transparent; color: #888;")

    def set_unwatched_style(self):
        font = self.title_lbl.font()
        font.setStrikeOut(False)
        self.title_lbl.setFont(font)
        self.title_lbl.setStyleSheet("border: none; background: transparent; color: white;")

    def delete_clicked(self):
        self.parent_window.delete_video(self.vid_id, self.list_item)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self.url:
                webbrowser.open(self.url)
                self.parent_window.mark_as_watched(self.vid_id, self)
        elif event.button() == Qt.MouseButton.RightButton:
            self.parent_window.mark_as_unwatched(self.vid_id, self)

class LavidaApp(QMainWindow):
    update_title_signal = pyqtSignal(str, int, int) 

    def __init__(self):
        super().__init__()
        
        self.setWindowTitle("Lavida")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | 
                            Qt.WindowType.WindowStaysOnTopHint | 
                            Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(340, 600)
        self.setAcceptDrops(True)

        self.position_left_center()
        self.init_db()
        self.setup_ui()
        self.load_data()

        self.update_title_signal.connect(self.update_item_title)

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
        self.layout.setContentsMargins(15, 15, 15, 15)
        self.layout.setSpacing(10)

        self.setStyleSheet("""
            QWidget#CentralWidget {
                background-color: rgba(15, 15, 15, 230);
                border-radius: 16px;
                border: 1px solid rgba(255, 255, 255, 10);
            }
            QTabWidget::pane { border: 0; background: transparent; }
            QTabBar::tab {
                background: transparent;
                color: #888;
                padding: 8px 15px;
                font-weight: bold;
                font-size: 14px;
            }
            QTabBar::tab:selected { color: white; border-bottom: 2px solid #ff4444; }
            QTabBar::tab:hover { color: #ccc; }
            QListWidget { background: transparent; border: none; outline: none; }
            QListWidget::item { background: transparent; margin-bottom: 4px; border: none; }
            QListWidget::item:selected { background: transparent; }
        """)
        self.central_widget.setObjectName("CentralWidget")

        top_bar = QHBoxLayout()
        
        title_lbl = QLabel("Lavida")
        title_lbl.setStyleSheet("color: white; font-weight: bold; font-size: 18px; border: none; background: transparent;")
        top_bar.addWidget(title_lbl)

        top_bar.addStretch()

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(28, 28)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(self.close_application)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #888;
                border-radius: 14px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: rgba(255, 50, 50, 200);
                color: white;
            }
        """)
        top_bar.addWidget(close_btn)
        
        self.layout.addLayout(top_bar)

        self.tabs = QTabWidget()
        self.tab_lists = []
        
        for i in range(1, 4):
            lst = QListWidget()
            lst.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            lst.setSpacing(4)
            self.tab_lists.append(lst)
            self.tabs.addTab(lst, str(i))

        self.layout.addWidget(self.tabs)
        
        self.empty_lbl = QLabel("Drop links here")
        self.empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_lbl.setStyleSheet("color: rgba(255,255,255,50); font-size: 14px; font-style: italic; background: transparent;")
        self.layout.addWidget(self.empty_lbl)
        self.empty_lbl.hide()

    def check_empty_state(self):
        total_items = sum(lst.count() for lst in self.tab_lists)
        if total_items == 0:
            self.empty_lbl.show()
            self.tabs.hide()
        else:
            self.empty_lbl.hide()
            self.tabs.show()

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
            self.create_card_item(vid_id, title, url, watched, target_index)
        
        self.check_empty_state()

    def create_card_item(self, vid_id, title, url, watched, tab_index):
        target_list = self.tab_lists[tab_index]
        
        item = QListWidgetItem(target_list)
        item.setSizeHint(QSize(0, 60)) 
        
        card = VideoCard(vid_id, title, url, watched, self, item)
        target_list.setItemWidget(item, card)

    def mark_as_watched(self, vid_id, card_widget):
        self.cursor.execute("UPDATE videos SET watched = 1 WHERE id = ?", (vid_id,))
        self.conn.commit()
        card_widget.set_watched_style()

    def mark_as_unwatched(self, vid_id, card_widget):
        self.cursor.execute("UPDATE videos SET watched = 0 WHERE id = ?", (vid_id,))
        self.conn.commit()
        card_widget.set_unwatched_style()

    def delete_video(self, vid_id, item):
        self.cursor.execute("DELETE FROM videos WHERE id = ?", (vid_id,))
        self.conn.commit()
        
        list_widget = item.listWidget()
        row = list_widget.row(item)
        list_widget.takeItem(row)
        
        self.check_empty_state()

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
            
            self.cursor.execute("INSERT INTO videos (url, title, tab_index) VALUES (?, ?, ?)", (url, "Fetching title...", current_tab_index))
            self.conn.commit()
            last_id = self.cursor.lastrowid
            
            self.create_card_item(last_id, "Fetching title...", url, 0, current_tab_index)
            self.check_empty_state()
            
            threading.Thread(target=self.fetch_title, args=(url, last_id, current_tab_index), daemon=True).start()

    def fetch_title(self, url, vid_id, tab_index):
        try:
            headers = {'User-Agent': 'Mozilla/5.0'}
            response = requests.get(url, headers=headers, timeout=5)
            soup = BeautifulSoup(response.text, 'html.parser')
            title = url
            if soup.title:
                title = soup.title.string.replace("- YouTube", "").strip()
            
            self.update_title_signal.emit(title, vid_id, tab_index)
        except:
            pass

    def update_item_title(self, title, vid_id, tab_index):
        self.cursor.execute("UPDATE videos SET title = ? WHERE id = ?", (title, vid_id))
        self.conn.commit()
        
        target_list = self.tab_lists[tab_index]
        for i in range(target_list.count()):
            item = target_list.item(i)
            widget = target_list.itemWidget(item)
            if widget.vid_id == vid_id:
                widget.title_lbl.setText(title)
                break

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