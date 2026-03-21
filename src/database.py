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
        ]
        for sql in migrations:
            try:
                self.cursor.execute(sql)
            except sqlite3.OperationalError:
                pass  # Column already exists

        self.cursor.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
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

    # -- Videos --

    def add_video(self, url, title, tab_index, row_order):
        self.cursor.execute(
            "INSERT INTO videos (url, title, tab_index, row_order, is_deleted) VALUES (?, ?, ?, ?, 0)",
            (url, title, tab_index, row_order)
        )
        self.conn.commit()
        self.data_changed.emit()
        return self.cursor.lastrowid

    def update_video_title(self, vid_id, title, thumbnail_path=""):
        self.cursor.execute("UPDATE videos SET title = ?, thumbnail_path = ? WHERE id = ?",
                            (title, thumbnail_path, vid_id))
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
        self.cursor.execute("UPDATE videos SET is_deleted=1 WHERE id = ?", (vid_id,))
        self.conn.commit()
        self.data_changed.emit()

    def hard_delete_video(self, vid_id):
        self.cursor.execute("DELETE FROM videos WHERE id = ?", (vid_id,))
        self.conn.commit()
        self.data_changed.emit()

    def restore_video(self, vid_id):
        self.cursor.execute("UPDATE videos SET is_deleted=0 WHERE id = ?", (vid_id,))
        self.conn.commit()
        self.data_changed.emit()

    def get_video_tab(self, vid_id):
        self.cursor.execute("SELECT tab_index FROM videos WHERE id = ?", (vid_id,))
        row = self.cursor.fetchone()
        return row[0] if row else 0

    def get_active_videos(self):
        self.cursor.execute(
            "SELECT id, title, url, watched, tab_index, thumbnail_path "
            "FROM videos WHERE is_deleted=0 ORDER BY row_order ASC, id DESC"
        )
        return self.cursor.fetchall()

    def get_deleted_videos(self):
        self.cursor.execute(
            "SELECT id, title, url, watched, thumbnail_path "
            "FROM videos WHERE is_deleted=1 ORDER BY id DESC"
        )
        return self.cursor.fetchall()

    def find_video_by_url(self, url):
        self.cursor.execute(
            "SELECT id FROM videos WHERE url = ? AND is_deleted = 0", (url,)
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
        self.cursor.execute(f"UPDATE videos SET is_deleted=1 WHERE id IN ({placeholders})", vid_ids)
        self.conn.commit()
        self.data_changed.emit()

    def bulk_mark_watched(self, vid_ids):
        if not vid_ids:
            return
        placeholders = ','.join('?' * len(vid_ids))
        self.cursor.execute(f"UPDATE videos SET watched=1 WHERE id IN ({placeholders})", vid_ids)
        self.conn.commit()
        self.data_changed.emit()

    def bulk_move_to_tab(self, vid_ids, tab_index):
        if not vid_ids:
            return
        placeholders = ','.join('?' * len(vid_ids))
        self.cursor.execute(f"UPDATE videos SET tab_index=? WHERE id IN ({placeholders})", [tab_index] + vid_ids)
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
