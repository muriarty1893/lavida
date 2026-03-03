# Lavida - Project Rules

Rules for AI agents working on this repository.

---

## Project Overview

Lavida is a lightweight, always-on-top desktop widget for managing YouTube video links. Built with PyQt6, it provides a frameless, translucent dark-themed UI where users can save, organize, and track YouTube videos across multiple tabs.

## File Organization

```
lavida/
├── main.py                    # Entry point; creates QApplication and LavidaApp
├── requirements.txt           # Python package dependencies
├── README.md                  # Project documentation with screenshots
├── run.sh                     # Bash script to activate venv and run app
├── img/                       # Screenshots for README
│   └── *.png
├── src/
│   ├── __init__.py
│   ├── workers.py             # GlobalInputListener - QThread for mouse scroll events
│   └── ui/
│       ├── __init__.py
│       ├── main_window.py     # LavidaApp - main window, DB operations, drag-drop, UI setup
│       └── widgets.py         # VideoCard, DraggableListWidget, DragHandle components
└── lavida.db                  # SQLite database (gitignored, auto-generated)
```

**Generated/runtime files (DO NOT commit):**
- `lavida.db` - SQLite database, auto-created on first run
- `startup_log.txt` - Runtime log file
- `run.sh` - Local startup script

## Tech Stack

- **Python 3** - Programming language
- **PyQt6** - GUI framework (desktop application)
- **SQLite3** - Persistent storage (built-in, no extra dependency)
- **requests** - HTTP client for fetching YouTube page titles
- **BeautifulSoup4** - HTML parsing for extracting video titles
- **pynput** - Global mouse/keyboard listener for system-wide hotkeys

## Key Classes

- **LavidaApp** (`src/ui/main_window.py`): Main application window. Handles database operations, drag-drop, window resizing, tab management, and all core functionality.
- **VideoCard** (`src/ui/widgets.py`): Individual video item widget displaying title with watched/unwatched state.
- **DraggableListWidget** (`src/ui/widgets.py`): Tab list widget supporting drag-and-drop reordering of videos.
- **DragHandle** (`src/ui/widgets.py`): Visual grip handle for dragging videos.
- **GlobalInputListener** (`src/workers.py`): QThread that listens for mouse scroll right event to toggle window visibility.

## Architecture

### UI Design
- **Frameless, translucent window** with custom drag/resize handling
- **Dark theme** with cyan (`#00bcd4`) accent color
- **4 tabs**: 3 work tabs + 1 History tab
- **Always-on-top** window for quick access

### User Interactions
| Action | Effect |
|--------|--------|
| Left-click video | Open in browser + mark watched |
| Right-click video | Mark unwatched |
| Middle-click (scroll click) video | Delete to history |
| Drag handle | Reorder videos within tab |
| Mouse scroll right (global) | Toggle window visibility |
| Drag window edges/corners | Resize window |
| Drag title bar area | Move window |

### Database Schema
SQLite database (`lavida.db`) stores:
- **videos**: url, title, watched status, tab assignment, display order, deletion flag
- **settings**: window position and size (persisted across sessions)

### Threading Model
- **Main thread**: PyQt6 event loop, UI rendering
- **GlobalInputListener thread**: pynput mouse listener for global hotkey detection
- **Title fetching**: Background thread for HTTP requests (does not block UI)

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
- All database operations are in `LavidaApp` (centralized)
- Use `sqlite3` context managers for safe connection handling
- Database is auto-created on first run if not present

### Styling
- All widget styling uses PyQt6 `setStyleSheet()` with inline CSS
- Primary accent color: `#00bcd4` (cyan)
- Background: semi-transparent dark (`rgba(30, 30, 30, 230)`)
- Text: white (`#ffffff`)

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
