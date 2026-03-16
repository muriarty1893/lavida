# Lavida - Project Rules

Rules for AI agents working on this repository.

---

## Project Overview

Lavida is a lightweight, always-on-top desktop widget for managing YouTube video links. Built with PyQt6, it provides a frameless, translucent dark-themed UI where users can save, organize, and track YouTube videos across multiple tabs. Features include thumbnail caching, fullscreen detection, search/filter, and global hotkey support.

## File Organization

```
lavida/
├── main.py                    # Entry point; creates QApplication and LavidaApp
├── requirements.txt           # Python package dependencies
├── pyproject.toml             # Project metadata and configuration
├── README.md                  # Project documentation with screenshots
├── AGENTS.md                  # AI agent rules and conventions
├── CONTRIBUTING.md            # Contribution guidelines
├── CODE_OF_CONDUCT.md         # Community code of conduct
├── CHANGELOG.md               # Version history
├── LICENSE                    # MIT license
├── .editorconfig              # Editor configuration (4-space indent, UTF-8)
├── .gitignore                 # Git ignore patterns
├── img/                       # Screenshots for README
│   └── *.png
├── src/
│   ├── __init__.py
│   ├── database.py            # Database class - centralized DB operations
│   ├── theme.py               # Shared color tokens, theme presets, apply_theme()
│   ├── workers.py             # GlobalInputListener - QThread for mouse scroll events
│   └── ui/
│       ├── __init__.py
│       ├── main_window.py     # LavidaApp - main window, drag-drop, UI setup
│       ├── settings_dialog.py # SettingsDialog - theme, startup, shortcuts panel
│       └── widgets.py         # VideoCard, DraggableListWidget, DragHandle, ThumbnailPreview
├── thumbnails/                # Cached YouTube thumbnails (gitignored, auto-generated)
│   └── *.jpg
└── lavida.db                  # SQLite database (gitignored, auto-generated)
```

**Generated/runtime files (DO NOT commit):**
- `lavida.db` - SQLite database, auto-created on first run
- `thumbnails/` - Downloaded YouTube thumbnails, auto-created
- `startup_log.txt` - Runtime log file
- `run.sh` - Local startup script

## Tech Stack

- **Python 3.10+** - Programming language
- **PyQt6** - GUI framework (desktop application)
- **SQLite3** - Persistent storage (built-in, no extra dependency)
- **requests** - HTTP client for fetching YouTube page titles
- **BeautifulSoup4** - HTML parsing for extracting video titles
- **pynput** - Global mouse/keyboard listener for system-wide hotkeys

## Key Classes

- **Database** (`src/database.py`): Centralized database operations - video CRUD, settings persistence, schema migrations.
- **LavidaApp** (`src/ui/main_window.py`): Main application window. Handles drag-drop, window resizing, tab management, fullscreen detection, title fetching, and all core UI.
- **SettingsDialog** (`src/ui/settings_dialog.py`): Settings panel with theme selection, startup options, activation key rebinding, and shortcut reference.
- **VideoCard** (`src/ui/widgets.py`): Individual video item widget displaying title and thumbnail with watched/unwatched state.
- **DraggableListWidget** (`src/ui/widgets.py`): Tab list widget supporting drag-and-drop reordering of videos.
- **DragHandle** (`src/ui/widgets.py`): Visual grip handle (6-dot pattern) for dragging videos.
- **ThumbnailPreview** (`src/ui/widgets.py`): Singleton popup that shows an enlarged thumbnail on hover, positioned to the right of the main window.
- **GlobalInputListener** (`src/workers.py`): QThread that listens for a configurable activation key (mouse button, scroll direction, or keyboard key) to toggle window visibility. Supports a detection mode for rebinding from the settings dialog.

## Architecture

### UI Design
- **Frameless, translucent window** with custom drag/resize handling
- **Dark warm theme** with 5 switchable accent color presets (Rust, Ocean, Forest, Amethyst, Cyan)
- **4 tabs**: 3 renameable work tabs + 1 History tab
- **Always-on-top** window for quick access
- **Fullscreen detection** auto-hides when other apps go fullscreen

### Semantic Color System (`src/theme.py`)

Base colors are constant; accent colors change with the selected theme.

| Token | Default Value | Usage |
|-------|-------|-------|
| `CLR_BASE` | `#1a1714` | Very dark brown background |
| `CLR_SURFACE` | `#231f1b` | Slightly lighter surface |
| `CLR_ELEVATED` | `#2e2921` | Elevated elements |
| `CLR_BORDER` | `#3a332c` | Default border |
| `CLR_BORDER_HOVER` | `#524a40` | Hover border |
| `CLR_TEXT` | `#e8e0d4` | Primary text (warm light) |
| `CLR_TEXT_DIM` | `#8a7f73` | Secondary text |
| `CLR_TEXT_MUTED` | `#6b6259` | Tertiary text |
| `CLR_ACCENT` | `#c96442` | Primary accent (changes with theme) |
| `CLR_ACCENT_HOVER` | `#db7a58` | Lighter accent on hover |
| `CLR_ACCENT_SUBTLE` | `rgba(201, 100, 66, 0.12)` | Subtle accent background |

**Theme presets:** Rust (default), Ocean, Forest, Amethyst, Cyan

### User Interactions
| Action | Effect |
|--------|--------|
| Left-click video | Open in browser + mark watched |
| Right-click video | Mark unwatched |
| Middle-click (scroll click) video | Delete to history |
| Drag handle | Reorder videos within tab |
| Activation key (global, configurable) | Toggle window visibility |
| Drag window edges/corners | Resize window |
| Drag title bar area | Move window |
| "+ Add" button | Grab current browser URL and add video |
| Search button | Show/hide search input to filter videos |
| Settings button (⚙) | Open settings panel |
| Hide button | Hide window |
| Quit button | Exit application |
| Double-click tab | Rename tab |

### Database Schema
SQLite database (`lavida.db`) stores:
- **videos**: id, url, title, watched status, tab assignment, display order, deletion flag, thumbnail_path
- **settings**: window position/size, theme, tab names, start_visible (persisted across sessions)

### Threading Model
- **Main thread**: PyQt6 event loop, UI rendering
- **GlobalInputListener thread**: pynput mouse listener for global hotkey detection (0.4s debounce)
- **Title fetching**: Background thread for HTTP requests (does not block UI)
- **Fullscreen check**: QTimer polling at 100ms intervals

## Environment

### Setup

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the application
python main.py
```

### Dependencies (requirements.txt)

- PyQt6==6.10.2
- requests==2.32.5
- beautifulsoup4==4.14.3
- pynput==1.8.1

## Code Conventions

### PyQt6 Patterns
- Use signals/slots for cross-thread communication
- Never access UI elements from worker threads
- Use `QThread` subclasses for background work (not Python `threading`)

### Database Access

- All database operations are in `Database` class (`src/database.py`)
- `LavidaApp` accesses DB via `self.db` instance
- Database is auto-created on first run if not present
- Schema migrations handled via `ALTER TABLE` with try/except

### Styling
- All widget styling uses PyQt6 `setStyleSheet()` with inline CSS
- Use semantic color tokens from `src/theme.py` (imported as `import src.theme as theme`)
- Primary accent color: theme-dependent (default `#c96442` rust/terracotta)
- Background: warm dark brown (`#1a1714`)
- Text: warm light (`#e8e0d4`)
- Font family: Inter, Segoe UI, SF Pro Display (system fallbacks)

### Widget Creation
- Custom widgets inherit from appropriate `QWidget` subclass
- Layout management uses `QVBoxLayout`, `QHBoxLayout`
- Fixed sizes preferred over dynamic for consistent UI

## Git Commit Rules

**Do NOT include any of the following in commit messages:**
- `Co-Authored-By` lines
- `Generated with [Claude Code]` or similar attribution
- Any reference to Claude or AI assistance

Commit messages should be clean and appear as if written by the repository owner.

## Security

- **No credentials in code** - the app does not require authentication
- **Local-only storage** - all data stays in local SQLite database
- **URL validation** - only YouTube URLs should be accepted
- **No network exposure** - desktop-only application, no server component
