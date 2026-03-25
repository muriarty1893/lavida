import re
import json
import time
import logging
import threading
import requests
from pynput import mouse, keyboard
from PyQt6.QtCore import QThread, pyqtSignal

logger = logging.getLogger(__name__)

DEFAULT_ACTIVATION_KEY = 'scroll_right'

# Map stored key strings to human-readable labels
_LABELS = {
    'scroll_right': 'Scroll right',
    'scroll_left': 'Scroll left',
    'scroll_up': 'Scroll up',
    'scroll_down': 'Scroll down',
    'mouse_middle': 'Mouse middle',
    'mouse_back': 'Mouse back',
    'mouse_forward': 'Mouse forward',
}


def activation_key_label(key):
    if key in _LABELS:
        return _LABELS[key]
    if key and key.startswith('key_'):
        name = key[4:]
        # Clean up pynput key names like "Key.f1" -> "F1"
        if name.startswith('Key.'):
            return name[4:].upper()
        return name.upper() if len(name) == 1 else name.capitalize()
    return key or DEFAULT_ACTIVATION_KEY


def detect_input(timeout=10):
    """Block and wait for the user to press any mouse button, scroll, or keyboard key.
    Returns a key string like 'scroll_left', 'mouse_back', 'key_a', 'key_Key.f1', etc.
    Returns None on timeout."""
    result = []
    done = threading.Event()

    def on_scroll(x, y, dx, dy):
        if dx > 0:
            result.append('scroll_right')
        elif dx < 0:
            result.append('scroll_left')
        elif dy > 0:
            result.append('scroll_up')
        elif dy < 0:
            result.append('scroll_down')
        if result:
            done.set()
            return False

    def on_click(x, y, button, pressed):
        if not pressed:
            return
        name = button.name if hasattr(button, 'name') else ''
        val = button.value if hasattr(button, 'value') else -1
        # Ignore left/right click — they're too essential to bind
        if name in ('left', 'right') or val in (1, 3):
            return
        if name == 'middle' or val == 2:
            result.append('mouse_middle')
        elif name in ('x1', 'button8') or val == 8:
            result.append('mouse_back')
        elif name in ('x2', 'button9') or val == 9:
            result.append('mouse_forward')
        else:
            result.append(f'mouse_{name or val}')
        done.set()
        return False

    def on_press(key):
        try:
            result.append(f'key_{key.char}')
        except AttributeError:
            result.append(f'key_{key}')
        done.set()
        return False

    ml = mouse.Listener(on_scroll=on_scroll, on_click=on_click)
    kl = keyboard.Listener(on_press=on_press)
    ml.start()
    kl.start()

    done.wait(timeout=timeout)

    ml.stop()
    kl.stop()

    return result[0] if result else None


class GlobalInputListener(QThread):
    toggle_signal = pyqtSignal()
    detected_signal = pyqtSignal(str)

    def __init__(self, activation_key=DEFAULT_ACTIVATION_KEY):
        super().__init__()
        self.activation_key = activation_key
        self.last_action_time = 0
        self.detecting = False

    def _try_toggle(self):
        current_time = time.time()
        if current_time - self.last_action_time > 0.4:
            self.toggle_signal.emit()
            self.last_action_time = current_time

    def _resolve_click(self, button):
        name = button.name if hasattr(button, 'name') else ''
        val = button.value if hasattr(button, 'value') else -1
        if name in ('left', 'right') or val in (1, 3):
            return None
        if name == 'middle' or val == 2:
            return 'mouse_middle'
        if name in ('x1', 'button8') or val == 8:
            return 'mouse_back'
        if name in ('x2', 'button9') or val == 9:
            return 'mouse_forward'
        return f'mouse_{name or val}'

    def _resolve_scroll(self, dx, dy):
        if dx > 0:
            return 'scroll_right'
        if dx < 0:
            return 'scroll_left'
        if dy > 0:
            return 'scroll_up'
        if dy < 0:
            return 'scroll_down'
        return None

    def _resolve_key(self, key_event):
        try:
            return f'key_{key_event.char}'
        except AttributeError:
            return f'key_{key_event}'

    def run(self):
        ml = mouse.Listener(on_scroll=self.on_scroll, on_click=self.on_click)
        kl = keyboard.Listener(on_press=self.on_press)
        ml.start()
        kl.start()
        ml.join()

    def on_scroll(self, x, y, dx, dy):
        resolved = self._resolve_scroll(dx, dy)
        if not resolved:
            return
        if self.detecting:
            self.detecting = False
            self.detected_signal.emit(resolved)
        elif resolved == self.activation_key:
            self._try_toggle()

    def on_click(self, x, y, button, pressed):
        if not pressed:
            return
        resolved = self._resolve_click(button)
        if not resolved:
            return
        if self.detecting:
            self.detecting = False
            self.detected_signal.emit(resolved)
        elif resolved == self.activation_key:
            self._try_toggle()

    def on_press(self, key_event):
        resolved = self._resolve_key(key_event)
        if self.detecting:
            self.detecting = False
            self.detected_signal.emit(resolved)
        elif resolved == self.activation_key:
            self._try_toggle()


class PlaylistFetchWorker(QThread):
    """Fetches video URLs and titles from a YouTube playlist page."""
    video_found = pyqtSignal(str, str)       # url, title
    progress = pyqtSignal(int, int)          # current, total
    finished_signal = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, playlist_url):
        super().__init__()
        self.playlist_url = playlist_url

    def run(self):
        try:
            headers = {'User-Agent': 'Mozilla/5.0'}
            resp = requests.get(self.playlist_url, headers=headers, timeout=10)
            if resp.status_code != 200:
                self.error.emit(f"HTTP {resp.status_code}")
                return

            # Extract ytInitialData JSON from page
            match = re.search(r'var ytInitialData\s*=\s*(\{.+?\});\s*</script>', resp.text)
            if not match:
                self.error.emit("Could not parse playlist data")
                return

            data = json.loads(match.group(1))

            # Navigate to playlist video list
            videos = []
            try:
                tabs = data['contents']['twoColumnBrowseResultsRenderer']['tabs']
                for tab in tabs:
                    section = tab.get('tabRenderer', {}).get('content', {})
                    section_list = section.get('sectionListRenderer', {}).get('contents', [])
                    for s in section_list:
                        items = (s.get('itemSectionRenderer', {})
                                  .get('contents', [{}])[0]
                                  .get('playlistVideoListRenderer', {})
                                  .get('contents', []))
                        for item in items:
                            renderer = item.get('playlistVideoRenderer')
                            if not renderer:
                                continue
                            video_id = renderer.get('videoId', '')
                            title_runs = renderer.get('title', {}).get('runs', [])
                            title = title_runs[0]['text'] if title_runs else video_id
                            if video_id:
                                videos.append((
                                    f"https://www.youtube.com/watch?v={video_id}",
                                    title
                                ))
            except (KeyError, IndexError, TypeError):
                self.error.emit("Could not extract videos from playlist")
                return

            if not videos:
                self.error.emit("No videos found in playlist")
                return

            total = len(videos)
            for i, (url, title) in enumerate(videos):
                self.video_found.emit(url, title)
                self.progress.emit(i + 1, total)

        except requests.RequestException as e:
            self.error.emit(str(e))
        except (json.JSONDecodeError, ValueError) as e:
            self.error.emit(f"Parse error: {e}")
        finally:
            self.finished_signal.emit()
