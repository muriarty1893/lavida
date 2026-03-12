import os
import webbrowser
from PyQt6.QtWidgets import (QWidget, QLabel, QPushButton, QHBoxLayout, QFrame,
                             QListWidget, QAbstractItemView, QListWidgetItem)
from PyQt6.QtCore import Qt, QSize, QRectF, QTimer, QPoint
from PyQt6.QtGui import QColor, QCursor, QPainter, QBrush, QPixmap


class ThumbnailPreview(QLabel):
    """Floating popup that shows a larger thumbnail on hover."""
    _instance = None

    @classmethod
    def instance(cls):
        if cls._instance is None or not cls._instance.isVisible:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        super().__init__(None)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.ToolTip
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(248, 148)
        self.setStyleSheet("""
            QLabel {
                background: #2d2926;
                border: 1px solid #3e3832;
                border-radius: 6px;
                padding: 4px;
            }
        """)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hide()

    def show_at(self, pixmap, global_pos):
        scaled = pixmap.scaled(
            480, 280,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        self.setPixmap(scaled)
        self.setFixedSize(scaled.width() + 8, scaled.height() + 8)
        self.move(global_pos)
        self.show()

class DragHandle(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(10, 20)
        self.setCursor(Qt.CursorShape.SizeAllCursor)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QBrush(QColor(155, 146, 135, 80)))
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

class VideoCard(QFrame):
    def __init__(self, vid_id, title, url, watched, parent_window, list_item, is_history=False):
        super().__init__()
        self.vid_id = vid_id
        self.url = url
        self.watched = watched
        self.parent_window = parent_window
        self.list_item = list_item
        self.is_history = is_history
        self._thumb_path = None
        self._hover_timer = QTimer(self)
        self._hover_timer.setSingleShot(True)
        self._hover_timer.setInterval(350)
        self._hover_timer.timeout.connect(self._show_preview)

        self.setObjectName("VideoCard")
        self.setStyleSheet("""
            QFrame#VideoCard {
                background: transparent;
                border: none;
                border-bottom: 1px solid #3e3832;
            }
            QFrame#VideoCard:hover {
                background: #35302b;
            }
        """)

        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(4, 2, 4, 2)
        self.layout.setSpacing(6)

        self.drag_handle = DragHandle()
        self.layout.addWidget(self.drag_handle)

        self.thumb_lbl = QLabel()
        self.thumb_lbl.setFixedSize(48, 36)
        self.thumb_lbl.setStyleSheet("background: #1e1b18; border-radius: 3px;")
        self.thumb_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.thumb_lbl)

        self.title_lbl = QLabel(title)
        self.title_lbl.setStyleSheet("color: #ece5da; font-size: 13px; font-weight: 400;")
        if watched: self.set_watched_style()
        self.layout.addWidget(self.title_lbl, stretch=1)

        if is_history:
            self.restore_btn = QPushButton("restore")
            self.restore_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.restore_btn.setStyleSheet("""
                QPushButton { background: transparent; color: #6b6259; border: none; font-size: 11px; font-weight: 500; padding: 2px 6px; }
                QPushButton:hover { color: #ece5da; }
            """)
            self.restore_btn.clicked.connect(self.restore_clicked)
            self.layout.addWidget(self.restore_btn)

        self.del_btn = QPushButton("×")
        self.del_btn.setFixedSize(16, 16)
        self.del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.del_btn.setStyleSheet("""
            QPushButton { background: transparent; color: #6b6259; border: none; font-size: 15px; }
            QPushButton:hover { color: #ece5da; }
        """)
        self.del_btn.clicked.connect(self.delete_clicked)
        self.layout.addWidget(self.del_btn)

    def set_watched_style(self):
        font = self.title_lbl.font()
        font.setStrikeOut(True)
        self.title_lbl.setFont(font)
        self.title_lbl.setStyleSheet("color: #6b6259; font-size: 13px; font-weight: 400;")

    def set_unwatched_style(self):
        font = self.title_lbl.font()
        font.setStrikeOut(False)
        self.title_lbl.setFont(font)
        self.title_lbl.setStyleSheet("color: #ece5da; font-size: 13px; font-weight: 400;")

    def delete_clicked(self):
        self.parent_window.delete_video(self.vid_id, self.list_item)

    def restore_clicked(self):
        self.parent_window.restore_video(self.vid_id, self.list_item)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
             child = self.childAt(event.pos())
             if child != self.drag_handle:
                if self.url:
                    webbrowser.open(self.url)
                    self.parent_window.mark_as_watched(self.vid_id, self)
                    self.parent_window.hide()
        elif event.button() == Qt.MouseButton.RightButton:
            self.parent_window.mark_as_unwatched(self.vid_id, self)
        elif event.button() == Qt.MouseButton.MiddleButton:
            self.delete_clicked()
        super().mousePressEvent(event)

    def set_thumbnail(self, path):
        if path and os.path.exists(path):
            pixmap = QPixmap(path)
            if not pixmap.isNull():
                self._thumb_path = path
                self.thumb_lbl.setPixmap(
                    pixmap.scaled(48, 36, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                  Qt.TransformationMode.SmoothTransformation)
                )
                self.thumb_lbl.setStyleSheet("border-radius: 3px;")

    def enterEvent(self, event):
        if self._thumb_path:
            self._hover_timer.start()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hover_timer.stop()
        preview = ThumbnailPreview.instance()
        preview.hide()
        super().leaveEvent(event)

    def _show_preview(self):
        if not self._thumb_path or not os.path.exists(self._thumb_path):
            return
        pixmap = QPixmap(self._thumb_path)
        if pixmap.isNull():
            return
        preview = ThumbnailPreview.instance()
        # Position to the right of the main window
        main_win = self.parent_window
        win_rect = main_win.geometry()
        card_global_y = self.mapToGlobal(QPoint(0, 0)).y()
        popup_x = win_rect.x() + win_rect.width() + 6
        popup_y = card_global_y - 40
        preview.show_at(pixmap, QPoint(popup_x, popup_y))

class DraggableListWidget(QListWidget):
    def __init__(self, parent_window, tab_index):
        super().__init__()
        self.parent_window = parent_window
        self.tab_index = tab_index

        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)

        self.setSpacing(1)
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
                thumb_path = item.data(Qt.ItemDataRole.UserRole + 4)
                if title is None: title = "Loading..."

                card = VideoCard(vid_id, title, url, watched, self.parent_window, item)
                if thumb_path:
                    card.set_thumbnail(thumb_path)
                item.setSizeHint(QSize(0, 48))
                self.setItemWidget(item, card)

        self.update_db_order()

    def update_db_order(self):
        for i in range(self.count()):
            item = self.item(i)
            vid_id = item.data(Qt.ItemDataRole.UserRole + 1)
            if vid_id:
                self.parent_window.update_video_order(vid_id, i)
