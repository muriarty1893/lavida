# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added
- Settings panel with theme selection, startup options, and shortcut reference
- 5 accent color themes: Rust (default), Ocean, Forest, Amethyst, Cyan
- Customizable tab names (double-click to rename)
- "No results found" message when search has no matches
- "Start visible" option in settings
- Logging for error visibility (replaces silent `except: pass`)

### Changed
- Redesigned UI with semantic color system, polished buttons, tabs, cards, and search input
- Updated button labels for clarity ("+ Add", "Hide", "Quit")
- Extracted database operations into `Database` class (`src/database.py`)
- Extracted color tokens into shared `src/theme.py` module

## [0.1.0] - 2026-02-23

### Added
- Initial release
- Drag-and-drop YouTube link management
- 3 tabs for organizing videos + history tab
- Auto-fetch video titles and thumbnails
- Configurable activation key to toggle window visibility (set on first launch, changeable in settings)
- Always-on-top frameless window
- Left click to open and mark as watched
- Right click to mark as unwatched
- Middle click to delete
- Drag-to-reorder within tabs
- Persistent storage via SQLite
- Auto-hide when another app goes fullscreen
- Search/filter across videos
- "Add current video" button (grabs URL from active browser)
- Video thumbnail preview on hover
