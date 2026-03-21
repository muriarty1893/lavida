"""Settings dialog for Lavida."""

import os

import src.theme as theme
from src.workers import activation_key_label
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                             QPushButton, QCheckBox, QFrame, QLineEdit,
                             QFileDialog)
from PyQt6.QtCore import Qt, QTimer


class SettingsDialog(QDialog):
    def __init__(self, parent, db):
        super().__init__(parent)
        self.db = db
        self.parent_window = parent
        self.current_theme = db.load_setting('theme', theme.DEFAULT_THEME)
        self._detecting = False

        self.setWindowTitle("Settings")
        self.setFixedSize(300, 550)
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
            margin-top: 10px;
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
        layout.setSpacing(10)

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

        # Activation key
        activation_layout = QHBoxLayout()
        activation_layout.setContentsMargins(0, 4, 0, 4)
        activation_lbl = QLabel("Activation key")
        activation_lbl.setStyleSheet(f"color: {theme.CLR_TEXT}; font-size: 12px;")

        current_key = self.db.load_setting('activation_key', 'scroll_right')
        self.activation_btn = QPushButton(activation_key_label(current_key))
        self.activation_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.activation_btn.setStyleSheet(f"""
            QPushButton {{
                background: {theme.CLR_ELEVATED};
                color: {theme.CLR_TEXT};
                border: 1px solid {theme.CLR_BORDER};
                border-radius: 4px;
                padding: 4px 12px;
                font-size: 11px;
                font-weight: 600;
                min-width: 120px;
            }}
            QPushButton:hover {{
                border-color: {theme.CLR_BORDER_HOVER};
            }}
        """)
        self.activation_btn.clicked.connect(self._on_activation_btn_clicked)

        activation_layout.addWidget(activation_lbl)
        activation_layout.addStretch()
        activation_layout.addWidget(self.activation_btn)
        layout.addLayout(activation_layout)

        layout.addWidget(self._separator())

        # -- Obsidian Vault --
        layout.addWidget(self._section_label("OBSIDIAN VAULT"))

        vault_row = QHBoxLayout()
        vault_row.setContentsMargins(0, 4, 0, 4)
        vault_row.setSpacing(6)

        vault_lbl = QLabel("Vault path")
        vault_lbl.setStyleSheet(f"color: {theme.CLR_TEXT}; font-size: 12px;")

        self.vault_input = QLineEdit()
        self.vault_input.setPlaceholderText("Not configured")
        self.vault_input.setReadOnly(True)
        vault_path = self.db.load_setting('obsidian_vault_path', '')
        if vault_path:
            self.vault_input.setText(vault_path)
        self.vault_input.setStyleSheet(f"""
            QLineEdit {{
                background: {theme.CLR_BASE};
                border: 1px solid {theme.CLR_BORDER};
                border-radius: 4px;
                color: {theme.CLR_TEXT};
                padding: 3px 6px;
                font-size: 11px;
            }}
        """)

        browse_btn = QPushButton("Browse")
        browse_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        browse_btn.setStyleSheet(f"""
            QPushButton {{
                background: {theme.CLR_ELEVATED};
                color: {theme.CLR_TEXT};
                border: 1px solid {theme.CLR_BORDER};
                border-radius: 4px;
                padding: 4px 12px;
                font-size: 11px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                border-color: {theme.CLR_BORDER_HOVER};
            }}
        """)
        browse_btn.clicked.connect(self._browse_vault)

        vault_row.addWidget(vault_lbl)
        vault_row.addWidget(self.vault_input, 1)
        vault_row.addWidget(browse_btn)
        layout.addLayout(vault_row)

        layout.addWidget(self._separator())

        # -- Shortcuts --
        layout.addWidget(self._section_label("SHORTCUTS"))

        self._toggle_key_lbl = None
        shortcuts = [
            ("Left click", "Open video"),
            ("Right click", "Mark unwatched"),
            ("Middle click", "Delete to history"),
            (activation_key_label(current_key), "Toggle window"),
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
            if action == "Toggle window":
                self._toggle_key_lbl = key_lbl

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

    def _browse_vault(self):
        start = self.vault_input.text() or os.path.expanduser("~")
        path = QFileDialog.getExistingDirectory(self, "Select Obsidian Vault", start)
        if path:
            self.vault_input.setText(path)
            self.db.save_setting('obsidian_vault_path', path)
            self.parent_window.configure_obsidian_export(path)

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

    def _on_activation_btn_clicked(self):
        if self._detecting:
            return
        self._detecting = True
        self.activation_btn.setText("Press any key...")
        self.activation_btn.setStyleSheet(f"""
            QPushButton {{
                background: {theme.CLR_ACCENT};
                color: {theme.CLR_TEXT};
                border: 1px solid {theme.CLR_ACCENT};
                border-radius: 4px;
                padding: 4px 12px;
                font-size: 11px;
                font-weight: 600;
                min-width: 120px;
            }}
        """)

        listener = self.parent_window.listener
        listener.detected_signal.connect(self._on_key_detected)
        # Small delay so the button click itself isn't captured
        QTimer.singleShot(300, self._start_detecting)

    def _start_detecting(self):
        self.parent_window.listener.detecting = True
        # Timeout: reset after 5s if nothing detected
        self._detect_timer = QTimer()
        self._detect_timer.setSingleShot(True)
        self._detect_timer.timeout.connect(self._on_detect_timeout)
        self._detect_timer.start(5000)

    def _on_key_detected(self, key):
        self._detect_timer.stop()
        self.parent_window.listener.detected_signal.disconnect(self._on_key_detected)
        self._detecting = False

        self.db.save_setting('activation_key', key)
        self.parent_window.listener.activation_key = key

        label = activation_key_label(key)
        self.activation_btn.setText(label)
        self._reset_activation_btn_style()
        if self._toggle_key_lbl:
            self._toggle_key_lbl.setText(label)

    def _on_detect_timeout(self):
        self.parent_window.listener.detecting = False
        try:
            self.parent_window.listener.detected_signal.disconnect(self._on_key_detected)
        except TypeError:
            pass
        self._detecting = False

        label = activation_key_label(self.db.load_setting('activation_key', 'scroll_right'))
        self.activation_btn.setText(label)
        self._reset_activation_btn_style()

    def _reset_activation_btn_style(self):
        self.activation_btn.setStyleSheet(f"""
            QPushButton {{
                background: {theme.CLR_ELEVATED};
                color: {theme.CLR_TEXT};
                border: 1px solid {theme.CLR_BORDER};
                border-radius: 4px;
                padding: 4px 12px;
                font-size: 11px;
                font-weight: 600;
                min-width: 120px;
            }}
            QPushButton:hover {{
                border-color: {theme.CLR_BORDER_HOVER};
            }}
        """)
