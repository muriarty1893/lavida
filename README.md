# Lavida

A lightweight, always-on-top Linux desktop widget for managing YouTube video links. Drop links, organize across tabs, and pick up where you left off. Mouse scroll right to toggle window visibility (global).

## Features

- **Drag & drop** YouTube URLs onto the window to save them
- **Customizable tabs** for organizing videos + a history tab for deleted items
- **Auto-fetches** video titles and thumbnails
- **Always on top** with frameless, resizable window
- **Global hotkey** (mouse scroll right) to toggle visibility
- **Persistent storage** via local SQLite database
- **Auto-hide** when another app goes fullscreen
- **Search** across all your saved videos
- **Drag to reorder** within tabs
- **Theme support** with 5 accent color presets
- **Settings panel** for theme, startup, and shortcut reference

## Installation

**Requirements:** Python 3.10+, Linux (X11)

```bash
git clone https://github.com/muriarty1893/lavida.git
cd lavida
pip install -r requirements.txt
```

## Usage

```bash
python main.py
```

### Controls

| Action | Effect |
| --- | --- |
| Drag & drop URL | Add video to current tab |
| Left click | Open in browser, mark as watched |
| Right click | Mark as unwatched |
| Middle click | Delete to history |
| Mouse scroll right | Toggle window visibility (global) |
| Double-click tab | Rename tab |

### Buttons

- **+ Add** - Grab the current browser URL and add it
- **Search** - Filter videos by title
- **⚙** - Open settings panel
- **Hide** - Hide the window (bring back with scroll right)
- **Quit** - Exit the application

## Screenshots

![](img/ss1.png)

![](img/ss2.png)

![](img/ss3.png)

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

[MIT](LICENSE)
