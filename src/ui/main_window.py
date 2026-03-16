import os
import re
import logging
import subprocess
import requests
import threading
from bs4 import BeautifulSoup

from PyQt6.QtWidgets import (QMainWindow, QWidget, QLabel, QPushButton, QTabWidget,
                             QVBoxLayout, QHBoxLayout, QFrame,
                             QApplication, QListWidgetItem, QLineEdit, QInputDialog)
from PyQt6.QtCore import Qt, pyqtSignal, QPoint, QSize, QTimer

import src.theme as theme
from src.database import Database
from src.workers import GlobalInputListener
from src.ui.widgets import VideoCard, DraggableListWidget

logger = logging.getLogger(__name__)


class DropEdge(QWidget):
    """Thin strip on the left screen edge that detects video drag-and-drop."""

    def __init__(self, parent_window):
        super().__init__(None)
        self.parent_window = parent_window

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAcceptDrops(True)

        screen = QApplication.primaryScreen().geometry()
        self.setGeometry(0, 0, 12, screen.height())
        # Needs minimal opacity to receive drag events on X11
        self.setStyleSheet("background: rgba(0, 0, 0, 0.01);")
        self.show()

    def dragEnterEvent(self, event):
        mime = event.mimeData()
        text = ""
        if mime.hasUrls():
            text = mime.urls()[0].toString()
        elif mime.hasText():
            text = mime.text()

        if "youtube.com" in text or "youtu.be" in text:
            event.acceptProposedAction()
            if self.parent_window.isHidden():
                self.parent_window._hidden_by_fullscreen = False
                self.parent_window._opened_by_drag = True
                self.parent_window.show()
                self.parent_window.activateWindow()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        event.acceptProposedAction()

    def dropEvent(self, event):
        mime = event.mimeData()
        url = ""
        if mime.hasUrls():
            url = mime.urls()[0].toString()
        elif mime.hasText():
            url = mime.text()

        if "youtube.com" in url or "youtu.be" in url:
            self.parent_window._opened_by_drag = True
            self.parent_window._add_video_url(url)
        event.acceptProposedAction()


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

        self.db = Database()

        # Load theme before building UI
        saved_theme = self.db.load_setting('theme', theme.DEFAULT_THEME)
        theme.apply_theme(saved_theme)

        if not self._load_window_position():
            self.position_left_center()

        self.setup_ui()
        self.load_data()

        self.update_title_signal.connect(self.update_item_title)

        activation_key = self.db.load_setting('activation_key', 'scroll_right')
        self.listener = GlobalInputListener(activation_key)
        self.listener.toggle_signal.connect(self.toggle_visibility)
        self.listener.start()

        self.resize_margin = 10
        self.current_edge = None
        self.is_resizing = False
        self.old_pos = None

        self._hidden_by_fullscreen = False
        self._fullscreen_timer = QTimer(self)
        self._fullscreen_timer.setInterval(500)
        self._fullscreen_timer.timeout.connect(self._check_fullscreen)
        self._fullscreen_timer.start()

        self._drop_edge = DropEdge(self)
        self._opened_by_drag = False

    def position_left_center(self):
        screen = QApplication.primaryScreen().geometry()
        new_y = (screen.height() - self.height()) // 2
        self.move(20, new_y)

    # -- Window drag / resize --

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
            self._save_window_position()

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

    # -- Settings persistence --

    def _save_window_position(self):
        self.db.save_window_settings(self.x(), self.y(), self.width(), self.height())

    def _load_window_position(self):
        result = self.db.load_window_settings()
        if result:
            x, y, w, h = result
            self.move(x, y)
            self.resize(w, h)
            return True
        return False

    # -- UI setup --

    def _btn_style(self):
        return f"""
            QPushButton {{
                background: transparent;
                color: {theme.CLR_TEXT_DIM};
                border: 1px solid transparent;
                border-radius: 6px;
                font-size: 11px;
                font-weight: 600;
                letter-spacing: 0.3px;
                padding: 5px 8px;
            }}
            QPushButton:hover {{
                color: {theme.CLR_TEXT};
                background: rgba(255, 255, 255, 0.06);
                border: 1px solid rgba(255, 255, 255, 0.05);
            }}
        """

    def setup_ui(self):
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)

        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        self.central_widget.setStyleSheet(
            "QWidget { font-family: 'Inter', 'Segoe UI', 'SF Pro Display', sans-serif; }"
        )

        self.main_frame = QFrame()
        self.main_frame.setObjectName("MainFrame")
        self.frame_layout = QVBoxLayout(self.main_frame)
        self.frame_layout.setContentsMargins(8, 8, 8, 12)
        self.frame_layout.setSpacing(0)
        self.main_layout.addWidget(self.main_frame)

        # -- Top bar --
        top_bar = QHBoxLayout()
        top_bar.setSpacing(4)
        top_bar.setContentsMargins(4, 0, 4, 0)

        self.add_btn = QPushButton("+ Add")
        self.add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_btn.clicked.connect(self.add_current_video)
        top_bar.addWidget(self.add_btn)

        top_bar.addStretch()

        self.select_btn = QPushButton("Select")
        self.select_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.select_btn.clicked.connect(self.toggle_select_mode)
        top_bar.addWidget(self.select_btn)

        self.search_btn = QPushButton("Search")
        self.search_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.search_btn.clicked.connect(self.toggle_search)
        top_bar.addWidget(self.search_btn)

        self.settings_btn = QPushButton("\u2699")
        self.settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.settings_btn.clicked.connect(self._open_settings)
        top_bar.addWidget(self.settings_btn)

        self.hide_btn = QPushButton("Hide")
        self.hide_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.hide_btn.clicked.connect(self.hide)
        top_bar.addWidget(self.hide_btn)

        self.quit_btn = QPushButton("Quit")
        self.quit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.quit_btn.clicked.connect(self.close_application)
        top_bar.addWidget(self.quit_btn)

        self.frame_layout.addLayout(top_bar)

        # -- Search input --
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search videos...")
        self.search_input.textChanged.connect(self.filter_videos)
        self.search_input.hide()
        self.frame_layout.addWidget(self.search_input)

        # -- Filter bar (All / Watched / Unwatched) --
        self._filter_mode = "all"
        self.filter_bar = QHBoxLayout()
        self.filter_bar.setSpacing(4)
        self.filter_bar.setContentsMargins(4, 4, 4, 0)

        self.filter_all_btn = QPushButton("All")
        self.filter_watched_btn = QPushButton("Watched")
        self.filter_unwatched_btn = QPushButton("Unwatched")

        for btn in (self.filter_all_btn, self.filter_watched_btn, self.filter_unwatched_btn):
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setCheckable(True)
            self.filter_bar.addWidget(btn)

        self.filter_all_btn.setChecked(True)
        self.filter_all_btn.clicked.connect(lambda: self._set_filter_mode("all"))
        self.filter_watched_btn.clicked.connect(lambda: self._set_filter_mode("watched"))
        self.filter_unwatched_btn.clicked.connect(lambda: self._set_filter_mode("unwatched"))

        self.frame_layout.addLayout(self.filter_bar)

        # -- Bulk action bar --
        self._select_mode = False
        self.bulk_bar = QFrame()
        self.bulk_bar.setObjectName("BulkBar")
        bulk_layout = QHBoxLayout(self.bulk_bar)
        bulk_layout.setContentsMargins(4, 4, 4, 4)
        bulk_layout.setSpacing(4)

        self.bulk_delete_btn = QPushButton("Delete Selected")
        self.bulk_watched_btn = QPushButton("Mark Watched")
        self.bulk_move_btn = QPushButton("Move to Tab...")

        for btn in (self.bulk_delete_btn, self.bulk_watched_btn, self.bulk_move_btn):
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            bulk_layout.addWidget(btn)

        self.bulk_delete_btn.clicked.connect(self._bulk_delete)
        self.bulk_watched_btn.clicked.connect(self._bulk_mark_watched)
        self.bulk_move_btn.clicked.connect(self._bulk_move)

        self.bulk_bar.hide()
        self.frame_layout.addWidget(self.bulk_bar)

        # -- No results label --
        self.no_results_lbl = QLabel("No results found")
        self.no_results_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.no_results_lbl.hide()
        self.frame_layout.addWidget(self.no_results_lbl)

        # -- Tabs --
        self.tabs = QTabWidget()
        self.tabs.tabBarDoubleClicked.connect(self._rename_tab)

        self.tab_lists = []
        for i in range(3):
            lst = DraggableListWidget(self, i)
            self.tab_lists.append(lst)
            tab_name = self.db.load_setting(f'tab_name_{i}', f"Tab {i + 1}")
            self.tabs.addTab(lst, tab_name)

        self.history_list = DraggableListWidget(self, 99)
        self.tab_lists.append(self.history_list)
        self.tabs.addTab(self.history_list, "History")

        self.tabs.currentChanged.connect(lambda: self.filter_videos(self.search_input.text()))
        self.frame_layout.addWidget(self.tabs)

        self.empty_lbl = QLabel("Drop YouTube links here")
        self.empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.frame_layout.addWidget(self.empty_lbl)
        self.empty_lbl.hide()

        # Apply all styles
        self._apply_styles()

    def _apply_styles(self):
        """Apply or re-apply all stylesheets using current theme colors."""
        self.main_frame.setStyleSheet(f"""
            QFrame#MainFrame {{
                background: {theme.CLR_SURFACE};
                border: 1px solid {theme.CLR_BORDER};
                border-radius: 12px;
            }}
        """)

        self.add_btn.setStyleSheet(f"""
            QPushButton {{
                background: {theme.CLR_ACCENT_SUBTLE};
                color: {theme.CLR_ACCENT};
                border: 1px solid {theme.accent_rgba(0.20)};
                border-radius: 6px;
                font-size: 11px;
                font-weight: 700;
                padding: 5px 14px;
            }}
            QPushButton:hover {{
                background: {theme.accent_rgba(0.22)};
                color: {theme.CLR_ACCENT_HOVER};
                border: 1px solid {theme.accent_rgba(0.35)};
            }}
        """)

        btn_style = self._btn_style()
        self.search_btn.setStyleSheet(btn_style)
        self.select_btn.setStyleSheet(btn_style)
        self.settings_btn.setStyleSheet(btn_style)
        self.hide_btn.setStyleSheet(btn_style)

        self.quit_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {theme.CLR_TEXT_DIM};
                border: 1px solid transparent;
                border-radius: 6px;
                font-size: 11px;
                font-weight: 600;
                letter-spacing: 0.3px;
                padding: 5px 12px;
            }}
            QPushButton:hover {{
                color: #e05252;
                background: rgba(224, 82, 82, 0.10);
                border: 1px solid rgba(224, 82, 82, 0.15);
            }}
        """)

        self.search_input.setStyleSheet(f"""
            QLineEdit {{
                background: {theme.CLR_BASE};
                border: 1px solid {theme.CLR_BORDER};
                border-radius: 8px;
                color: {theme.CLR_TEXT};
                padding: 8px 12px;
                margin: 8px 4px 0px 4px;
                font-size: 12px;
            }}
            QLineEdit:focus {{
                border: 1px solid {theme.CLR_ACCENT};
            }}
        """)

        self.no_results_lbl.setStyleSheet(f"""
            color: {theme.CLR_TEXT_MUTED};
            font-size: 12px;
            font-weight: 500;
            border: none;
            padding: 20px 0px;
        """)

        self.tabs.setStyleSheet(f"""
            QTabWidget::pane {{
                border: none;
                background: transparent;
                margin-top: 4px;
            }}
            QTabBar {{
                background: transparent;
            }}
            QTabBar::tab {{
                background: transparent;
                color: {theme.CLR_TEXT_MUTED};
                padding: 6px 4px;
                min-width: 48px;
                margin: 4px 2px 0px 2px;
                font-weight: 600;
                font-size: 11px;
                letter-spacing: 0.3px;
                border: none;
                border-bottom: 2px solid transparent;
                border-radius: 0px;
            }}
            QTabBar::tab:selected {{
                color: {theme.CLR_TEXT};
                border-bottom: 2px solid {theme.CLR_ACCENT};
            }}
            QTabBar::tab:hover:!selected {{
                color: {theme.CLR_TEXT_DIM};
            }}
        """)

        self.empty_lbl.setStyleSheet(f"""
            color: {theme.CLR_TEXT_MUTED};
            font-size: 13px;
            font-weight: 500;
            border: none;
            padding: 32px 0px;
        """)

        filter_btn_style = f"""
            QPushButton {{
                background: transparent;
                color: {theme.CLR_TEXT_MUTED};
                border: 1px solid transparent;
                border-radius: 4px;
                font-size: 10px;
                font-weight: 600;
                padding: 3px 10px;
            }}
            QPushButton:hover {{
                color: {theme.CLR_TEXT};
                background: rgba(255, 255, 255, 0.06);
            }}
            QPushButton:checked {{
                color: {theme.CLR_ACCENT};
                background: {theme.CLR_ACCENT_SUBTLE};
                border: 1px solid {theme.accent_rgba(0.20)};
            }}
        """
        self.filter_all_btn.setStyleSheet(filter_btn_style)
        self.filter_watched_btn.setStyleSheet(filter_btn_style)
        self.filter_unwatched_btn.setStyleSheet(filter_btn_style)

        bulk_btn_style = f"""
            QPushButton {{
                background: {theme.CLR_ELEVATED};
                color: {theme.CLR_TEXT};
                border: 1px solid {theme.CLR_BORDER};
                border-radius: 4px;
                font-size: 10px;
                font-weight: 600;
                padding: 4px 10px;
            }}
            QPushButton:hover {{
                background: {theme.CLR_BORDER};
            }}
        """
        self.bulk_delete_btn.setStyleSheet(bulk_btn_style)
        self.bulk_watched_btn.setStyleSheet(bulk_btn_style)
        self.bulk_move_btn.setStyleSheet(bulk_btn_style)

        self.bulk_bar.setStyleSheet(f"""
            QFrame#BulkBar {{
                background: {theme.CLR_BASE};
                border: 1px solid {theme.CLR_BORDER};
                border-radius: 6px;
                margin: 4px;
            }}
        """)

    def refresh_styles(self):
        """Refresh all styles and reload data after theme change."""
        self._apply_styles()
        self.load_data()

    # -- Tab rename --

    def _rename_tab(self, index):
        if index >= 3:
            return  # Don't rename History tab

        current_name = self.tabs.tabText(index)

        dialog = QInputDialog(self)
        dialog.setWindowTitle("Rename Tab")
        dialog.setLabelText("Tab name:")
        dialog.setTextValue(current_name)
        dialog.setStyleSheet(f"""
            QInputDialog, QDialog {{
                background: {theme.CLR_SURFACE};
            }}
            QLabel {{
                color: {theme.CLR_TEXT};
                font-size: 12px;
            }}
            QLineEdit {{
                background: {theme.CLR_BASE};
                border: 1px solid {theme.CLR_BORDER};
                border-radius: 6px;
                color: {theme.CLR_TEXT};
                padding: 6px 10px;
                font-size: 12px;
            }}
            QLineEdit:focus {{
                border: 1px solid {theme.CLR_ACCENT};
            }}
            QPushButton {{
                background: {theme.CLR_ELEVATED};
                color: {theme.CLR_TEXT};
                border: 1px solid {theme.CLR_BORDER};
                border-radius: 6px;
                padding: 6px 16px;
                font-size: 12px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background: {theme.CLR_BORDER};
            }}
        """)

        if dialog.exec():
            new_name = dialog.textValue().strip()
            if new_name:
                self.tabs.setTabText(index, new_name)
                self.db.save_setting(f'tab_name_{index}', new_name)

    # -- Settings dialog --

    def _open_settings(self):
        from src.ui.settings_dialog import SettingsDialog
        dialog = SettingsDialog(self, self.db)
        dialog.exec()

    # -- Search --

    def toggle_search(self):
        if self.search_input.isVisible():
            self.search_input.clear()
            self.search_input.hide()
            self.no_results_lbl.hide()
        else:
            self.search_input.show()
            self.search_input.setFocus()

    def _set_filter_mode(self, mode):
        self._filter_mode = mode
        self.filter_all_btn.setChecked(mode == "all")
        self.filter_watched_btn.setChecked(mode == "watched")
        self.filter_unwatched_btn.setChecked(mode == "unwatched")
        self.filter_videos(self.search_input.text())

    def filter_videos(self, text):
        text = text.lower()
        current_idx = self.tabs.currentIndex()
        current_list = self.tab_lists[current_idx] if current_idx < len(self.tab_lists) else None

        has_visible = False
        for tab_list in self.tab_lists:
            for i in range(tab_list.count()):
                item = tab_list.item(i)
                title = item.data(Qt.ItemDataRole.UserRole + 3) or ""
                watched = item.data(Qt.ItemDataRole.UserRole + 2)

                hidden = text not in title.lower()

                if not hidden and self._filter_mode == "watched":
                    hidden = not watched
                elif not hidden and self._filter_mode == "unwatched":
                    hidden = bool(watched)

                item.setHidden(hidden)
                if tab_list == current_list and not hidden:
                    has_visible = True

        if (text or self._filter_mode != "all") and current_list and not has_visible:
            self.no_results_lbl.show()
        else:
            self.no_results_lbl.hide()

    def toggle_select_mode(self):
        self._select_mode = not self._select_mode
        self.select_btn.setChecked(self._select_mode)

        if self._select_mode:
            self.bulk_bar.show()
        else:
            self.bulk_bar.hide()

        for tab_list in self.tab_lists:
            for i in range(tab_list.count()):
                w = tab_list.itemWidget(tab_list.item(i))
                if w:
                    w.set_select_mode(self._select_mode)

    def _get_checked_vid_ids(self):
        current_idx = self.tabs.currentIndex()
        current_list = self.tab_lists[current_idx] if current_idx < len(self.tab_lists) else None
        if not current_list:
            return []
        vid_ids = []
        for i in range(current_list.count()):
            w = current_list.itemWidget(current_list.item(i))
            if w and w.is_checked():
                vid_ids.append(w.vid_id)
        return vid_ids

    def _bulk_delete(self):
        vid_ids = self._get_checked_vid_ids()
        if not vid_ids:
            return
        self.db.bulk_soft_delete(vid_ids)
        self.toggle_select_mode()
        self.load_data()

    def _bulk_mark_watched(self):
        vid_ids = self._get_checked_vid_ids()
        if not vid_ids:
            return
        self.db.bulk_mark_watched(vid_ids)
        self.toggle_select_mode()
        self.load_data()

    def _bulk_move(self):
        vid_ids = self._get_checked_vid_ids()
        if not vid_ids:
            return

        tab_names = [self.tabs.tabText(i) for i in range(3)]
        name, ok = QInputDialog.getItem(self, "Move to Tab", "Select tab:", tab_names, 0, False)
        if ok and name:
            tab_index = tab_names.index(name)
            self.db.bulk_move_to_tab(vid_ids, tab_index)
            self.toggle_select_mode()
            self.load_data()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape and self.search_input.isVisible():
            self.search_input.clear()
            self.search_input.hide()
            self.no_results_lbl.hide()
        else:
            super().keyPressEvent(event)

    # -- Empty state --

    def check_empty_state(self):
        total_items = sum(lst.count() for lst in self.tab_lists)
        if total_items == 0:
            self.empty_lbl.show()
            self.tabs.hide()
        else:
            self.empty_lbl.hide()
            self.tabs.show()

    def close_application(self):
        self._fullscreen_timer.stop()
        self._save_window_position()
        self.db.close()
        QApplication.quit()

    # -- Video CRUD --

    def update_video_order(self, vid_id, new_order):
        self.db.update_video_order(vid_id, new_order)

    def load_data(self):
        for lst in self.tab_lists:
            lst.clear()

        for vid_id, title, url, watched, tab_index, thumb_path in self.db.get_active_videos():
            target_index = tab_index if tab_index < 3 else 0
            self.create_card_item(vid_id, title, url, watched, self.tab_lists[target_index], thumbnail_path=thumb_path)

        for vid_id, title, url, watched, thumb_path in self.db.get_deleted_videos():
            self.create_card_item(vid_id, title, url, watched, self.history_list, thumbnail_path=thumb_path)

        self.check_empty_state()

    def create_card_item(self, vid_id, title, url, watched, target_list, insert_top=False, thumbnail_path=""):
        if insert_top:
            item = QListWidgetItem()
            target_list.insertItem(0, item)
            row_index = 0
        else:
            item = QListWidgetItem(target_list)
            row_index = target_list.count() - 1

        item.setSizeHint(QSize(0, 48))
        item.setData(Qt.ItemDataRole.UserRole, url)
        item.setData(Qt.ItemDataRole.UserRole + 1, vid_id)
        item.setData(Qt.ItemDataRole.UserRole + 2, watched)
        item.setData(Qt.ItemDataRole.UserRole + 3, title)
        item.setData(Qt.ItemDataRole.UserRole + 4, thumbnail_path or "")
        is_history = (target_list == self.history_list)
        card = VideoCard(vid_id, title, url, watched, self, item, is_history=is_history, row_index=row_index)
        if thumbnail_path:
            card.set_thumbnail(thumbnail_path)
        target_list.setItemWidget(item, card)

        # Re-apply alternating styles when inserting at top
        if insert_top:
            for i in range(target_list.count()):
                w = target_list.itemWidget(target_list.item(i))
                if w:
                    w.apply_row_style(i)

    def mark_as_watched(self, vid_id, card_widget):
        self.db.mark_watched(vid_id)
        card_widget.set_watched_style()

    def mark_as_unwatched(self, vid_id, card_widget):
        self.db.mark_unwatched(vid_id)
        card_widget.set_unwatched_style()

    def delete_video(self, vid_id, item):
        list_widget = item.listWidget()

        if list_widget == self.history_list:
            self.db.hard_delete_video(vid_id)
            row = list_widget.row(item)
            list_widget.takeItem(row)
        else:
            self.db.soft_delete_video(vid_id)

            row = list_widget.row(item)
            list_widget.takeItem(row)

            title = item.data(Qt.ItemDataRole.UserRole + 3)
            url = item.data(Qt.ItemDataRole.UserRole)
            watched = item.data(Qt.ItemDataRole.UserRole + 2)
            thumb_path = item.data(Qt.ItemDataRole.UserRole + 4) or ""
            self.create_card_item(vid_id, title, url, watched, self.history_list, thumbnail_path=thumb_path)

        self.check_empty_state()

    def restore_video(self, vid_id, item):
        target_tab = self.db.get_video_tab(vid_id)
        if target_tab >= 3:
            target_tab = 0

        self.db.restore_video(vid_id)

        list_widget = item.listWidget()
        list_widget.takeItem(list_widget.row(item))

        title = item.data(Qt.ItemDataRole.UserRole + 3)
        url = item.data(Qt.ItemDataRole.UserRole)
        watched = item.data(Qt.ItemDataRole.UserRole + 2)
        thumb_path = item.data(Qt.ItemDataRole.UserRole + 4) or ""
        self.create_card_item(vid_id, title, url, watched, self.tab_lists[target_tab], insert_top=True, thumbnail_path=thumb_path)
        self.check_empty_state()

    # -- Drag & drop --

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
            self._opened_by_drag = True
            self._add_video_url(url)

    def _add_video_url(self, url):
        if self.tabs.currentIndex() == 3:
            current_tab_index = 0
        else:
            current_tab_index = self.tabs.currentIndex()

        existing_id = self.db.find_video_by_url(url)
        if existing_id:
            self.db.hard_delete_video(existing_id)
            self.load_data()

        new_order = self.db.get_min_row_order() - 1

        last_id = self.db.add_video(url, "Loading info...", current_tab_index, new_order)

        self.create_card_item(last_id, "Loading info...", url, 0, self.tab_lists[current_tab_index], insert_top=True)
        self.check_empty_state()
        threading.Thread(target=self.fetch_title, args=(url, last_id, current_tab_index), daemon=True).start()

    # -- Add from browser --

    def _find_browser_window(self):
        """Find the most recently active browser window."""
        browsers = ['firefox', 'chrome', 'chromium', 'brave']
        for browser in browsers:
            try:
                result = subprocess.run(
                    ['xdotool', 'search', '--class', browser],
                    capture_output=True, text=True, timeout=1
                )
                wins = result.stdout.strip().split('\n')
                for win_id in wins:
                    if not win_id:
                        continue
                    name = subprocess.run(
                        ['xdotool', 'getwindowname', win_id],
                        capture_output=True, text=True, timeout=1
                    ).stdout.strip()
                    if name and name != browser:
                        return win_id
            except Exception:
                continue
        return None

    def add_current_video(self):
        win_id = self._find_browser_window()
        if not win_id:
            logger.warning("No browser window found")
            return

        try:
            subprocess.run(['xdotool', 'windowactivate', '--sync', win_id], timeout=2)
            subprocess.run(['xdotool', 'key', 'ctrl+l'], timeout=1)
            subprocess.run(['xdotool', 'key', 'ctrl+c'], timeout=1)
            subprocess.run(['xdotool', 'key', 'Escape'], timeout=1)
        except Exception:
            logger.warning("xdotool grab failed", exc_info=True)
            return

        QApplication.processEvents()
        url = QApplication.clipboard().text().strip()

        if 'youtube.com' in url or 'youtu.be' in url:
            self._add_video_url(url)
            self.activateWindow()

    # -- Title / thumbnail fetching --

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
            if soup.title:
                title = soup.title.string.replace("- YouTube", "").strip()
        except Exception:
            logger.warning("Failed to fetch title for %s", url, exc_info=True)

        try:
            video_id = self.extract_video_id(url)
            if video_id:
                thumb_url = f"https://img.youtube.com/vi/{video_id}/mqdefault.jpg"
                resp = requests.get(thumb_url, timeout=5)
                if resp.status_code == 200:
                    thumb_path = os.path.join(self.db.thumbnails_dir, f"{video_id}.jpg")
                    with open(thumb_path, 'wb') as f:
                        f.write(resp.content)
        except Exception:
            logger.warning("Failed to fetch thumbnail for %s", url, exc_info=True)

        self.update_title_signal.emit(title, thumb_path, vid_id, tab_index)

    def update_item_title(self, title, thumb_path, vid_id, tab_index):
        self.db.update_video_title(vid_id, title, thumb_path)

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

        if self._opened_by_drag:
            self._opened_by_drag = False
            QTimer.singleShot(800, self._hide_after_drag)

    def _hide_after_drag(self):
        if not self._opened_by_drag:
            self.hide()

    # -- Visibility --

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
            logger.debug("Fullscreen check failed", exc_info=True)
