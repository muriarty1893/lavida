import sqlite3
import requests
import threading
from bs4 import BeautifulSoup

from PyQt6.QtWidgets import (QMainWindow, QWidget, QLabel, QPushButton, QTabWidget, 
                             QVBoxLayout, QHBoxLayout, QFrame, QListWidgetItem, 
                             QGraphicsDropShadowEffect, QApplication)
from PyQt6.QtCore import Qt, pyqtSignal, QSize, QPoint
from PyQt6.QtGui import QColor

# Kendi modüllerimizi çağırıyoruz
from src.workers import GlobalInputListener
from src.ui.widgets import VideoCard, DraggableListWidget

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

        self.init_db()
        if not self.load_window_position():
            self.position_left_center()

        self.setup_ui()
        self.load_data()

        self.update_title_signal.connect(self.update_item_title)

        self.listener = GlobalInputListener()
        self.listener.toggle_signal.connect(self.toggle_visibility)
        self.listener.start()
        
        self.old_pos = None

    def position_left_center(self):
        screen = QApplication.primaryScreen().geometry()
        new_y = (screen.height() - self.height()) // 2
        self.move(20, new_y)

    # --- Mouse Olayları (Pencere Taşıma) ---
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.old_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        if self.old_pos:
            delta = QPoint(event.globalPosition().toPoint() - self.old_pos)
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.old_pos = event.globalPosition().toPoint()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.old_pos = None
            self.save_window_position()

    # --- Ayarlar ve Veritabanı ---
    def save_window_position(self):
        x = self.x()
        y = self.y()
        self.cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('pos_x', ?)", (str(x),))
        self.cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('pos_y', ?)", (str(y),))
        self.conn.commit()

    def load_window_position(self):
        try:
            self.cursor.execute("SELECT value FROM settings WHERE key='pos_x'")
            row_x = self.cursor.fetchone()
            self.cursor.execute("SELECT value FROM settings WHERE key='pos_y'")
            row_y = self.cursor.fetchone()
            if row_x and row_y:
                self.move(int(row_x[0]), int(row_y[0]))
                return True
            return False
        except:
            return False

    def init_db(self):
        self.conn = sqlite3.connect("lavida.db", check_same_thread=False)
        self.cursor = self.conn.cursor()
        
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS videos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT,
                title TEXT,
                watched INTEGER DEFAULT 0,
                tab_index INTEGER DEFAULT 0,
                row_order INTEGER DEFAULT 0
            )
        """)
        try: self.cursor.execute("ALTER TABLE videos ADD COLUMN tab_index INTEGER DEFAULT 0")
        except: pass
        try: self.cursor.execute("ALTER TABLE videos ADD COLUMN row_order INTEGER DEFAULT 0")
        except: pass
        
        self.cursor.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
        self.conn.commit()

    # --- Arayüz Kurulumu ---
    def setup_ui(self):
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)
        self.layout.setContentsMargins(2, 2, 2, 2)
        self.layout.setSpacing(0)
        self.central_widget.setStyleSheet("QWidget { font-family: 'Segoe UI', sans-serif; }")

        self.main_frame = QFrame()
        self.main_frame.setObjectName("MainFrame")
        self.main_frame.setStyleSheet("""
            QFrame#MainFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #1e1e2e, stop:1 #161625);
                border-radius: 12px;
                border: 2px solid #00d4ff;
            }
        """)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 212, 255, 80))
        shadow.setOffset(0, 0)
        self.main_frame.setGraphicsEffect(shadow)

        self.frame_layout = QVBoxLayout(self.main_frame)
        self.frame_layout.setContentsMargins(12, 12, 12, 12)
        self.frame_layout.setSpacing(5)
        self.layout.addWidget(self.main_frame)

        # Header
        top_bar = QHBoxLayout()
        title_lbl = QLabel("LAVIDA")
        title_lbl.setStyleSheet("color: #00d4ff; font-weight: 900; font-size: 18px; letter-spacing: 2px; border: none; background: transparent;")
        top_bar.addWidget(title_lbl)
        top_bar.addStretch()

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(24, 24)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(self.close_application)
        close_btn.setStyleSheet("QPushButton { background-color: rgba(255, 255, 255, 0.05); color: white; border-radius: 12px; font-weight: bold; border: none; font-size: 12px; } QPushButton:hover { background-color: #ff4757; }")
        top_bar.addWidget(close_btn)
        self.frame_layout.addLayout(top_bar)

        # Tabs
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane { border: 0; background: transparent; margin-top: 15px; }
            QTabBar::tab { background: rgba(255, 255, 255, 0.05); color: #888; padding: 4px 0px; width: 50px; height: 22px; margin-right: 8px; border-radius: 11px; font-weight: bold; font-size: 11px; border: 1px solid transparent; }
            QTabBar::tab:selected { background: rgba(0, 212, 255, 0.15); color: #00d4ff; border: 1px solid rgba(0, 212, 255, 0.4); }
            QTabBar::tab:hover { background: rgba(255, 255, 255, 0.1); color: white; }
        """)

        self.tab_lists = []
        for i in range(1, 4):
            lst = DraggableListWidget(self, i)
            self.tab_lists.append(lst)
            self.tabs.addTab(lst, f"TAB {i}")

        self.frame_layout.addWidget(self.tabs)
        
        self.empty_lbl = QLabel("Drop YouTube links here")
        self.empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_lbl.setStyleSheet("color: rgba(255,255,255,30); font-size: 12px; font-weight: bold; border:none;")
        self.frame_layout.addWidget(self.empty_lbl)
        self.empty_lbl.hide()

    # --- İş Mantığı (Logic) ---
    def check_empty_state(self):
        total_items = sum(lst.count() for lst in self.tab_lists)
        if total_items == 0:
            self.empty_lbl.show()
            self.tabs.hide()
        else:
            self.empty_lbl.hide()
            self.tabs.show()

    def close_application(self):
        self.save_window_position()
        QApplication.quit()

    def update_video_order(self, vid_id, new_order):
        self.cursor.execute("UPDATE videos SET row_order = ? WHERE id = ?", (new_order, vid_id))
        self.conn.commit()

    def load_data(self):
        for lst in self.tab_lists: lst.clear()
        self.cursor.execute("SELECT id, title, url, watched, tab_index FROM videos ORDER BY row_order ASC, id DESC")
        for vid_id, title, url, watched, tab_index in self.cursor.fetchall():
            target_index = tab_index if tab_index < len(self.tab_lists) else 0
            self.create_card_item(vid_id, title, url, watched, target_index)
        self.check_empty_state()

    def create_card_item(self, vid_id, title, url, watched, tab_index):
        target_list = self.tab_lists[tab_index]
        item = QListWidgetItem(target_list)
        item.setSizeHint(QSize(0, 40))
        item.setData(Qt.ItemDataRole.UserRole, url)
        item.setData(Qt.ItemDataRole.UserRole + 1, vid_id)
        item.setData(Qt.ItemDataRole.UserRole + 2, watched)
        item.setData(Qt.ItemDataRole.UserRole + 3, title)
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
        if event.mimeData().hasUrls() or event.mimeData().hasText(): event.accept()
        else: event.ignore()

    def dropEvent(self, event):
        url = ""
        if event.mimeData().hasUrls(): url = event.mimeData().urls()[0].toString()
        elif event.mimeData().hasText(): url = event.mimeData().text()
        if "youtube.com" in url or "youtu.be" in url:
            current_tab_index = self.tabs.currentIndex()
            self.cursor.execute("SELECT MAX(row_order) FROM videos")
            max_order = self.cursor.fetchone()[0]
            new_order = (max_order if max_order else 0) + 1
            self.cursor.execute("INSERT INTO videos (url, title, tab_index, row_order) VALUES (?, ?, ?, ?)", (url, "Loading info...", current_tab_index, new_order))
            self.conn.commit()
            last_id = self.cursor.lastrowid
            self.create_card_item(last_id, "Loading info...", url, 0, current_tab_index)
            self.check_empty_state()
            threading.Thread(target=self.fetch_title, args=(url, last_id, current_tab_index), daemon=True).start()

    def fetch_title(self, url, vid_id, tab_index):
        try:
            headers = {'User-Agent': 'Mozilla/5.0'}
            response = requests.get(url, headers=headers, timeout=5)
            soup = BeautifulSoup(response.text, 'html.parser')
            title = url
            if soup.title: title = soup.title.string.replace("- YouTube", "").strip()
            self.update_title_signal.emit(title, vid_id, tab_index)
        except: pass

    def update_item_title(self, title, vid_id, tab_index):
        self.cursor.execute("UPDATE videos SET title = ? WHERE id = ?", (title, vid_id))
        self.conn.commit()
        target_list = self.tab_lists[tab_index]
        for i in range(target_list.count()):
            item = target_list.item(i)
            item.setData(Qt.ItemDataRole.UserRole + 3, title)
            widget = target_list.itemWidget(item)
            if widget and widget.vid_id == vid_id:
                widget.title_lbl.setText(title)
                break

    def toggle_visibility(self):
        if self.isHidden():
            self.show()
            self.activateWindow()
        else:
            self.hide()