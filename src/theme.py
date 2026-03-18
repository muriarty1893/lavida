"""Shared color tokens and theme definitions for Lavida."""

# -- Colors (updated by apply_theme) --
CLR_BASE = "#1a1714"
CLR_SURFACE = "#231f1b"
CLR_ELEVATED = "#2e2921"
CLR_BORDER = "#3a332c"
CLR_BORDER_HOVER = "#524a40"
CLR_TEXT = "#e8e0d4"
CLR_TEXT_DIM = "#8a7f73"
CLR_TEXT_MUTED = "#6b6259"

CLR_ACCENT = "#c96442"
CLR_ACCENT_HOVER = "#db7a58"
CLR_ACCENT_SUBTLE = "rgba(201, 100, 66, 0.12)"
_ACCENT_RGB = "201, 100, 66"

CLR_CARD_BG = "rgba(255, 255, 255, 0.035)"
CLR_CARD_BG_ALT = "rgba(255, 255, 255, 0.055)"
CLR_CARD_HOVER = "rgba(255, 255, 255, 0.07)"

THEMES = {
    "rust": {
        "label": "Rust",
        "base": "#1a1714", "surface": "#231f1b", "elevated": "#2e2921",
        "border": "#3a332c", "border_hover": "#524a40",
        "text": "#e8e0d4", "text_dim": "#8a7f73", "text_muted": "#6b6259",
        "accent": "#c96442", "accent_hover": "#db7a58", "rgb": "201, 100, 66",
    },
    "ocean": {
        "label": "Ocean",
        "base": "#131820", "surface": "#1a2030", "elevated": "#222a3a",
        "border": "#2d3748", "border_hover": "#3e4f66",
        "text": "#d4dfe8", "text_dim": "#7088a0", "text_muted": "#546b82",
        "accent": "#4a90d9", "accent_hover": "#6aacef", "rgb": "74, 144, 217",
    },
    "forest": {
        "label": "Forest",
        "base": "#141a16", "surface": "#1b2420", "elevated": "#243029",
        "border": "#2f3d34", "border_hover": "#425a4c",
        "text": "#d4e8dc", "text_dim": "#6f9a7e", "text_muted": "#547662",
        "accent": "#4a9e5c", "accent_hover": "#62b876", "rgb": "74, 158, 92",
    },
    "amethyst": {
        "label": "Amethyst",
        "base": "#18141e", "surface": "#211c2b", "elevated": "#2c2638",
        "border": "#3a3248", "border_hover": "#504668",
        "text": "#e0d8ec", "text_dim": "#8878a0", "text_muted": "#6a5e82",
        "accent": "#8b5cf6", "accent_hover": "#a47ef7", "rgb": "139, 92, 246",
    },
    "cyan": {
        "label": "Cyan",
        "base": "#121a1c", "surface": "#192428", "elevated": "#212f34",
        "border": "#2c3e44", "border_hover": "#3e5860",
        "text": "#d4e6ea", "text_dim": "#6a9aa6", "text_muted": "#507e88",
        "accent": "#00bcd4", "accent_hover": "#2cd6ec", "rgb": "0, 188, 212",
    },
}

DEFAULT_THEME = "rust"


def apply_theme(name):
    """Apply a theme by name, updating module-level colors."""
    global CLR_BASE, CLR_SURFACE, CLR_ELEVATED, CLR_BORDER, CLR_BORDER_HOVER
    global CLR_TEXT, CLR_TEXT_DIM, CLR_TEXT_MUTED
    global CLR_ACCENT, CLR_ACCENT_HOVER, CLR_ACCENT_SUBTLE, _ACCENT_RGB

    t = THEMES.get(name, THEMES[DEFAULT_THEME])

    CLR_BASE = t["base"]
    CLR_SURFACE = t["surface"]
    CLR_ELEVATED = t["elevated"]
    CLR_BORDER = t["border"]
    CLR_BORDER_HOVER = t["border_hover"]
    CLR_TEXT = t["text"]
    CLR_TEXT_DIM = t["text_dim"]
    CLR_TEXT_MUTED = t["text_muted"]

    CLR_ACCENT = t["accent"]
    CLR_ACCENT_HOVER = t["accent_hover"]
    _ACCENT_RGB = t["rgb"]
    CLR_ACCENT_SUBTLE = f"rgba({_ACCENT_RGB}, 0.12)"


def accent_rgba(opacity):
    """Get accent color with custom opacity."""
    return f"rgba({_ACCENT_RGB}, {opacity})"
