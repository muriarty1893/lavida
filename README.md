# Lavida

A lightweight, always-on-top desktop widget for managing YouTube video links.

## Setup

```bash
pip install -r requirements.txt
python main.py
```

## How it works

Drag and drop a YouTube link onto the window. The title is fetched automatically. Videos are saved in a local SQLite database and persist across sessions.

The window stays on top of other windows. You can organize videos across 3 tabs and move them between tabs by dragging.

## Controls

| Drag & drop URL > Add a video to the current tab |
| Left click a video > Open in browser, mark as watched |
| Right click a video > Mark as unwatched |
| Middle click a video > Delete to history |
| Mouse scroll right > Toggle window visibility (global) |

- **Close** - Hide the window. Bring it back with mouse scroll right.
- **Disable** - Quit the application completely.

## Screenshots

![](img/Screenshot%20from%202026-02-23%2010-37-06.png)

![](img/Screenshot%20from%202026-02-23%2010-37-23.png)

![](img/Screenshot%20from%202026-02-23%2010-37-42.png)
