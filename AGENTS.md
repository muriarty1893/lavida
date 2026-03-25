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
│   ├── workers.py             # GlobalInputListener, PlaylistFetchWorker - background QThread workers
│   ├── obsidian_export.py     # ObsidianExporter - two-way Obsidian vault sync
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

- **Database** (`src/database.py`): Centralized database operations - video CRUD, settings persistence, schema migrations. Includes silent watchers for Obsidian sync (`mark_watched_silent`, `mark_unwatched_silent`, `get_video_by_url`).
- **LavidaApp** (`src/ui/main_window.py`): Main application window. Handles drag-drop, window resizing, tab management, fullscreen detection, title fetching, and all core UI.
- **SettingsDialog** (`src/ui/settings_dialog.py`): Settings panel with theme selection, startup options, activation key rebinding, and shortcut reference.
- **VideoCard** (`src/ui/widgets.py`): Individual video item widget. Displays thumbnail with duration badge overlay, title, channel subtitle, and watched/unwatched state. Exposes `set_metadata(duration, channel)` to populate those fields after creation.
- **DraggableListWidget** (`src/ui/widgets.py`): Tab list widget supporting drag-and-drop reordering of videos.
- **DragHandle** (`src/ui/widgets.py`): Visual grip handle (6-dot pattern) for dragging videos.
- **ThumbnailPreview** (`src/ui/widgets.py`): Singleton popup that shows an enlarged thumbnail on hover, positioned to the right of the main window.
- **GlobalInputListener** (`src/workers.py`): QThread that listens for a configurable activation key (mouse button, scroll direction, or keyboard key) to toggle window visibility. Supports a detection mode for rebinding from the settings dialog.
- **PlaylistFetchWorker** (`src/workers.py`): QThread that scrapes `ytInitialData` JSON from a YouTube playlist page to extract video IDs and titles. Emits `video_found(url, title)`, `progress(current, total)`, `finished_signal()`, and `error(msg)` signals. Handles only the first ~100 videos (no pagination).
- **ObsidianExporter** (`src/obsidian_export.py`): Two-way sync with Obsidian vaults. Watches `vault_path/Lavida/` directory for markdown file changes and syncs watched state bidirectionally. Exports app data as markdown tabs, imports checkbox state from Obsidian without UI updates (silent sync).

## Architecture

### UI Design
- **Frameless, translucent window** with custom drag/resize handling
- **Dark warm theme** with 5 switchable accent color presets (Rust, Ocean, Forest, Amethyst, Cyan)
- **Dynamic tabs**: N renameable work tabs (default 3) + 1 locked History tab + "+" tab to add new tabs; work tabs can be reordered by dragging
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
| Right-click video | Open context menu (open, copy URL, watch state, move to tab, delete/restore) |
| Middle-click (scroll click) video | Delete to history |
| Drag handle | Reorder videos within tab |
| Drag tab | Reorder work tabs (History and "+" are locked) |
| Activation key (global, configurable) | Toggle window visibility |
| Drag window edges/corners | Resize window |
| Drag title bar area | Move window |
| "+ Add" button | Grab current browser URL and add video (or import playlist) |
| Search button | Show/hide search input to filter videos |
| Settings button (⚙) | Open settings panel |
| Hide button | Hide window |
| Quit button | Exit application |
| Double-click tab | Rename tab |

### Database Schema
SQLite database (`lavida.db`) stores:
- **videos**: id, url, title, watched, tab_id, row_order, is_deleted, thumbnail_path, duration, channel, deleted_at
- **tabs**: id, name, sort_order, is_history
- **settings**: window position/size, theme, tab names, start_visible, obsidian_vault_path (persisted across sessions)

### Obsidian Two-Way Sync
Lavida can sync with Obsidian vaults via markdown files in a `Lavida/` folder. When configured:

1. **Export (App → Obsidian)**: Videos are written to markdown files (one per tab) with format:
   ```markdown
   - [x] [Video Title](https://youtube.com/watch?v=...)  # checked = watched
   - [ ] [Other Video](https://youtube.com/watch?v=...)  # unchecked = unwatched
   ```

2. **Import (Obsidian → App)**: Changes to markdown checkbox state are detected via `QFileSystemWatcher` and synced silently (no UI updates) using `mark_watched_silent()` and `mark_unwatched_silent()`. A debounce timer (1s) prevents rapid re-reads.

3. **Loop Prevention**: `_writing` flag prevents reading vault while app is exporting, debounce timers prevent thrashing.

4. **Tab Renaming**: When a tab is renamed in the app, the corresponding `.md` file is renamed in the vault.

### Threading Model
- **Main thread**: PyQt6 event loop, UI rendering
- **GlobalInputListener thread**: pynput mouse listener for global hotkey detection (0.4s debounce)
- **Title fetching**: Background thread for HTTP requests (does not block UI)
- **Fullscreen check**: QTimer polling at 100ms intervals
- **Obsidian watcher thread**: `QFileSystemWatcher` monitors `vault_path/Lavida/` for changes, fires read debounce timer (1s) when files modified

## Database API Reference

### Public Methods

**Video Operations**
- `add_video(url, title, tab_id, row_order) → vid_id` — Create video entry
- `update_video_title(vid_id, title, thumbnail_path="", duration="", channel="")` — Update title, thumbnail, and metadata
- `update_video_order(vid_id, order)` — Update display order
- `mark_watched(vid_id)` — Mark watched and emit `data_changed` signal
- `mark_unwatched(vid_id)` — Mark unwatched and emit `data_changed` signal
- `mark_watched_silent(vid_id)` — Mark watched without signal (Obsidian import use only)
- `mark_unwatched_silent(vid_id)` — Mark unwatched without signal (Obsidian import use only)
- `soft_delete_video(vid_id)` — Move to history (is_deleted=1, sets deleted_at timestamp)
- `restore_video(vid_id)` — Restore from history (clears deleted_at)
- `hard_delete_video(vid_id)` — Permanently delete
- `reassign_video_tab(vid_id, tab_id)` — Move video to a different tab
- `get_video_by_url(url) → (id, watched) | None` — Lookup video for Obsidian sync
- `find_video_by_url(url) → vid_id | None` — Lookup active video
- `get_video_tab(vid_id) → tab_id` — Get tab assignment
- `get_active_videos() → [(id, title, url, watched, tab_id, thumbnail_path, duration, channel), ...]` — All active videos
- `get_deleted_videos() → [(id, title, url, watched, thumbnail_path, duration, channel), ...]` — History videos, sorted by deleted_at DESC

**Tab Operations**
- `get_tabs() → [(id, name, sort_order, is_history), ...]` — All tabs
- `add_tab(name, sort_order) → tab_id` — Create new work tab
- `delete_tab(tab_id)` — Soft-delete all videos in tab, remove tab row
- `rename_tab(tab_id, new_name)` — Rename a tab
- `update_tab_sort_orders(tab_ids)` — Persist drag-reordered tab order

**Bulk Operations**
- `bulk_soft_delete(vid_ids)` — Move multiple videos to history (sets deleted_at)
- `bulk_mark_watched(vid_ids)` — Mark multiple watched
- `bulk_move_to_tab(vid_ids, tab_id)` — Move multiple to tab

**Settings**
- `save_setting(key, value)` — Persist key-value pair
- `load_setting(key, default=None)` — Retrieve saved setting
- `save_window_settings(x, y, width, height)` — Save window geometry
- `load_window_settings() → (x, y, width, height) | None` — Restore geometry

**Utility**
- `get_min_row_order() → int` — Get lowest row order value
- `close()` — Close database connection (called on app shutdown)

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
