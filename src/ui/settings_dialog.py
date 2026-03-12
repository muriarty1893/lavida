"""Settings dialog for Lavida."""

import src.theme as theme
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                             QPushButton, QCheckBox, QFrame)
from PyQt6.QtCore import Qt


class SettingsDialog(QDialog):
    def __init__(self, parent, db):
        super().__init__(parent)
        self.db = db
        self.parent_window = parent
        self.current_theme = db.load_setting('theme', theme.DEFAULT_THEME)

        self.setWindowTitle("Settings")
        self.setFixedSize(300, 440)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        self._apply_dialog_style()
        self._build_ui()

    def _apply_dialog_style(self):
        self.setStyleSheet(f"""
            QDialog {{
                background: {theme.CLR_SURFACE};
            }}
            QLabel {{
                color: {theme.CLR_TEXT};
                background: transparent;
                border: none;
            }}
            QCheckBox {{
                color: {theme.CLR_TEXT};
                spacing: 8px;
                font-size: 12px;
            }}
            QCheckBox::indicator {{
                width: 16px;
                height: 16px;
                border: 1px solid {theme.CLR_BORDER_HOVER};
                border-radius: 3px;
                background: {theme.CLR_BASE};
            }}
            QCheckBox::indicator:checked {{
                background: {theme.CLR_ACCENT};
                border-color: {theme.CLR_ACCENT};
            }}
        """)

    def _section_label(self, text):
        lbl = QLabel(text)
        lbl.setStyleSheet(f"""
            color: {theme.CLR_TEXT_DIM};
            font-size: 10px;
            font-weight: 700;
            letter-spacing: 1px;
            padding: 0px;
            margin-top: 8px;
        """)
        return lbl

    def _separator(self):
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet(f"background: {theme.CLR_BORDER}; max-height: 1px; border: none;")
        return line

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(8)

        # -- Appearance --
        layout.addWidget(self._section_label("APPEARANCE"))

        theme_layout = QHBoxLayout()
        theme_layout.setSpacing(8)
        self._theme_buttons = {}

        for name, data in theme.THEMES.items():
            btn = QPushButton()
            btn.setFixedSize(36, 36)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setToolTip(data["label"])
            btn.clicked.connect(lambda checked, n=name: self._select_theme(n))
            self._theme_buttons[name] = btn
            theme_layout.addWidget(btn)

        theme_layout.addStretch()
        layout.addLayout(theme_layout)
        self._update_theme_buttons()

        layout.addWidget(self._separator())

        # -- General --
        layout.addWidget(self._section_label("GENERAL"))

        self.start_visible_cb = QCheckBox("Start visible on launch")
        self.start_visible_cb.setChecked(self.db.load_setting('start_visible', '0') == '1')
        self.start_visible_cb.toggled.connect(self._on_start_visible_changed)
        layout.addWidget(self.start_visible_cb)

        layout.addWidget(self._separator())

        # -- Shortcuts --
        layout.addWidget(self._section_label("SHORTCUTS"))

        shortcuts = [
            ("Left click", "Open video"),
            ("Right click", "Mark unwatched"),
            ("Middle click", "Delete to history"),
            ("Scroll right", "Toggle window"),
            ("Double-click tab", "Rename tab"),
            ("Escape", "Close search"),
        ]
        for key, action in shortcuts:
            row = QHBoxLayout()
            row.setContentsMargins(0, 2, 0, 2)

            key_lbl = QLabel(key)
            key_lbl.setStyleSheet(f"""
                color: {theme.CLR_TEXT};
                font-size: 11px;
                font-weight: 600;
                background: {theme.CLR_ELEVATED};
                border-radius: 4px;
                padding: 3px 8px;
            """)

            action_lbl = QLabel(action)
            action_lbl.setStyleSheet(f"""
                color: {theme.CLR_TEXT_DIM};
                font-size: 11px;
            """)

            row.addWidget(key_lbl)
            row.addStretch()
            row.addWidget(action_lbl)
            layout.addLayout(row)

        layout.addStretch()

        # -- Close button --
        close_btn = QPushButton("Close")
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background: {theme.CLR_ELEVATED};
                color: {theme.CLR_TEXT};
                border: 1px solid {theme.CLR_BORDER};
                border-radius: 6px;
                font-size: 12px;
                font-weight: 600;
                padding: 8px 0px;
            }}
            QPushButton:hover {{
                background: {theme.CLR_BORDER};
                border-color: {theme.CLR_BORDER_HOVER};
            }}
        """)
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

    def _update_theme_buttons(self):
        for name, btn in self._theme_buttons.items():
            data = theme.THEMES[name]
            is_active = (name == self.current_theme)
            border = f"3px solid {theme.CLR_TEXT}" if is_active else f"2px solid {theme.CLR_BORDER}"
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: {data['accent']};
                    border: {border};
                    border-radius: 18px;
                }}
                QPushButton:hover {{
                    border: 3px solid {theme.CLR_TEXT_DIM};
                }}
            """)

    def _select_theme(self, name):
        self.current_theme = name
        self.db.save_setting('theme', name)
        theme.apply_theme(name)
        self._update_theme_buttons()
        self._apply_dialog_style()
        self.parent_window.refresh_styles()

    def _on_start_visible_changed(self, checked):
        self.db.save_setting('start_visible', '1' if checked else '0')
