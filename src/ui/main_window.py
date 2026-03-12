import os
import re
import sqlite3
import subprocess
import requests
import threading
from bs4 import BeautifulSoup

from PyQt6.QtWidgets import (QMainWindow, QWidget, QLabel, QPushButton, QTabWidget,
                             QVBoxLayout, QHBoxLayout, QFrame,
                             QApplication, QListWidgetItem, QLineEdit)
from PyQt6.QtCore import Qt, pyqtSignal, QPoint, QSize, QTimer

from src.workers import GlobalInputListener
from src.ui.widgets import VideoCard, DraggableListWidget

class LavidaApp(QMainWindow):
    update_title_signal = pyqtSignal(str, str, int, int)

    def __init__(self):
        super().__init__()
        
        self.setWindowTitle("Lavida")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | 
                            Qt.WindowType.WindowStaysOnTopHint | 
                            Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        self.setMinimumSize(300, 400) 
        self.resize(340, 600)         
        
        self.setAcceptDrops(True)
        self.setMouseTracking(True) 

        self.init_db()
        
        if not self.load_settings():
            self.position_left_center()

        self.setup_ui()
        self.load_data()

        self.update_title_signal.connect(self.update_item_title)

        self.listener = GlobalInputListener()
        self.listener.toggle_signal.connect(self.toggle_visibility)
        self.listener.start()
        
        self.resize_margin = 10       
        self.current_edge = None      
        self.is_resizing = False      
        self.old_pos = None           

        self._hidden_by_fullscreen = False
        self._fullscreen_timer = QTimer(self)
        self._fullscreen_timer.setInterval(100)
        self._fullscreen_timer.timeout.connect(self._check_fullscreen)
        self._fullscreen_timer.start()

    def position_left_center(self):
        screen = QApplication.primaryScreen().geometry()
        new_y = (screen.height() - self.height()) // 2
        self.move(20, new_y)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.current_edge = self.check_edge(event.pos())
            
            if self.current_edge:
                self.is_resizing = True
                self.start_geometry = self.geometry()      
                self.start_mouse_pos = event.globalPosition() 
            else:
                self.is_resizing = False
                self.old_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        if not self.is_resizing and not self.old_pos:
            edge = self.check_edge(event.pos())
            self.set_cursor_shape(edge)
            return

        if self.is_resizing:
            delta = event.globalPosition() - self.start_mouse_pos
            geom = self.start_geometry
            
            x, y, w, h = geom.x(), geom.y(), geom.width(), geom.height()
            dx, dy = delta.x(), delta.y()

            if "LEFT" in self.current_edge:
                x += dx
                w -= dx
            if "RIGHT" in self.current_edge:
                w += dx
            if "TOP" in self.current_edge:
                y += dy
                h -= dy
            if "BOTTOM" in self.current_edge:
                h += dy
            
            if w > self.minimumWidth() and h > self.minimumHeight():
                self.setGeometry(int(x), int(y), int(w), int(h))

        elif self.old_pos:
            delta = QPoint(event.globalPosition().toPoint() - self.old_pos)
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.old_pos = event.globalPosition().toPoint()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_resizing = False
            self.old_pos = None
            self.current_edge = None
            self.setCursor(Qt.CursorShape.ArrowCursor)
            self.save_settings() 

    def check_edge(self, pos):
        x, y = pos.x(), pos.y()
        w, h = self.width(), self.height()
        m = self.resize_margin
        
        edge = ""
        if y < m: edge += "TOP"
        elif y > h - m: edge += "BOTTOM"
        
        if x < m: edge += "LEFT"
        elif x > w - m: edge += "RIGHT"
        
        return edge if edge else None

    def set_cursor_shape(self, edge):
        if not edge:
            self.setCursor(Qt.CursorShape.ArrowCursor)
            return

        if edge in ["TOPLEFT", "BOTTOMRIGHT"]:
            self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        elif edge in ["TOPRIGHT", "BOTTOMLEFT"]:
            self.setCursor(Qt.CursorShape.SizeBDiagCursor)
        elif edge in ["LEFT", "RIGHT"]:
            self.setCursor(Qt.CursorShape.SizeHorCursor)
        elif edge in ["TOP", "BOTTOM"]:
            self.setCursor(Qt.CursorShape.SizeVerCursor)

    def save_settings(self):
        self.cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('pos_x', ?)", (str(self.x()),))
        self.cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('pos_y', ?)", (str(self.y()),))
        self.cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('width', ?)", (str(self.width()),))
        self.cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('height', ?)", (str(self.height()),))
        self.conn.commit()

    def load_settings(self):
        try:
            self.cursor.execute("SELECT value FROM settings WHERE key='pos_x'")
            row_x = self.cursor.fetchone()
            self.cursor.execute("SELECT value FROM settings WHERE key='pos_y'")
            row_y = self.cursor.fetchone()
            
            self.cursor.execute("SELECT value FROM settings WHERE key='width'")
            row_w = self.cursor.fetchone()
            self.cursor.execute("SELECT value FROM settings WHERE key='height'")
            row_h = self.cursor.fetchone()

            if row_x and row_y:
                self.move(int(row_x[0]), int(row_y[0]))

            if row_w and row_h:
                self.resize(int(row_w[0]), int(row_h[0]))

            return (row_x is not None)
        except Exception:
            return False

    def init_db(self):
        db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "lavida.db")
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()
        
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS videos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT,
                title TEXT,
                watched INTEGER DEFAULT 0,
                tab_index INTEGER DEFAULT 0,
                row_order INTEGER DEFAULT 0,
                is_deleted INTEGER DEFAULT 0
            )
        """)
        try: self.cursor.execute("ALTER TABLE videos ADD COLUMN tab_index INTEGER DEFAULT 0")
        except sqlite3.OperationalError: pass
        try: self.cursor.execute("ALTER TABLE videos ADD COLUMN row_order INTEGER DEFAULT 0")
        except sqlite3.OperationalError: pass
        try: self.cursor.execute("ALTER TABLE videos ADD COLUMN is_deleted INTEGER DEFAULT 0")
        except sqlite3.OperationalError: pass
        try: self.cursor.execute("ALTER TABLE videos ADD COLUMN thumbnail_path TEXT DEFAULT ''")
        except sqlite3.OperationalError: pass
        
        self.cursor.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
        self.conn.commit()

        self.thumbnails_dir = os.path.join(os.path.dirname(db_path), "thumbnails")
        os.makedirs(self.thumbnails_dir, exist_ok=True)

    BTN_STYLE = """
        QPushButton {
            background: transparent;
            color: #9b9287;
            border: none;
            font-size: 12px;
            font-weight: 500;
            padding: 4px 10px;
        }
        QPushButton:hover { color: #ece5da; }
    """

    def setup_ui(self):
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)

        self.layout = QVBoxLayout(self.central_widget)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        self.central_widget.setStyleSheet("QWidget { font-family: 'Segoe UI', sans-serif; }")

        self.main_frame = QFrame()
        self.main_frame.setObjectName("MainFrame")
        self.main_frame.setStyleSheet("""
            QFrame#MainFrame {
                background: #2d2926;
                border-radius: 8px;
            }
        """)
        self.layout.addWidget(self.main_frame)

        self.frame_layout = QVBoxLayout(self.main_frame)
        self.frame_layout.setContentsMargins(12, 10, 12, 12)
        self.frame_layout.setSpacing(0)

        top_bar = QHBoxLayout()
        top_bar.setSpacing(0)

        add_btn = QPushButton("Add Curr Vid")
        add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_btn.clicked.connect(self.add_current_video)
        add_btn.setStyleSheet(self.BTN_STYLE)
        top_bar.addWidget(add_btn)

        top_bar.addStretch()

        search_btn = QPushButton("Search")
        search_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        search_btn.clicked.connect(self.toggle_search)
        search_btn.setStyleSheet(self.BTN_STYLE)
        top_bar.addWidget(search_btn)

        close_btn = QPushButton("Close")
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(self.hide)
        close_btn.setStyleSheet(self.BTN_STYLE)
        top_bar.addWidget(close_btn)

        disable_btn = QPushButton("Disable")
        disable_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        disable_btn.clicked.connect(self.close_application)
        disable_btn.setStyleSheet(self.BTN_STYLE)
        top_bar.addWidget(disable_btn)

        self.frame_layout.addLayout(top_bar)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("search...")
        self.search_input.setStyleSheet("""
            QLineEdit {
                background: transparent;
                border: none;
                border-bottom: 1px solid #3e3832;
                color: #ece5da;
                padding: 6px 2px;
                font-size: 13px;
            }
            QLineEdit:focus {
                border-bottom: 1px solid #6b6259;
            }
        """)
        self.search_input.textChanged.connect(self.filter_videos)
        self.search_input.hide()
        self.frame_layout.addWidget(self.search_input)

        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane { border: none; background: transparent; margin-top: 10px; }
            QTabBar::tab {
                background: transparent;
                color: #6b6259;
                padding: 5px 0px;
                width: 54px;
                height: 24px;
                margin-right: 8px;
                font-weight: 500;
                font-size: 12px;
                border: none;
                border-bottom: 1px solid transparent;
            }
            QTabBar::tab:selected {
                color: #ece5da;
                border-bottom: 1px solid #c96442;
            }
            QTabBar::tab:hover { color: #9b9287; }
        """)

        self.tab_lists = []
        for i in range(1, 4):
            lst = DraggableListWidget(self, i)
            self.tab_lists.append(lst)
            self.tabs.addTab(lst, f"tab {i}")

        self.history_list = DraggableListWidget(self, 99)
        self.tab_lists.append(self.history_list)
        self.tabs.addTab(self.history_list, "history")

        self.tabs.currentChanged.connect(lambda: self.filter_videos(self.search_input.text()))
        self.frame_layout.addWidget(self.tabs)

        self.empty_lbl = QLabel("drop youtube links here")
        self.empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_lbl.setStyleSheet("color: #6b6259; font-size: 13px; border: none;")
        self.frame_layout.addWidget(self.empty_lbl)
        self.empty_lbl.hide()

    def toggle_search(self):
        if self.search_input.isVisible():
            self.search_input.clear()
            self.search_input.hide()
        else:
            self.search_input.show()
            self.search_input.setFocus()

    def filter_videos(self, text):
        text = text.lower()
        for tab_list in self.tab_lists:
            for i in range(tab_list.count()):
                item = tab_list.item(i)
                title = item.data(Qt.ItemDataRole.UserRole + 3) or ""
                item.setHidden(text not in title.lower())

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape and self.search_input.isVisible():
            self.search_input.clear()
            self.search_input.hide()
        else:
            super().keyPressEvent(event)

    def check_empty_state(self):
        total_items = sum(lst.count() for lst in self.tab_lists)
        if total_items == 0:
            self.empty_lbl.show()
            self.tabs.hide()
        else:
            self.empty_lbl.hide()
            self.tabs.show()

    def close_application(self):
        self.save_settings()
        QApplication.quit()

    def update_video_order(self, vid_id, new_order):
        self.cursor.execute("UPDATE videos SET row_order = ? WHERE id = ?", (new_order, vid_id))
        self.conn.commit()

    def load_data(self):
        for lst in self.tab_lists: lst.clear()
        
        self.cursor.execute("SELECT id, title, url, watched, tab_index, thumbnail_path FROM videos WHERE is_deleted=0 ORDER BY row_order ASC, id DESC")
        for vid_id, title, url, watched, tab_index, thumb_path in self.cursor.fetchall():
            target_index = tab_index if tab_index < 3 else 0
            self.create_card_item(vid_id, title, url, watched, self.tab_lists[target_index], thumbnail_path=thumb_path)

        self.cursor.execute("SELECT id, title, url, watched, thumbnail_path FROM videos WHERE is_deleted=1 ORDER BY id DESC")
        for vid_id, title, url, watched, thumb_path in self.cursor.fetchall():
            self.create_card_item(vid_id, title, url, watched, self.history_list, thumbnail_path=thumb_path)

        self.check_empty_state()

    def create_card_item(self, vid_id, title, url, watched, target_list, insert_top=False, thumbnail_path=""):
        if insert_top:
            item = QListWidgetItem()
            target_list.insertItem(0, item)
        else:
            item = QListWidgetItem(target_list)
            
        item.setSizeHint(QSize(0, 48))
        item.setData(Qt.ItemDataRole.UserRole, url)
        item.setData(Qt.ItemDataRole.UserRole + 1, vid_id)
        item.setData(Qt.ItemDataRole.UserRole + 2, watched)
        item.setData(Qt.ItemDataRole.UserRole + 3, title)
        item.setData(Qt.ItemDataRole.UserRole + 4, thumbnail_path or "")
        is_history = (target_list == self.history_list)
        card = VideoCard(vid_id, title, url, watched, self, item, is_history=is_history)
        if thumbnail_path:
            card.set_thumbnail(thumbnail_path)
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
        list_widget = item.listWidget()
        
        if list_widget == self.history_list:
            self.cursor.execute("DELETE FROM videos WHERE id = ?", (vid_id,))
            self.conn.commit()
            row = list_widget.row(item)
            list_widget.takeItem(row)
        else:
            self.cursor.execute("UPDATE videos SET is_deleted=1 WHERE id = ?", (vid_id,))
            self.conn.commit()
            
            row = list_widget.row(item)
            list_widget.takeItem(row)
            
            title = item.data(Qt.ItemDataRole.UserRole + 3)
            url = item.data(Qt.ItemDataRole.UserRole)
            watched = item.data(Qt.ItemDataRole.UserRole + 2)
            thumb_path = item.data(Qt.ItemDataRole.UserRole + 4) or ""
            self.create_card_item(vid_id, title, url, watched, self.history_list, thumbnail_path=thumb_path)

        self.check_empty_state()

    def restore_video(self, vid_id, item):
        self.cursor.execute("SELECT tab_index FROM videos WHERE id = ?", (vid_id,))
        row = self.cursor.fetchone()
        target_tab = row[0] if row and row[0] < 3 else 0

        self.cursor.execute("UPDATE videos SET is_deleted=0 WHERE id = ?", (vid_id,))
        self.conn.commit()

        list_widget = item.listWidget()
        list_widget.takeItem(list_widget.row(item))

        title = item.data(Qt.ItemDataRole.UserRole + 3)
        url = item.data(Qt.ItemDataRole.UserRole)
        watched = item.data(Qt.ItemDataRole.UserRole + 2)
        thumb_path = item.data(Qt.ItemDataRole.UserRole + 4) or ""
        self.create_card_item(vid_id, title, url, watched, self.tab_lists[target_tab], insert_top=True, thumbnail_path=thumb_path)
        self.check_empty_state()

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls() or event.mimeData().hasText(): event.accept()
        else: event.ignore()

    def dropEvent(self, event):
        url = ""
        if event.mimeData().hasUrls(): url = event.mimeData().urls()[0].toString()
        elif event.mimeData().hasText(): url = event.mimeData().text()
        
        if "youtube.com" in url or "youtu.be" in url:
            self._add_video_url(url)

    def _add_video_url(self, url):
        if self.tabs.currentIndex() == 3: 
            current_tab_index = 0
        else:
            current_tab_index = self.tabs.currentIndex()
        
        self.cursor.execute("SELECT MIN(row_order) FROM videos")
        min_val = self.cursor.fetchone()[0]
        new_order = (min_val if min_val is not None else 0) - 1
        
        self.cursor.execute("INSERT INTO videos (url, title, tab_index, row_order, is_deleted) VALUES (?, ?, ?, ?, 0)", (url, "Loading info...", current_tab_index, new_order))
        self.conn.commit()
        last_id = self.cursor.lastrowid
        
        self.create_card_item(last_id, "Loading info...", url, 0, self.tab_lists[current_tab_index], insert_top=True)
        self.check_empty_state()
        threading.Thread(target=self.fetch_title, args=(url, last_id, current_tab_index), daemon=True).start()

    def add_current_video(self):
        self.hide()
        QTimer.singleShot(150, self._grab_step_focus)

    def _grab_step_focus(self):
        try:
            subprocess.run(['xdotool', 'key', 'ctrl+l'], timeout=1)
        except Exception:
            self.show()
            return
        QTimer.singleShot(150, self._grab_step_copy)

    def _grab_step_copy(self):
        try:
            subprocess.run(['xdotool', 'key', 'ctrl+c'], timeout=1)
        except Exception:
            self.show()
            return
        QTimer.singleShot(150, self._grab_step_read)

    def _grab_step_read(self):
        try:
            subprocess.run(['xdotool', 'key', 'Escape'], timeout=1)
        except Exception:
            pass

        clipboard = QApplication.clipboard()
        url = clipboard.text().strip()

        if 'youtube.com' in url or 'youtu.be' in url:
            self._add_video_url(url)

        self.show()
        self.activateWindow()

    @staticmethod
    def extract_video_id(url):
        patterns = [
            r'(?:v=|/v/)([a-zA-Z0-9_-]{11})',
            r'youtu\.be/([a-zA-Z0-9_-]{11})',
            r'(?:embed|shorts)/([a-zA-Z0-9_-]{11})',
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None

    def fetch_title(self, url, vid_id, tab_index):
        title = url
        thumb_path = ""
        try:
            headers = {'User-Agent': 'Mozilla/5.0'}
            response = requests.get(url, headers=headers, timeout=5)
            soup = BeautifulSoup(response.text, 'html.parser')
            if soup.title: title = soup.title.string.replace("- YouTube", "").strip()
        except Exception:
            pass

        try:
            video_id = self.extract_video_id(url)
            if video_id:
                thumb_url = f"https://img.youtube.com/vi/{video_id}/mqdefault.jpg"
                resp = requests.get(thumb_url, timeout=5)
                if resp.status_code == 200:
                    thumb_path = os.path.join(self.thumbnails_dir, f"{video_id}.jpg")
                    with open(thumb_path, 'wb') as f:
                        f.write(resp.content)
        except Exception:
            pass

        self.update_title_signal.emit(title, thumb_path, vid_id, tab_index)

    def update_item_title(self, title, thumb_path, vid_id, tab_index):
        self.cursor.execute("UPDATE videos SET title = ?, thumbnail_path = ? WHERE id = ?", (title, thumb_path, vid_id))
        self.conn.commit()
        
        target_list = self.tab_lists[tab_index] if tab_index < 3 else self.history_list
        
        for i in range(target_list.count()):
            item = target_list.item(i)
            widget = target_list.itemWidget(item)
            if widget and widget.vid_id == vid_id:
                item.setData(Qt.ItemDataRole.UserRole + 3, title)
                item.setData(Qt.ItemDataRole.UserRole + 4, thumb_path)
                widget.title_lbl.setText(title)
                if thumb_path:
                    widget.set_thumbnail(thumb_path)
                break

    def toggle_visibility(self):
        if self.isHidden():
            self._hidden_by_fullscreen = False
            self.show()
            self.activateWindow()
        else:
            self.hide()

    def _check_fullscreen(self):
        try:
            result = subprocess.run(
                ['xprop', '-root', '_NET_ACTIVE_WINDOW'],
                capture_output=True, text=True, timeout=1
            )
            parts = result.stdout.strip().split()
            window_id = parts[-1] if parts else None
            if not window_id or window_id == '0x0':
                return

            result = subprocess.run(
                ['xprop', '-id', window_id, '_NET_WM_STATE'],
                capture_output=True, text=True, timeout=1
            )
            is_fullscreen = '_NET_WM_STATE_FULLSCREEN' in result.stdout

            if is_fullscreen and not self.isHidden():
                self._hidden_by_fullscreen = True
                self.hide()
            elif not is_fullscreen and self._hidden_by_fullscreen:
                self._hidden_by_fullscreen = False
                self.show()
        except Exception:
            pass