import os
import webbrowser
from PyQt6.QtWidgets import (QWidget, QLabel, QPushButton, QHBoxLayout, QVBoxLayout, QFrame,
                             QListWidget, QAbstractItemView, QListWidgetItem, QCheckBox,
                             QLayout, QSizePolicy, QMenu, QApplication)
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
        self.layout.setContentsMargins(6, 2, 6, 2)
        self.layout.setSpacing(6)

        self.checkbox = QCheckBox()
        self.checkbox.setStyleSheet("QCheckBox { margin-left: 4px; }")
        self.checkbox.hide()
        self.layout.addWidget(self.checkbox)

        self.drag_handle = DragHandle()
        self.layout.addWidget(self.drag_handle)

        # Thumbnail container (for duration badge overlay)
        self._thumb_container = QWidget()
        self._thumb_container.setFixedSize(54, 30)
        self._thumb_container.setStyleSheet("background: transparent;")
        thumb_container_layout = QHBoxLayout(self._thumb_container)
        thumb_container_layout.setContentsMargins(0, 0, 0, 0)
        thumb_container_layout.setSpacing(0)

        self.thumb_lbl = QLabel()
        self.thumb_lbl.setFixedSize(54, 30)
        self.thumb_lbl.setStyleSheet(f"""
            background: {theme.CLR_BASE};
            border-radius: 6px;
        """)
        self.thumb_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        thumb_container_layout.addWidget(self.thumb_lbl)

        self.duration_lbl = QLabel()
        self.duration_lbl.setStyleSheet(f"""
            background: rgba(0, 0, 0, 0.75);
            color: #ffffff;
            font-size: 8px;
            font-weight: 600;
            border-radius: 3px;
            padding: 1px 3px;
        """)
        self.duration_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.duration_lbl.hide()

        self.layout.addWidget(self._thumb_container)

        # Title + channel vertical layout
        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(1)

        self.title_lbl = QLabel(title)
        self.title_lbl.setStyleSheet(f"""
            color: {theme.CLR_TEXT};
            font-size: 13px;
            font-weight: 500;
        """)
        if watched: self.set_watched_style()
        text_layout.addWidget(self.title_lbl)

        self.channel_lbl = QLabel()
        self.channel_lbl.setStyleSheet(f"""
            color: {theme.CLR_TEXT_DIM};
            font-size: 10px;
        """)
        self.channel_lbl.hide()
        text_layout.addWidget(self.channel_lbl)

        self.layout.addLayout(text_layout, stretch=1)

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
            self._show_context_menu(event.globalPosition().toPoint())
        elif event.button() == Qt.MouseButton.MiddleButton:
            self.delete_clicked()
        super().mousePressEvent(event)

    def _show_context_menu(self, global_pos):
        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{
                background: {theme.CLR_SURFACE};
                border: 1px solid {theme.CLR_BORDER};
                border-radius: 6px;
                padding: 4px;
            }}
            QMenu::item {{
                color: {theme.CLR_TEXT};
                padding: 6px 24px 6px 12px;
                border-radius: 4px;
                font-size: 12px;
            }}
            QMenu::item:selected {{
                background: {theme.accent_rgba(0.15)};
            }}
            QMenu::separator {{
                height: 1px;
                background: {theme.CLR_BORDER};
                margin: 4px 8px;
            }}
        """)

        if self.url:
            menu.addAction("Open in Browser", lambda: (
                webbrowser.open(self.url),
                self.parent_window.mark_as_watched(self.vid_id, self),
                self.parent_window.hide(),
            ))
            menu.addAction("Copy URL", lambda: QApplication.clipboard().setText(self.url))

        menu.addSeparator()

        if self.watched:
            menu.addAction("Mark Unwatched",
                           lambda: self.parent_window.mark_as_unwatched(self.vid_id, self))
        else:
            menu.addAction("Mark Watched",
                           lambda: self.parent_window.mark_as_watched(self.vid_id, self))

        if not self.is_history:
            tabs = self.parent_window.get_work_tabs_for_menu()
            current_tab_id = self.list_item.listWidget().tab_id if self.list_item.listWidget() else None
            if len(tabs) > 1:
                move_menu = menu.addMenu("Move to Tab")
                move_menu.setStyleSheet(menu.styleSheet())
                for tab_id, name in tabs:
                    if tab_id == current_tab_id:
                        continue
                    move_menu.addAction(name,
                                        lambda tid=tab_id: self.parent_window.move_video_to_tab(
                                            self.vid_id, self.list_item, tid))

        menu.addSeparator()

        if self.is_history:
            menu.addAction("Restore", self.restore_clicked)
            menu.addAction("Delete Permanently", self.delete_clicked)
        else:
            menu.addAction("Delete", self.delete_clicked)

        menu.exec(global_pos)

    def set_metadata(self, duration, channel):
        if duration:
            self.duration_lbl.setText(duration)
            self.duration_lbl.adjustSize()
            self.duration_lbl.setParent(self._thumb_container)
            self.duration_lbl.move(
                self._thumb_container.width() - self.duration_lbl.width() - 2,
                self._thumb_container.height() - self.duration_lbl.height() - 2
            )
            self.duration_lbl.raise_()
            self.duration_lbl.show()
        if channel:
            self.channel_lbl.setText(channel)
            self.channel_lbl.show()

    def set_thumbnail(self, path):
        if path and os.path.exists(path):
            pixmap = QPixmap(path)
            if not pixmap.isNull():
                self._thumb_path = path
                self.thumb_lbl.setPixmap(
                    pixmap.scaled(54, 30, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
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
    def __init__(self, parent_window, tab_id):
        super().__init__()
        self.parent_window = parent_window
        self.tab_id = tab_id

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
                duration = item.data(Qt.ItemDataRole.UserRole + 5) or ""
                channel = item.data(Qt.ItemDataRole.UserRole + 6) or ""
                if title is None: title = "Loading..."

                card = VideoCard(vid_id, title, url, watched, self.parent_window, item, row_index=i)
                if thumb_path:
                    card.set_thumbnail(thumb_path)
                if duration or channel:
                    card.set_metadata(duration, channel)
                item.setSizeHint(QSize(0, 40))
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
