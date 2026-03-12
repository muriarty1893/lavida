"""Shared color tokens and theme definitions for Lavida."""

# -- Base colors (constant across all themes) --
CLR_BASE = "#1a1714"
CLR_SURFACE = "#231f1b"
CLR_ELEVATED = "#2e2921"
CLR_BORDER = "#3a332c"
CLR_BORDER_HOVER = "#524a40"
CLR_TEXT = "#e8e0d4"
CLR_TEXT_DIM = "#8a7f73"
CLR_TEXT_MUTED = "#6b6259"

# -- Accent colors (updated by apply_theme) --
CLR_ACCENT = "#c96442"
CLR_ACCENT_HOVER = "#db7a58"
CLR_ACCENT_SUBTLE = "rgba(201, 100, 66, 0.12)"
_ACCENT_RGB = "201, 100, 66"

THEMES = {
    "rust":     {"label": "Rust",     "accent": "#c96442", "accent_hover": "#db7a58", "rgb": "201, 100, 66"},
    "ocean":    {"label": "Ocean",    "accent": "#4287c9", "accent_hover": "#5a9dd8", "rgb": "66, 135, 201"},
    "forest":   {"label": "Forest",   "accent": "#4a9e5c", "accent_hover": "#5cb870", "rgb": "74, 158, 92"},
    "amethyst": {"label": "Amethyst", "accent": "#8b5cf6", "accent_hover": "#a07af7", "rgb": "139, 92, 246"},
    "cyan":     {"label": "Cyan",     "accent": "#00bcd4", "accent_hover": "#26c6da", "rgb": "0, 188, 212"},
}

DEFAULT_THEME = "rust"


def apply_theme(name):
    """Apply a theme by name, updating module-level accent colors."""
    global CLR_ACCENT, CLR_ACCENT_HOVER, CLR_ACCENT_SUBTLE, _ACCENT_RGB
    t = THEMES.get(name, THEMES[DEFAULT_THEME])
    CLR_ACCENT = t["accent"]
    CLR_ACCENT_HOVER = t["accent_hover"]
    _ACCENT_RGB = t["rgb"]
    CLR_ACCENT_SUBTLE = f"rgba({_ACCENT_RGB}, 0.12)"


def accent_rgba(opacity):
    """Get accent color with custom opacity."""
    return f"rgba({_ACCENT_RGB}, {opacity})"
