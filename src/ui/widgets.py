import webbrowser
from PyQt6.QtWidgets import (QWidget, QLabel, QPushButton, QHBoxLayout, QFrame, 
                             QListWidget, QAbstractItemView, QListWidgetItem)
from PyQt6.QtCore import Qt, QSize, QRectF
from PyQt6.QtGui import QColor, QCursor, QPainter, QBrush

# --- 1. ÖZEL TUTMA YERİ (6 NOKTA) ---
class DragHandle(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(12, 24) 
        self.setCursor(Qt.CursorShape.SizeAllCursor)
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QBrush(QColor(255, 255, 255, 80)))
        painter.setPen(Qt.PenStyle.NoPen)
        
        dot_size = 2.0
        gap = 4.0
        rows = 3
        cols = 2
        
        content_width = cols * dot_size + (cols - 1) * gap
        content_height = rows * dot_size + (rows - 1) * gap
        
        start_x = (self.width() - content_width) / 2
        start_y = (self.height() - content_height) / 2
        
        for row in range(rows):
            for col in range(cols):
                x = start_x + col * (dot_size + gap)
                y = start_y + row * (dot_size + gap)
                painter.drawEllipse(QRectF(x, y, dot_size, dot_size))

# --- 2. KART TASARIMI ---
class VideoCard(QFrame):
    def __init__(self, vid_id, title, url, watched, parent_window, list_item):
        super().__init__()
        self.vid_id = vid_id
        self.url = url
        self.watched = watched
        self.parent_window = parent_window
        self.list_item = list_item

        self.setObjectName("VideoCard")
        self.setStyleSheet("""
            QFrame#VideoCard {
                background-color: rgba(30, 30, 46, 0.6);
                border: 1px solid rgba(255, 255, 255, 0.05);
                border-radius: 6px;
            }
            QFrame#VideoCard:hover {
                background-color: rgba(40, 40, 60, 0.9);
                border: 1px solid rgba(0, 212, 255, 0.5);
            }
        """)

        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(5, 2, 4, 2) 
        self.layout.setSpacing(2)

        self.drag_handle = DragHandle()
        self.layout.addWidget(self.drag_handle)

        self.title_lbl = QLabel(title)
        self.title_lbl.setStyleSheet("border: none; background: transparent; color: #e0e0e0; font-family: 'Segoe UI'; font-size: 12px; font-weight: 500; margin-left: 2px;")
        if watched: self.set_watched_style()
        self.layout.addWidget(self.title_lbl, stretch=1)

        self.del_btn = QPushButton("×")
        self.del_btn.setFixedSize(18, 18)
        self.del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.del_btn.setStyleSheet("""
            QPushButton { background-color: transparent; color: #555; border-radius: 9px; border: none; font-weight: bold; font-size: 14px; padding-bottom: 2px; }
            QPushButton:hover { background-color: rgba(255, 71, 87, 0.8); color: white; }
        """)
        self.del_btn.clicked.connect(self.delete_clicked)
        self.layout.addWidget(self.del_btn)

    def set_watched_style(self):
        font = self.title_lbl.font()
        font.setStrikeOut(True)
        self.title_lbl.setFont(font)
        self.title_lbl.setStyleSheet("border: none; background: transparent; color: #555;")

    def set_unwatched_style(self):
        font = self.title_lbl.font()
        font.setStrikeOut(False)
        self.title_lbl.setFont(font)
        self.title_lbl.setStyleSheet("border: none; background: transparent; color: #e0e0e0;")

    def delete_clicked(self):
        self.parent_window.delete_video(self.vid_id, self.list_item)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
             child = self.childAt(event.pos())
             if child != self.drag_handle:
                if self.url:
                    webbrowser.open(self.url)
                    self.parent_window.mark_as_watched(self.vid_id, self)
        elif event.button() == Qt.MouseButton.RightButton:
            self.parent_window.mark_as_unwatched(self.vid_id, self)
        super().mousePressEvent(event)

# --- 3. SÜRÜKLENEBİLİR LİSTE ---
class DraggableListWidget(QListWidget):
    def __init__(self, parent_window, tab_index):
        super().__init__()
        self.parent_window = parent_window
        self.tab_index = tab_index
        
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        
        self.setSpacing(3)
        self.setStyleSheet("""
            QListWidget { background: transparent; border: none; outline: none; }
            QListWidget::item { background: transparent; border: none; padding: 0px; }
            QListWidget::item:hover { background: transparent; }
            QListWidget::item:selected { background: transparent; }
        """)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

    def dropEvent(self, event):
        super().dropEvent(event)
        for i in range(self.count()):
            item = self.item(i)
            if self.itemWidget(item) is None:
                vid_id = item.data(Qt.ItemDataRole.UserRole + 1)
                url = item.data(Qt.ItemDataRole.UserRole)
                watched = item.data(Qt.ItemDataRole.UserRole + 2)
                title = item.data(Qt.ItemDataRole.UserRole + 3)
                if title is None: title = "Loading..."
                
                card = VideoCard(vid_id, title, url, watched, self.parent_window, item)
                item.setSizeHint(QSize(0, 40))
                self.setItemWidget(item, card)
        
        self.update_db_order()

    def update_db_order(self):
        for i in range(self.count()):
            item = self.item(i)
            vid_id = item.data(Qt.ItemDataRole.UserRole + 1)
            if vid_id:
                self.parent_window.update_video_order(vid_id, i)