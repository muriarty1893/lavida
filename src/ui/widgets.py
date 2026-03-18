import os
import webbrowser
from PyQt6.QtWidgets import (QWidget, QLabel, QPushButton, QHBoxLayout, QFrame,
                             QListWidget, QAbstractItemView, QListWidgetItem, QCheckBox,
                             QLayout, QSizePolicy)
from PyQt6.QtCore import Qt, QSize, QRectF, QTimer, QPoint, QRect
from PyQt6.QtGui import QColor, QCursor, QPainter, QBrush, QPixmap

import src.theme as theme


class FlowLayout(QLayout):
    """Layout that wraps items to the next row when they don't fit."""

    def __init__(self, parent=None, spacing=4):
        super().__init__(parent)
        self._items = []
        self._spacing = spacing

    def addItem(self, item):
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, index):
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index):
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._do_layout(QRect(0, 0, width, 0), test_only=True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._do_layout(rect, test_only=False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        m = self.contentsMargins()
        size += QSize(m.left() + m.right(), m.top() + m.bottom())
        return size

    def _do_layout(self, rect, test_only):
        m = self.contentsMargins()
        effective = rect.adjusted(m.left(), m.top(), -m.right(), -m.bottom())
        x = effective.x()
        y = effective.y()
        row_height = 0

        for item in self._items:
            w = item.sizeHint().width()
            h = item.sizeHint().height()

            if x + w > effective.right() + 1 and x > effective.x():
                x = effective.x()
                y += row_height + self._spacing
                row_height = 0

            if not test_only:
                item.setGeometry(QRect(x, y, w, h))

            x += w + self._spacing
            row_height = max(row_height, h)

        return y + row_height - rect.y() + m.bottom()


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
        self.setStyleSheet(f"""
            QLabel {{
                background: {theme.CLR_SURFACE};
                border: 1px solid {theme.CLR_BORDER};
                border-radius: 10px;
                padding: 4px;
            }}
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
        self.setFixedSize(8, 20)
        self.setCursor(Qt.CursorShape.SizeAllCursor)

    def paintEvent(self, event):
        card = self.parent()
        if hasattr(card, '_card_hovered') and not card._card_hovered:
            return
        if hasattr(card, 'checkbox') and card.checkbox.isVisible():
            return
        if hasattr(card, 'is_history') and card.is_history:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = QColor(theme.CLR_TEXT_MUTED)
        color.setAlpha(100)
        painter.setBrush(QBrush(color))
        painter.setPen(Qt.PenStyle.NoPen)

        dot_size = 2.0
        gap = 3.5
        rows = 4
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
    def __init__(self, vid_id, title, url, watched, parent_window, list_item, is_history=False, row_index=0):
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
        self._card_hovered = False

        self.setObjectName("VideoCard")
        self.apply_row_style(row_index)

        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(6, 4, 6, 4)
        self.layout.setSpacing(8)

        self.checkbox = QCheckBox()
        self.checkbox.setStyleSheet("QCheckBox { margin-left: 4px; }")
        self.checkbox.hide()
        self.layout.addWidget(self.checkbox)

        self.drag_handle = DragHandle()
        self.layout.addWidget(self.drag_handle)

        self.thumb_lbl = QLabel()
        self.thumb_lbl.setFixedSize(64, 36)
        self.thumb_lbl.setStyleSheet(f"""
            background: {theme.CLR_BASE};
            border-radius: 6px;
        """)
        self.thumb_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.thumb_lbl)

        self.title_lbl = QLabel(title)
        self.title_lbl.setStyleSheet(f"""
            color: {theme.CLR_TEXT};
            font-size: 13px;
            font-weight: 500;
        """)
        if watched: self.set_watched_style()
        self.layout.addWidget(self.title_lbl, stretch=1)

        if is_history:
            self.restore_btn = QPushButton("Restore")
            self.restore_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.restore_btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    color: {theme.CLR_TEXT_MUTED};
                    border: 1px solid transparent;
                    border-radius: 4px;
                    font-size: 10px;
                    font-weight: 600;
                    padding: 2px 8px;
                }}
                QPushButton:hover {{
                    color: {theme.CLR_ACCENT};
                    background: {theme.accent_rgba(0.10)};
                    border: 1px solid {theme.accent_rgba(0.15)};
                }}
            """)
            self.restore_btn.clicked.connect(self.restore_clicked)
            self.layout.addWidget(self.restore_btn)

        self.del_btn = QPushButton("\u00d7")
        self.del_btn.setFixedSize(24, 24)
        self.del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.del_btn.setStyleSheet(self._del_btn_hidden_style())
        self.del_btn.clicked.connect(self.delete_clicked)
        self.layout.addWidget(self.del_btn)

    def set_select_mode(self, enabled):
        if enabled:
            self.checkbox.show()
        else:
            self.checkbox.hide()
            self.checkbox.setChecked(False)

    def is_checked(self):
        return self.checkbox.isChecked()

    def _del_btn_hidden_style(self):
        return f"""
            QPushButton {{
                background: transparent;
                color: transparent;
                border: none;
                border-radius: 6px;
                font-size: 16px;
                font-weight: 500;
            }}
        """

    def _del_btn_visible_style(self):
        return f"""
            QPushButton {{
                background: transparent;
                color: {theme.CLR_TEXT_MUTED};
                border: none;
                border-radius: 6px;
                font-size: 16px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                color: #e05252;
                background: rgba(224, 82, 82, 0.12);
            }}
        """

    def apply_row_style(self, row_index):
        bg = theme.CLR_CARD_BG if row_index % 2 == 0 else theme.CLR_CARD_BG_ALT
        self.setStyleSheet(f"""
            QFrame#VideoCard {{
                background: {bg};
                border: 1px solid rgba(255,255,255,0.04);
                border-radius: 10px;
                margin: 0px 2px;
            }}
            QFrame#VideoCard:hover {{
                background: {theme.CLR_CARD_HOVER};
                border: 1px solid rgba(255,255,255,0.07);
            }}
        """)

    def set_watched_style(self):
        font = self.title_lbl.font()
        font.setStrikeOut(True)
        self.title_lbl.setFont(font)
        self.title_lbl.setStyleSheet(f"""
            color: {theme.CLR_TEXT_MUTED};
            font-size: 13px;
            font-weight: 500;
        """)

    def set_unwatched_style(self):
        font = self.title_lbl.font()
        font.setStrikeOut(False)
        self.title_lbl.setFont(font)
        self.title_lbl.setStyleSheet(f"""
            color: {theme.CLR_TEXT};
            font-size: 13px;
            font-weight: 500;
        """)

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
                    pixmap.scaled(64, 36, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                  Qt.TransformationMode.SmoothTransformation)
                )
                self.thumb_lbl.setStyleSheet("border-radius: 6px;")

    def enterEvent(self, event):
        self._card_hovered = True
        self.drag_handle.update()
        self.del_btn.setStyleSheet(self._del_btn_visible_style())
        if self._thumb_path:
            self._hover_timer.start()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._card_hovered = False
        self.drag_handle.update()
        self.del_btn.setStyleSheet(self._del_btn_hidden_style())
        self._hover_timer.stop()
        ThumbnailPreview.instance().hide()
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

        self.setSpacing(3)
        self.setStyleSheet(f"""
            QListWidget {{
                background: transparent;
                border: none;
                outline: none;
            }}
            QListWidget::item {{
                background: transparent;
                border: none;
                border-radius: 10px;
                padding: 0px;
            }}
            QListWidget::item:hover {{
                background: transparent;
            }}
            QListWidget::item:selected {{
                background: transparent;
            }}
            QScrollBar:vertical {{
                width: 6px;
                background: transparent;
                border: none;
                margin: 0px;
            }}
            QScrollBar::handle:vertical {{
                background: rgba(255,255,255,0.10);
                border-radius: 3px;
                min-height: 30px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: rgba(255,255,255,0.18);
            }}
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
            QScrollBar::add-page:vertical,
            QScrollBar::sub-page:vertical {{
                background: transparent;
            }}
        """)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

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

                card = VideoCard(vid_id, title, url, watched, self.parent_window, item, row_index=i)
                if thumb_path:
                    card.set_thumbnail(thumb_path)
                item.setSizeHint(QSize(0, 46))
                self.setItemWidget(item, card)
            else:
                self.itemWidget(item).apply_row_style(i)

        self.update_db_order()

    def update_db_order(self):
        for i in range(self.count()):
            item = self.item(i)
            vid_id = item.data(Qt.ItemDataRole.UserRole + 1)
            if vid_id:
                self.parent_window.update_video_order(vid_id, i)
