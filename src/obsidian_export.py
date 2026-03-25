"""Obsidian vault two-way sync for Lavida (watched state)."""

import os
import re
import logging

from PyQt6.QtCore import QObject, QTimer, pyqtSignal
from PyQt6.QtCore import QFileSystemWatcher

logger = logging.getLogger(__name__)

_ITEM_RE = re.compile(r'^- \[([ x])\] \[(.+?)\]\((.+?)\)$')


class ObsidianExporter(QObject):
    import_complete = pyqtSignal()

    def __init__(self, db):
        super().__init__()
        self._db = db
        self._vault_path = ""
        self._lavida_dir = ""
        self._tab_names = []
        self._writing = False

        # Write debounce timer (2s)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(2000)
        self._timer.timeout.connect(self._write_vault)

        # Read debounce timer (1s) — fires after Obsidian edits settle
        self._read_timer = QTimer(self)
        self._read_timer.setSingleShot(True)
        self._read_timer.setInterval(1000)
        self._read_timer.timeout.connect(self._read_vault)

        self._watcher = QFileSystemWatcher(self)
        self._watcher.directoryChanged.connect(self._on_files_changed)

    def configure(self, vault_path, tab_names):
        self._vault_path = vault_path
        self._tab_names = tab_names
        if not vault_path:
            self._lavida_dir = ""
            self._clear_watcher()
            return
        self._lavida_dir = os.path.join(vault_path, "Lavida")
        os.makedirs(self._lavida_dir, exist_ok=True)
        self._setup_watcher()
        self._write_vault()

    def _setup_watcher(self):
        self._clear_watcher()
        if self._lavida_dir and os.path.isdir(self._lavida_dir):
            self._watcher.addPath(self._lavida_dir)

    def _clear_watcher(self):
        watched = self._watcher.directories()
        if watched:
            self._watcher.removePaths(watched)

    def _on_files_changed(self, _path=None):
        if self._writing:
            return
        self._read_timer.start()

    def _read_vault(self):
        if not self._lavida_dir or not os.path.isdir(self._lavida_dir):
            return
        changed = False
        try:
            for fname in os.listdir(self._lavida_dir):
                if not fname.endswith(".md"):
                    continue
                fpath = os.path.join(self._lavida_dir, fname)
                try:
                    with open(fpath, encoding="utf-8") as f:
                        for line in f:
                            m = _ITEM_RE.match(line.rstrip())
                            if not m:
                                continue
                            watched_char, _title, url = m.group(1), m.group(2), m.group(3)
                            obsidian_watched = watched_char == "x"
                            row = self._db.get_video_by_url(url)
                            if row is None:
                                continue
                            vid_id, db_watched = row
                            if bool(db_watched) != obsidian_watched:
                                if obsidian_watched:
                                    self._db.mark_watched_silent(vid_id)
                                else:
                                    self._db.mark_unwatched_silent(vid_id)
                                changed = True
                except Exception:
                    logger.warning("Failed to read Obsidian file %s", fpath, exc_info=True)
        except Exception:
            logger.warning("Failed to scan Obsidian vault dir", exc_info=True)

        if changed:
            self.import_complete.emit()

    def _schedule_write(self):
        if not self._vault_path:
            return
        self._timer.start()

    def _write_vault(self):
        if not self._vault_path or not self._lavida_dir:
            return
        self._writing = True
        try:
            active = self._db.get_active_videos()
            deleted = self._db.get_deleted_videos()
            work_tabs = self._db.get_work_tabs()  # [(id, name, sort_order), ...]

            tabs = {tab_id: [] for tab_id, _, _ in work_tabs}
            first_tab_id = work_tabs[0][0] if work_tabs else None

            for _vid_id, title, url, watched, tab_id, _thumb, _dur, _chan in active:
                if tab_id in tabs:
                    tabs[tab_id].append((title, url, watched))
                elif first_tab_id:
                    tabs[first_tab_id].append((title, url, watched))

            for tab_id, name, _ in work_tabs:
                content = self._format_tab(name, tabs.get(tab_id, []))
                self._atomic_write(os.path.join(self._lavida_dir, f"{name}.md"), content)

            history_videos = [(title, url, watched) for _id, title, url, watched, _thumb, _dur, _chan in deleted]
            self._atomic_write(
                os.path.join(self._lavida_dir, "History.md"),
                self._format_tab("History", history_videos),
            )
        except Exception:
            logger.warning("Obsidian export failed", exc_info=True)
        finally:
            QTimer.singleShot(500, self._reset_writing)

    def _reset_writing(self):
        self._writing = False

    def _format_tab(self, tab_name, videos):
        lines = [f"# {tab_name}", ""]
        for title, url, watched in videos:
            check = "x" if watched else " "
            lines.append(f"- [{check}] [{title}]({url})")
        return "\n".join(lines) + "\n"

    def _atomic_write(self, path, content):
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp, path)

    def update_tab_names(self, tab_names, removed_names=None):
        if self._vault_path and self._lavida_dir:
            # Remove files for deleted tabs
            if removed_names:
                for name in removed_names:
                    path = os.path.join(self._lavida_dir, f"{name}.md")
                    try:
                        if os.path.exists(path):
                            os.remove(path)
                    except Exception:
                        logger.warning("Failed to remove tab file %s", path, exc_info=True)
            # Rename changed tabs (compare old names minus removed with new names)
            old_names = [n for n in self._tab_names if not removed_names or n not in removed_names]
            for old, new in zip(old_names, tab_names):
                if old != new:
                    old_path = os.path.join(self._lavida_dir, f"{old}.md")
                    new_path = os.path.join(self._lavida_dir, f"{new}.md")
                    try:
                        if os.path.exists(old_path):
                            os.rename(old_path, new_path)
                    except Exception:
                        logger.warning("Failed to rename tab file %s → %s", old, new, exc_info=True)
        self._tab_names = tab_names
        self._write_vault()

    def shutdown(self):
        self._timer.stop()
        self._read_timer.stop()
        self._clear_watcher()
        self._write_vault()
