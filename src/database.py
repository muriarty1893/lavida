"""Centralized database operations for Lavida."""

import os
import sqlite3
import logging

from PyQt6.QtCore import QObject, pyqtSignal

logger = logging.getLogger(__name__)


class Database(QObject):
    data_changed = pyqtSignal()

    def __init__(self, db_path=None):
        super().__init__()
        if db_path is None:
            db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lavida.db")
        self.db_path = os.path.abspath(db_path)
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()
        self._init_tables()

        self.thumbnails_dir = os.path.join(os.path.dirname(self.db_path), "thumbnails")
        os.makedirs(self.thumbnails_dir, exist_ok=True)

    def _init_tables(self):
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS videos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT,
                title TEXT,
                watched INTEGER DEFAULT 0,
                tab_index INTEGER DEFAULT 0,
                row_order INTEGER DEFAULT 0,
                is_deleted INTEGER DEFAULT 0
            )
        """)

        migrations = [
            "ALTER TABLE videos ADD COLUMN tab_index INTEGER DEFAULT 0",
            "ALTER TABLE videos ADD COLUMN row_order INTEGER DEFAULT 0",
            "ALTER TABLE videos ADD COLUMN is_deleted INTEGER DEFAULT 0",
            "ALTER TABLE videos ADD COLUMN thumbnail_path TEXT DEFAULT ''",
            "ALTER TABLE videos ADD COLUMN tab_id INTEGER",
            "ALTER TABLE videos ADD COLUMN duration TEXT DEFAULT ''",
            "ALTER TABLE videos ADD COLUMN channel TEXT DEFAULT ''",
            "ALTER TABLE videos ADD COLUMN deleted_at TEXT DEFAULT ''",
        ]
        for sql in migrations:
            try:
                self.cursor.execute(sql)
            except sqlite3.OperationalError:
                pass  # Column already exists

        self.cursor.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")

        # Create tabs table and migrate existing data if needed
        self.cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='tabs'")
        if not self.cursor.fetchone():
            self.cursor.execute("""
                CREATE TABLE tabs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    is_history INTEGER NOT NULL DEFAULT 0
                )
            """)
            # Seed work tabs from existing settings (or defaults)
            for i in range(3):
                self.cursor.execute("SELECT value FROM settings WHERE key=?", (f'tab_name_{i}',))
                row = self.cursor.fetchone()
                name = row[0] if row else f"Tab {i + 1}"
                self.cursor.execute(
                    "INSERT INTO tabs (name, sort_order, is_history) VALUES (?, ?, 0)",
                    (name, i)
                )
            # History tab
            self.cursor.execute(
                "INSERT INTO tabs (name, sort_order, is_history) VALUES ('History', 999999, 1)"
            )
            # Map old tab_index → new tab_id for all videos
            self.cursor.execute(
                "SELECT id, sort_order FROM tabs WHERE is_history=0 ORDER BY sort_order"
            )
            tab_mapping = {row[1]: row[0] for row in self.cursor.fetchall()}
            self.cursor.execute("SELECT id FROM tabs WHERE is_history=1")
            history_id = self.cursor.fetchone()[0]
            first_tab_id = tab_mapping.get(0) or next(iter(tab_mapping.values()))
            for old_index, new_id in tab_mapping.items():
                self.cursor.execute(
                    "UPDATE videos SET tab_id=? WHERE tab_index=? AND is_deleted=0",
                    (new_id, old_index)
                )
            # Any remaining unmapped active videos go to the first tab
            self.cursor.execute(
                "UPDATE videos SET tab_id=? WHERE tab_id IS NULL AND is_deleted=0",
                (first_tab_id,)
            )
            # Deleted videos get the history tab_id
            self.cursor.execute(
                "UPDATE videos SET tab_id=? WHERE is_deleted=1",
                (history_id,)
            )

        self.conn.commit()

    # -- Settings --

    def save_setting(self, key, value):
        self.cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
        self.conn.commit()

    def load_setting(self, key, default=None):
        try:
            self.cursor.execute("SELECT value FROM settings WHERE key=?", (key,))
            row = self.cursor.fetchone()
            return row[0] if row else default
        except Exception:
            logger.warning("Failed to load setting '%s'", key, exc_info=True)
            return default

    def save_window_settings(self, x, y, width, height):
        for k, v in [('pos_x', x), ('pos_y', y), ('width', width), ('height', height)]:
            self.cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (k, str(v)))
        self.conn.commit()

    def load_window_settings(self):
        """Returns (x, y, width, height) or None if not saved."""
        try:
            vals = {}
            for key in ('pos_x', 'pos_y', 'width', 'height'):
                self.cursor.execute("SELECT value FROM settings WHERE key=?", (key,))
                row = self.cursor.fetchone()
                if row is None:
                    return None
                vals[key] = int(row[0])
            return vals['pos_x'], vals['pos_y'], vals['width'], vals['height']
        except Exception:
            logger.warning("Failed to load window settings", exc_info=True)
            return None

    # -- Tabs --

    def get_work_tabs(self):
        """Return all non-history tabs ordered by sort_order: [(id, name, sort_order), ...]"""
        self.cursor.execute(
            "SELECT id, name, sort_order FROM tabs WHERE is_history=0 ORDER BY sort_order ASC"
        )
        return self.cursor.fetchall()

    def get_history_tab_id(self):
        self.cursor.execute("SELECT id FROM tabs WHERE is_history=1")
        row = self.cursor.fetchone()
        return row[0] if row else None

    def update_tab_sort_orders(self, tab_ids):
        """Persist new tab display order."""
        for i, tab_id in enumerate(tab_ids):
            self.cursor.execute("UPDATE tabs SET sort_order=? WHERE id=?", (i, tab_id))
        self.conn.commit()

    def create_tab(self, name, sort_order):
        self.cursor.execute(
            "INSERT INTO tabs (name, sort_order, is_history) VALUES (?, ?, 0)",
            (name, sort_order)
        )
        self.conn.commit()
        return self.cursor.lastrowid

    def delete_tab(self, tab_id):
        """Soft-delete all videos in the tab, then remove the tab row."""
        self.cursor.execute(
            "UPDATE videos SET is_deleted=1, deleted_at=datetime('now') WHERE tab_id=? AND is_deleted=0", (tab_id,)
        )
        self.cursor.execute("DELETE FROM tabs WHERE id=?", (tab_id,))
        self.conn.commit()
        self.data_changed.emit()

    def rename_tab(self, tab_id, new_name):
        self.cursor.execute("UPDATE tabs SET name=? WHERE id=?", (new_name, tab_id))
        self.conn.commit()

    def get_work_tab_count(self):
        self.cursor.execute("SELECT COUNT(*) FROM tabs WHERE is_history=0")
        return self.cursor.fetchone()[0]

    def get_next_sort_order(self):
        self.cursor.execute("SELECT MAX(sort_order) FROM tabs WHERE is_history=0")
        val = self.cursor.fetchone()[0]
        return (val + 1) if val is not None else 0

    def reassign_video_tab(self, vid_id, tab_id):
        self.cursor.execute("UPDATE videos SET tab_id=? WHERE id=?", (tab_id, vid_id))
        self.conn.commit()

    # -- Videos --

    def add_video(self, url, title, tab_id, row_order):
        self.cursor.execute(
            "INSERT INTO videos (url, title, tab_id, row_order, is_deleted) VALUES (?, ?, ?, ?, 0)",
            (url, title, tab_id, row_order)
        )
        self.conn.commit()
        self.data_changed.emit()
        return self.cursor.lastrowid

    def update_video_title(self, vid_id, title, thumbnail_path="", duration="", channel=""):
        self.cursor.execute(
            "UPDATE videos SET title=?, thumbnail_path=?, duration=?, channel=? WHERE id=?",
            (title, thumbnail_path, duration, channel, vid_id)
        )
        self.conn.commit()
        self.data_changed.emit()

    def update_video_order(self, vid_id, order):
        self.cursor.execute("UPDATE videos SET row_order = ? WHERE id = ?", (order, vid_id))
        self.conn.commit()
        self.data_changed.emit()

    def mark_watched(self, vid_id):
        self.cursor.execute("UPDATE videos SET watched = 1 WHERE id = ?", (vid_id,))
        self.conn.commit()
        self.data_changed.emit()

    def mark_unwatched(self, vid_id):
        self.cursor.execute("UPDATE videos SET watched = 0 WHERE id = ?", (vid_id,))
        self.conn.commit()
        self.data_changed.emit()

    def soft_delete_video(self, vid_id):
        self.cursor.execute(
            "UPDATE videos SET is_deleted=1, deleted_at=datetime('now') WHERE id = ?",
            (vid_id,)
        )
        self.conn.commit()
        self.data_changed.emit()

    def hard_delete_video(self, vid_id):
        self.cursor.execute("DELETE FROM videos WHERE id = ?", (vid_id,))
        self.conn.commit()
        self.data_changed.emit()

    def restore_video(self, vid_id):
        self.cursor.execute(
            "UPDATE videos SET is_deleted=0, deleted_at='' WHERE id = ?", (vid_id,)
        )
        self.conn.commit()
        self.data_changed.emit()

    def get_video_tab(self, vid_id):
        self.cursor.execute("SELECT tab_id FROM videos WHERE id = ?", (vid_id,))
        row = self.cursor.fetchone()
        return row[0] if row else None

    def get_active_videos(self):
        self.cursor.execute(
            "SELECT id, title, url, watched, tab_id, thumbnail_path, duration, channel "
            "FROM videos WHERE is_deleted=0 ORDER BY row_order ASC, id DESC"
        )
        return self.cursor.fetchall()

    def get_deleted_videos(self):
        self.cursor.execute(
            "SELECT id, title, url, watched, thumbnail_path, duration, channel "
            "FROM videos WHERE is_deleted=1 ORDER BY deleted_at DESC, id DESC"
        )
        return self.cursor.fetchall()

    def find_video_by_url(self, url):
        self.cursor.execute(
            "SELECT id FROM videos WHERE url = ? AND is_deleted = 0", (url,)
        )
        row = self.cursor.fetchone()
        return row[0] if row else None

    def find_video_by_video_id(self, video_id):
        self.cursor.execute(
            "SELECT id FROM videos WHERE url LIKE ? AND is_deleted = 0",
            (f"%{video_id}%",)
        )
        row = self.cursor.fetchone()
        return row[0] if row else None

    def get_video_by_url(self, url):
        """Return (id, watched) for an active video by URL, or None."""
        self.cursor.execute(
            "SELECT id, watched FROM videos WHERE url = ? AND is_deleted = 0", (url,)
        )
        return self.cursor.fetchone()

    def mark_watched_silent(self, vid_id):
        """Mark watched without emitting data_changed (used by Obsidian import)."""
        self.cursor.execute("UPDATE videos SET watched = 1 WHERE id = ?", (vid_id,))
        self.conn.commit()

    def mark_unwatched_silent(self, vid_id):
        """Mark unwatched without emitting data_changed (used by Obsidian import)."""
        self.cursor.execute("UPDATE videos SET watched = 0 WHERE id = ?", (vid_id,))
        self.conn.commit()

    def bulk_soft_delete(self, vid_ids):
        if not vid_ids:
            return
        placeholders = ','.join('?' * len(vid_ids))
        self.cursor.execute(f"UPDATE videos SET is_deleted=1, deleted_at=datetime('now') WHERE id IN ({placeholders})", vid_ids)
        self.conn.commit()
        self.data_changed.emit()

    def bulk_mark_watched(self, vid_ids):
        if not vid_ids:
            return
        placeholders = ','.join('?' * len(vid_ids))
        self.cursor.execute(f"UPDATE videos SET watched=1 WHERE id IN ({placeholders})", vid_ids)
        self.conn.commit()
        self.data_changed.emit()

    def bulk_move_to_tab(self, vid_ids, tab_id):
        if not vid_ids:
            return
        placeholders = ','.join('?' * len(vid_ids))
        self.cursor.execute(
            f"UPDATE videos SET tab_id=? WHERE id IN ({placeholders})", [tab_id] + vid_ids
        )
        self.conn.commit()
        self.data_changed.emit()

    def get_min_row_order(self):
        self.cursor.execute("SELECT MIN(row_order) FROM videos")
        val = self.cursor.fetchone()[0]
        return val if val is not None else 0

    def close(self):
        try:
            self.conn.close()
        except Exception:
            logger.warning("Failed to close database connection", exc_info=True)
