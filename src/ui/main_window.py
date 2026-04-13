import os
import re
import json
import logging
import subprocess
import requests
from concurrent.futures import ThreadPoolExecutor
from bs4 import BeautifulSoup

from PyQt6.QtWidgets import (QMainWindow, QWidget, QLabel, QPushButton, QTabWidget, QTabBar,
                             QVBoxLayout, QHBoxLayout, QFrame, QMessageBox, QProgressBar,
                             QApplication, QListWidgetItem, QLineEdit, QInputDialog)
from PyQt6.QtCore import Qt, pyqtSignal, QPoint, QSize, QTimer, QObject, QEvent

import src.theme as theme
from src.database import Database
from src.net import is_safe_youtube_url, fetch_bounded
from src.obsidian_export import ObsidianExporter
from src.workers import GlobalInputListener, PlaylistFetchWorker
from src.ui.widgets import VideoCard, DraggableListWidget

logger = logging.getLogger(__name__)

_PAGE_MAX_BYTES = 4 * 1024 * 1024   # 4 MiB — YouTube pages ~2 MiB
_OEMBED_MAX_BYTES = 64 * 1024        # 64 KiB
_THUMB_MAX_BYTES = 2 * 1024 * 1024  # 2 MiB


def _sanitize_tab_name(raw: str) -> str | None:
    """Return a safe tab name or None if the input is invalid."""
    cleaned = re.sub(r'[/\\:*?"<>|\x00-\x1f]', '', raw).strip().strip('.')
    if not cleaned:
        return None
    return cleaned[:64]


class _TabBarDragFilter(QObject):
    """Prevents dragging the History and '+' tabs."""

    def __init__(self, app):
        super().__init__(app)
        self._app = app

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.MouseButtonPress:
            self._pressed_idx = obj.tabAt(event.pos())
        elif event.type() == QEvent.Type.MouseMove:
            # Block drag only if the press started on a protected tab
            if getattr(self, '_pressed_idx', -1) >= self._app.work_tab_count:
                return True
        return False


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
        self.setAcceptDrops(True)

        screen = QApplication.primaryScreen().geometry()
        self.setGeometry(0, 0, 12, screen.height())
        self.setStyleSheet("background: black;")
        self.setWindowOpacity(0.01)
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
            self.parent_window._add_video_url(url)
        event.acceptProposedAction()


class LavidaApp(QMainWindow):
    update_title_signal = pyqtSignal(str, str, int, int, str, str)

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

        self.obsidian_exporter = ObsidianExporter(self.db)
        self.db.data_changed.connect(self.obsidian_exporter._schedule_write)
        self.obsidian_exporter.import_complete.connect(self.load_data)
        vault_path = self.db.load_setting('obsidian_vault_path', '')
        if vault_path:
            self.obsidian_exporter.configure(vault_path, self._get_tab_names())

        self.update_title_signal.connect(self.update_item_title)

        activation_key = self.db.load_setting('activation_key', 'scroll_right')
        self.listener = GlobalInputListener(activation_key)
        self.listener.toggle_signal.connect(self.toggle_visibility)
        self.listener.start()

        self._executor = ThreadPoolExecutor(max_workers=3)

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
                background: {theme.CLR_ELEVATED};
                color: {theme.CLR_TEXT_DIM};
                border: 1px solid {theme.CLR_BORDER};
                border-radius: 8px;
                font-size: 13px;
                font-weight: 600;
                min-height: 34px;
                padding: 0px 12px;
            }}
            QPushButton:hover {{
                color: {theme.CLR_TEXT};
                background: rgba(255, 255, 255, 0.08);
                border: 1px solid {theme.CLR_BORDER_HOVER};
            }}
        """

    def _icon_btn_style(self):
        return f"""
            QPushButton {{
                background: {theme.CLR_ELEVATED};
                color: {theme.CLR_TEXT_DIM};
                border: 1px solid {theme.CLR_BORDER};
                border-radius: 8px;
                font-size: 15px;
                min-height: 34px;
                min-width: 34px;
                max-width: 34px;
                padding: 0px;
            }}
            QPushButton:hover {{
                color: {theme.CLR_TEXT};
                background: rgba(255, 255, 255, 0.08);
                border: 1px solid {theme.CLR_BORDER_HOVER};
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
        self.frame_layout.setContentsMargins(8, 10, 8, 12)
        self.frame_layout.setSpacing(0)
        self.main_layout.addWidget(self.main_frame)

        # -- Top bar --
        top_bar = QHBoxLayout()
        top_bar.setSpacing(6)
        top_bar.setContentsMargins(4, 6, 4, 6)

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

        self.hide_btn = QPushButton("–")
        self.hide_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.hide_btn.setToolTip("Hide")
        self.hide_btn.clicked.connect(self.hide)
        top_bar.addWidget(self.hide_btn)

        self.quit_btn = QPushButton("✕")
        self.quit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.quit_btn.setToolTip("Quit")
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
        self.filter_bar.setContentsMargins(4, 6, 4, 2)

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
        self._tab_id_map = {}       # {tab_id: DraggableListWidget}
        self._work_tab_ids = []     # ordered list of work tab IDs
        self._history_tab_id = None
        self._max_tabs = 10

        self.tabs = QTabWidget()
        self.tabs.tabBar().setMovable(True)
        self._tab_drag_filter = _TabBarDragFilter(self)
        self.tabs.tabBar().installEventFilter(self._tab_drag_filter)
        self.tabs.tabBar().tabMoved.connect(self._on_tab_moved)
        self.tabs.tabBarDoubleClicked.connect(self._rename_tab)

        self.tab_lists = []
        for tab_id, name, _ in self.db.get_work_tabs():
            lst = DraggableListWidget(self, tab_id)
            self.tab_lists.append(lst)
            self._tab_id_map[tab_id] = lst
            self._work_tab_ids.append(tab_id)
            self.tabs.addTab(lst, name)
            close_btn = self._make_close_btn(tab_id)
            self.tabs.tabBar().setTabButton(
                self.tabs.count() - 1, QTabBar.ButtonPosition.RightSide, close_btn
            )

        self._history_tab_id = self.db.get_history_tab_id()
        self.history_list = DraggableListWidget(self, self._history_tab_id)
        self.tab_lists.append(self.history_list)
        self._tab_id_map[self._history_tab_id] = self.history_list
        self.tabs.addTab(self.history_list, "History")
        # No close button on History tab

        # "+" tab — always last, acts as a button to add new tabs
        self._plus_placeholder = QWidget()
        self.tabs.addTab(self._plus_placeholder, "+")
        self.tabs.tabBar().setTabButton(
            self.tabs.count() - 1, QTabBar.ButtonPosition.RightSide, None
        )

        self.tabs.currentChanged.connect(self._on_tab_changed)
        self.frame_layout.addWidget(self.tabs)

        # -- Playlist import progress bar --
        self.playlist_progress = QProgressBar()
        self.playlist_progress.setFixedHeight(3)
        self.playlist_progress.setTextVisible(False)
        self.playlist_progress.setStyleSheet(f"""
            QProgressBar {{
                background: {theme.CLR_BASE};
                border: none;
                border-radius: 1px;
            }}
            QProgressBar::chunk {{
                background: {theme.CLR_ACCENT};
                border-radius: 1px;
            }}
        """)
        self.playlist_progress.hide()
        self.frame_layout.addWidget(self.playlist_progress)

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
                background: {theme.CLR_ACCENT};
                color: #ffffff;
                border: none;
                border-radius: 8px;
                font-size: 13px;
                font-weight: 700;
                min-height: 34px;
                padding: 0px 18px;
            }}
            QPushButton:hover {{
                background: {theme.CLR_ACCENT_HOVER};
            }}
        """)

        btn_style = self._btn_style()
        self.search_btn.setStyleSheet(btn_style)
        self.select_btn.setStyleSheet(btn_style)

        icon_btn_style = self._icon_btn_style()
        self.settings_btn.setStyleSheet(icon_btn_style)

        self.hide_btn.setStyleSheet(icon_btn_style)

        self.quit_btn.setStyleSheet(f"""
            QPushButton {{
                background: {theme.CLR_ELEVATED};
                color: {theme.CLR_TEXT_DIM};
                border: 1px solid {theme.CLR_BORDER};
                border-radius: 8px;
                font-size: 15px;
                min-height: 34px;
                min-width: 34px;
                max-width: 34px;
                padding: 0px;
            }}
            QPushButton:hover {{
                color: #e05252;
                background: rgba(224, 82, 82, 0.12);
                border: 1px solid rgba(224, 82, 82, 0.20);
            }}
        """)

        self.search_input.setStyleSheet(f"""
            QLineEdit {{
                background: {theme.CLR_BASE};
                border: 1px solid {theme.CLR_BORDER};
                border-radius: 8px;
                color: {theme.CLR_TEXT};
                padding: 8px 12px;
                margin: 8px 4px 4px 4px;
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
                margin-top: 2px;
            }}
            QTabBar {{
                background: transparent;
            }}
            QTabBar::tab {{
                background: transparent;
                color: {theme.CLR_TEXT_MUTED};
                padding: 10px 6px;
                min-width: 48px;
                margin: 6px 3px 0px 3px;
                font-weight: 600;
                font-size: 13px;
                letter-spacing: 0.3px;
                border: none;
                border-bottom: 2px solid transparent;
                border-radius: 0px;
            }}
            QTabBar::tab:selected {{
                color: {theme.CLR_TEXT};
                border-bottom: 2px solid {theme.CLR_ACCENT};
                background: {theme.accent_rgba(0.06)};
            }}
            QTabBar::tab:hover:!selected {{
                color: {theme.CLR_TEXT_DIM};
                background: rgba(255,255,255,0.03);
            }}
            QTabBar::tab:last {{
                color: {theme.CLR_TEXT_MUTED};
                min-width: 20px;
                padding: 10px 10px;
                font-size: 18px;
                font-weight: 400;
                letter-spacing: 0px;
                border-bottom: none;
            }}
            QTabBar::tab:last:hover {{
                color: {theme.CLR_TEXT};
                background: rgba(255,255,255,0.06);
            }}
            QTabBar::tab:last:selected {{
                color: {theme.CLR_TEXT_MUTED};
                border-bottom: none;
                background: transparent;
            }}
        """)

        close_btn_style = f"""
            QPushButton {{
                background: transparent;
                color: {theme.CLR_TEXT_MUTED};
                border: none;
                border-radius: 3px;
                font-size: 13px;
                font-weight: bold;
                padding: 0px;
            }}
            QPushButton:hover {{
                color: #e05252;
                background: rgba(224, 82, 82, 0.18);
            }}
        """
        for i, tab_id in enumerate(self._work_tab_ids):
            btn = self.tabs.tabBar().tabButton(i, QTabBar.ButtonPosition.RightSide)
            if btn:
                btn.setStyleSheet(close_btn_style)

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

    @property
    def work_tab_count(self):
        return len(self._work_tab_ids)

    def _get_tab_names(self):
        return [self.tabs.tabText(i) for i in range(self.work_tab_count)]

    def _make_close_btn(self, tab_id):
        btn = QPushButton("×")
        btn.setFixedSize(16, 16)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(lambda: self._close_tab_by_id(tab_id))
        return btn

    def _on_tab_moved(self, from_idx, to_idx):
        # Reject moves involving History or "+" tabs
        if from_idx >= self.work_tab_count or to_idx >= self.work_tab_count:
            self.tabs.tabBar().moveTab(to_idx, from_idx)
            return
        # Reorder internal structures
        tid = self._work_tab_ids.pop(from_idx)
        self._work_tab_ids.insert(to_idx, tid)
        lst = self.tab_lists.pop(from_idx)
        self.tab_lists.insert(to_idx, lst)
        # Persist
        self.db.update_tab_sort_orders(self._work_tab_ids)
        self.obsidian_exporter.update_tab_names(self._get_tab_names())

    def _on_tab_changed(self, index):
        plus_idx = self.tabs.count() - 1
        if index == plus_idx:
            # "+" tab clicked — redirect to last work tab, then create new tab
            self.tabs.setCurrentIndex(self.work_tab_count - 1)
            if self.work_tab_count < self._max_tabs:
                self._add_tab()
            return
        self.filter_videos(self.search_input.text())

    def _add_tab(self):
        if self.work_tab_count >= self._max_tabs:
            return
        sort_order = self.db.get_next_sort_order()
        existing = set(self._get_tab_names())
        n = self.work_tab_count + 1
        name = f"Tab {n}"
        while name in existing:
            n += 1
            name = f"Tab {n}"
        tab_id = self.db.create_tab(name, sort_order)
        lst = DraggableListWidget(self, tab_id)
        insert_idx = self.work_tab_count  # before History and "+" tab
        self._work_tab_ids.append(tab_id)
        self._tab_id_map[tab_id] = lst
        self.tab_lists.insert(-1, lst)
        self.tabs.insertTab(insert_idx, lst, name)
        close_btn = self._make_close_btn(tab_id)
        self.tabs.tabBar().setTabButton(insert_idx, QTabBar.ButtonPosition.RightSide, close_btn)
        self._apply_styles()
        self.tabs.setCurrentIndex(insert_idx)
        self.obsidian_exporter.update_tab_names(self._get_tab_names())

    def _close_tab_by_id(self, tab_id):
        if tab_id not in self._tab_id_map:
            return
        index = self._work_tab_ids.index(tab_id)
        self._close_tab(index)

    def _close_tab(self, index):
        if self.work_tab_count <= 1:
            return
        tab_name = self.tabs.tabText(index)
        tab_id = self._work_tab_ids[index]
        msg = QMessageBox(self)
        msg.setWindowTitle("Delete Tab")
        msg.setText(f"Delete tab '{tab_name}'?\nVideos will be moved to History.")
        msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel)
        msg.setDefaultButton(QMessageBox.StandardButton.Cancel)
        msg.setStyleSheet(f"""
            QMessageBox {{ background: {theme.CLR_SURFACE}; }}
            QLabel {{ color: {theme.CLR_TEXT}; font-size: 12px; }}
            QPushButton {{
                background: {theme.CLR_ELEVATED};
                color: {theme.CLR_TEXT};
                border: 1px solid {theme.CLR_BORDER};
                border-radius: 6px;
                padding: 6px 16px;
                font-size: 12px;
                font-weight: 600;
                min-width: 60px;
            }}
            QPushButton:hover {{ background: {theme.CLR_BORDER}; }}
        """)
        if msg.exec() != QMessageBox.StandardButton.Yes:
            return
        self.db.delete_tab(tab_id)
        self._work_tab_ids.pop(index)
        del self._tab_id_map[tab_id]
        self.tab_lists.pop(index)
        self.tabs.removeTab(index)
        # Stay on adjacent tab
        new_count = self.work_tab_count
        if index >= new_count:
            self.tabs.setCurrentIndex(max(0, new_count - 1))
        self.load_data()
        self.obsidian_exporter.update_tab_names(self._get_tab_names(), removed_names=[tab_name])

    def _rename_tab(self, index):
        if index >= self.work_tab_count:
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
            new_name = _sanitize_tab_name(dialog.textValue())
            if new_name and new_name not in self._get_tab_names():
                self.tabs.setTabText(index, new_name)
                self.db.rename_tab(self._work_tab_ids[index], new_name)
                self.obsidian_exporter.update_tab_names(self._get_tab_names())

    # -- Settings dialog --

    def _open_settings(self):
        from src.ui.settings_dialog import SettingsDialog
        dialog = SettingsDialog(self, self.db)
        dialog.exec()

    def configure_obsidian_export(self, path):
        self.obsidian_exporter.configure(path, self._get_tab_names())

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

        tab_names = self._get_tab_names()
        name, ok = QInputDialog.getItem(self, "Move to Tab", "Select tab:", tab_names, 0, False)
        if ok and name:
            tab_id = self._work_tab_ids[tab_names.index(name)]
            self.db.bulk_move_to_tab(vid_ids, tab_id)
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
        self.obsidian_exporter.shutdown()
        if hasattr(self, '_playlist_worker') and self._playlist_worker and self._playlist_worker.isRunning():
            self._playlist_worker.cancel()
            self._playlist_worker.quit()
            self._playlist_worker.wait(2000)
        self._executor.shutdown(wait=False, cancel_futures=True)
        self.listener.quit()
        self.listener.wait(2000)
        self.db.close()
        QApplication.quit()

    # -- Context menu helpers --

    def get_work_tabs_for_menu(self):
        return [(tid, self.tabs.tabText(i)) for i, tid in enumerate(self._work_tab_ids)]

    def move_video_to_tab(self, vid_id, list_item, target_tab_id):
        self.db.reassign_video_tab(vid_id, target_tab_id)
        list_widget = list_item.listWidget()
        if list_widget:
            list_widget.takeItem(list_widget.row(list_item))
        title = list_item.data(Qt.ItemDataRole.UserRole + 3)
        url = list_item.data(Qt.ItemDataRole.UserRole)
        watched = list_item.data(Qt.ItemDataRole.UserRole + 2)
        thumb_path = list_item.data(Qt.ItemDataRole.UserRole + 4) or ""
        duration = list_item.data(Qt.ItemDataRole.UserRole + 5) or ""
        channel = list_item.data(Qt.ItemDataRole.UserRole + 6) or ""
        target_list = self._tab_id_map.get(target_tab_id, self.tab_lists[0])
        self.create_card_item(vid_id, title, url, watched, target_list, insert_top=True,
                              thumbnail_path=thumb_path, duration=duration, channel=channel)
        self.check_empty_state()

    # -- Video CRUD --

    def update_video_order(self, vid_id, new_order):
        self.db.update_video_order(vid_id, new_order)

    def load_data(self):
        for lst in self.tab_lists:
            lst.clear()

        for vid_id, title, url, watched, tab_id, thumb_path, duration, channel in self.db.get_active_videos():
            target_list = self._tab_id_map.get(tab_id)
            if target_list is None or target_list == self.history_list:
                target_list = self.tab_lists[0]
            self.create_card_item(vid_id, title, url, watched, target_list,
                                  thumbnail_path=thumb_path, duration=duration or "",
                                  channel=channel or "")

        for vid_id, title, url, watched, thumb_path, duration, channel in self.db.get_deleted_videos():
            self.create_card_item(vid_id, title, url, watched, self.history_list,
                                  thumbnail_path=thumb_path, duration=duration or "",
                                  channel=channel or "")

        self.check_empty_state()

    def create_card_item(self, vid_id, title, url, watched, target_list, insert_top=False,
                         thumbnail_path="", duration="", channel=""):
        if insert_top:
            item = QListWidgetItem()
            target_list.insertItem(0, item)
            row_index = 0
        else:
            item = QListWidgetItem(target_list)
            row_index = target_list.count() - 1

        item.setSizeHint(QSize(0, 40))
        item.setData(Qt.ItemDataRole.UserRole, url)
        item.setData(Qt.ItemDataRole.UserRole + 1, vid_id)
        item.setData(Qt.ItemDataRole.UserRole + 2, watched)
        item.setData(Qt.ItemDataRole.UserRole + 3, title)
        item.setData(Qt.ItemDataRole.UserRole + 4, thumbnail_path or "")
        item.setData(Qt.ItemDataRole.UserRole + 5, duration)
        item.setData(Qt.ItemDataRole.UserRole + 6, channel)
        is_history = (target_list == self.history_list)
        card = VideoCard(vid_id, title, url, watched, self, item, is_history=is_history, row_index=row_index)
        if thumbnail_path:
            card.set_thumbnail(thumbnail_path)
        if duration or channel:
            card.set_metadata(duration, channel)
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
            duration = item.data(Qt.ItemDataRole.UserRole + 5) or ""
            channel = item.data(Qt.ItemDataRole.UserRole + 6) or ""
            self.create_card_item(vid_id, title, url, watched, self.history_list,
                                  insert_top=True, thumbnail_path=thumb_path,
                                  duration=duration, channel=channel)

        self.check_empty_state()

    def restore_video(self, vid_id, item):
        tab_id = self.db.get_video_tab(vid_id)
        target_list = self._tab_id_map.get(tab_id)
        if target_list is None or target_list == self.history_list:
            target_list = self.tab_lists[0]
            if self._work_tab_ids:
                self.db.reassign_video_tab(vid_id, self._work_tab_ids[0])

        self.db.restore_video(vid_id)

        list_widget = item.listWidget()
        list_widget.takeItem(list_widget.row(item))

        title = item.data(Qt.ItemDataRole.UserRole + 3)
        url = item.data(Qt.ItemDataRole.UserRole)
        watched = item.data(Qt.ItemDataRole.UserRole + 2)
        thumb_path = item.data(Qt.ItemDataRole.UserRole + 4) or ""
        duration = item.data(Qt.ItemDataRole.UserRole + 5) or ""
        channel = item.data(Qt.ItemDataRole.UserRole + 6) or ""
        self.create_card_item(vid_id, title, url, watched, target_list, insert_top=True,
                              thumbnail_path=thumb_path, duration=duration, channel=channel)
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

        if is_safe_youtube_url(url):
            self._add_video_url(url)

    @staticmethod
    def _extract_playlist_id(url):
        m = re.search(r'[?&]list=([a-zA-Z0-9_-]+)', url)
        return m.group(1) if m else None

    def _add_video_url(self, url):
        # Check for playlist URL first
        playlist_id = self._extract_playlist_id(url)
        if playlist_id and '/playlist' in url:
            self._import_playlist(url)
            return

        ui_index = self.tabs.currentIndex()
        if ui_index >= self.work_tab_count:
            ui_index = 0
        tab_id = self._work_tab_ids[ui_index]

        vid_id = self.extract_video_id(url)
        existing_id = (self.db.find_video_by_video_id(vid_id) if vid_id
                       else self.db.find_video_by_url(url))
        if existing_id:
            self.db.hard_delete_video(existing_id)
            self.load_data()

        new_order = self.db.get_min_row_order() - 1

        last_id = self.db.add_video(url, "Loading info...", tab_id, new_order)

        self.create_card_item(last_id, "Loading info...", url, 0, self._tab_id_map[tab_id], insert_top=True)
        self.check_empty_state()
        self._executor.submit(self.fetch_title, url, last_id, tab_id)

    def _import_playlist(self, url):
        self._playlist_worker = PlaylistFetchWorker(url)
        self._playlist_worker.video_found.connect(self._on_playlist_video_found)
        self._playlist_worker.progress.connect(self._on_playlist_progress)
        self._playlist_worker.finished_signal.connect(self._on_playlist_finished)
        self._playlist_worker.error.connect(self._on_playlist_error)

        self.playlist_progress.setValue(0)
        self.playlist_progress.show()
        self._playlist_worker.start()

    def _on_playlist_video_found(self, url, title):
        ui_index = self.tabs.currentIndex()
        if ui_index >= self.work_tab_count:
            ui_index = 0
        tab_id = self._work_tab_ids[ui_index]

        # Skip duplicates (match by video ID to catch URL variants)
        vid_id = self.extract_video_id(url)
        if (vid_id and self.db.find_video_by_video_id(vid_id)) or self.db.find_video_by_url(url):
            return

        new_order = self.db.get_min_row_order() - 1
        last_id = self.db.add_video(url, title, tab_id, new_order)
        self.create_card_item(last_id, title, url, 0, self._tab_id_map[tab_id], insert_top=True)
        self.check_empty_state()
        self._executor.submit(self.fetch_title, url, last_id, tab_id)

    def _on_playlist_progress(self, current, total):
        self.playlist_progress.setMaximum(total)
        self.playlist_progress.setValue(current)

    def _on_playlist_finished(self):
        self.playlist_progress.hide()

    def _on_playlist_error(self, msg):
        self.playlist_progress.hide()
        logger.warning("Playlist import error: %s", msg)

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

        if is_safe_youtube_url(url):
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

    @staticmethod
    def _parse_iso_duration(iso):
        """Parse ISO 8601 duration like 'PT1H2M34S' → '1:02:34'."""
        match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', iso or '')
        if not match:
            return ""
        h, m, s = (int(x) if x else 0 for x in match.groups())
        if h:
            return f"{h}:{m:02d}:{s:02d}"
        return f"{m}:{s:02d}"

    def fetch_title(self, url, vid_id, tab_id):
        title = url
        thumb_path = ""
        duration = ""
        channel = ""
        try:
            raw = fetch_bounded(url, _PAGE_MAX_BYTES)
            if raw is not None:
                page_text = raw.decode("utf-8", errors="replace")
                soup = BeautifulSoup(page_text, 'html.parser')
                if soup.title:
                    title = soup.title.string.replace("- YouTube", "").strip()

                # Extract duration from JSON-LD
                for script in soup.find_all('script', type='application/ld+json'):
                    try:
                        data = json.loads(script.string)
                        if isinstance(data, dict) and 'duration' in data:
                            duration = self._parse_iso_duration(data['duration'])
                            break
                    except (json.JSONDecodeError, TypeError):
                        pass
        except Exception:
            logger.warning("Failed to fetch title for %s", url, exc_info=True)

        # Fetch channel name via oEmbed
        try:
            oembed_url = f"https://www.youtube.com/oembed?url={url}&format=json"
            raw = fetch_bounded(oembed_url, _OEMBED_MAX_BYTES)
            if raw is not None:
                channel = json.loads(raw).get('author_name', '')
        except Exception:
            logger.warning("Failed to fetch channel for %s", url, exc_info=True)

        try:
            video_id = self.extract_video_id(url)
            if video_id:
                thumb_url = f"https://img.youtube.com/vi/{video_id}/mqdefault.jpg"
                raw = fetch_bounded(thumb_url, _THUMB_MAX_BYTES)
                if raw is not None:
                    thumb_path = os.path.join(self.db.thumbnails_dir, f"{video_id}.jpg")
                    with open(thumb_path, 'wb') as f:
                        f.write(raw)
        except Exception:
            logger.warning("Failed to fetch thumbnail for %s", url, exc_info=True)

        self.update_title_signal.emit(title, thumb_path, vid_id, tab_id, duration, channel)

    def update_item_title(self, title, thumb_path, vid_id, tab_id, duration, channel):
        self.db.update_video_title(vid_id, title, thumb_path, duration, channel)

        target_list = self._tab_id_map.get(tab_id, self.tab_lists[0])

        for i in range(target_list.count()):
            item = target_list.item(i)
            widget = target_list.itemWidget(item)
            if widget and widget.vid_id == vid_id:
                item.setData(Qt.ItemDataRole.UserRole + 3, title)
                item.setData(Qt.ItemDataRole.UserRole + 4, thumb_path)
                item.setData(Qt.ItemDataRole.UserRole + 5, duration)
                item.setData(Qt.ItemDataRole.UserRole + 6, channel)
                widget.title_lbl.setText(title)
                widget.set_metadata(duration, channel)
                if thumb_path:
                    widget.set_thumbnail(thumb_path)
                break

        if self._opened_by_drag:
            QTimer.singleShot(800, self._hide_after_drag)

    def _hide_after_drag(self):
        if self._opened_by_drag:
            self._opened_by_drag = False
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
