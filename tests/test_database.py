"""Tests for new Database methods: get_video_by_url and silent watched updates."""

import pytest
from src.database import Database


@pytest.fixture
def db(qapp, tmp_path):
    database = Database(str(tmp_path / "test.db"))
    yield database
    database.close()


class TestGetVideoByUrl:
    def test_returns_id_and_watched_for_active_video(self, db):
        vid_id = db.add_video("https://youtube.com/watch?v=abc", "Test", 0, 0)
        row = db.get_video_by_url("https://youtube.com/watch?v=abc")
        assert row is not None
        assert row[0] == vid_id
        assert row[1] == 0  # unwatched by default

    def test_returns_correct_watched_state_after_mark(self, db):
        vid_id = db.add_video("https://youtube.com/watch?v=xyz", "Test", 0, 0)
        db.mark_watched(vid_id)
        row = db.get_video_by_url("https://youtube.com/watch?v=xyz")
        assert row[1] == 1

    def test_returns_none_for_missing_url(self, db):
        assert db.get_video_by_url("https://youtube.com/watch?v=notexist") is None

    def test_returns_none_for_deleted_video(self, db):
        vid_id = db.add_video("https://youtube.com/watch?v=del", "Deleted", 0, 0)
        db.soft_delete_video(vid_id)
        assert db.get_video_by_url("https://youtube.com/watch?v=del") is None


class TestMarkWatchedSilent:
    def test_updates_watched_state_in_db(self, db):
        vid_id = db.add_video("https://youtube.com/watch?v=s1", "Test", 0, 0)
        db.mark_watched_silent(vid_id)
        row = db.get_video_by_url("https://youtube.com/watch?v=s1")
        assert row[1] == 1

    def test_does_not_emit_data_changed(self, db):
        vid_id = db.add_video("https://youtube.com/watch?v=s2", "Test", 0, 0)
        emissions = []
        db.data_changed.connect(lambda: emissions.append(1))
        db.mark_watched_silent(vid_id)
        assert emissions == []

    def test_idempotent_on_already_watched(self, db):
        vid_id = db.add_video("https://youtube.com/watch?v=s3", "Test", 0, 0)
        db.mark_watched(vid_id)
        db.mark_watched_silent(vid_id)
        row = db.get_video_by_url("https://youtube.com/watch?v=s3")
        assert row[1] == 1


class TestMarkUnwatchedSilent:
    def test_updates_unwatched_state_in_db(self, db):
        vid_id = db.add_video("https://youtube.com/watch?v=u1", "Test", 0, 0)
        db.mark_watched(vid_id)
        db.mark_unwatched_silent(vid_id)
        row = db.get_video_by_url("https://youtube.com/watch?v=u1")
        assert row[1] == 0

    def test_does_not_emit_data_changed(self, db):
        vid_id = db.add_video("https://youtube.com/watch?v=u2", "Test", 0, 0)
        db.mark_watched(vid_id)
        emissions = []
        db.data_changed.connect(lambda: emissions.append(1))
        db.mark_unwatched_silent(vid_id)
        assert emissions == []

    def test_idempotent_on_already_unwatched(self, db):
        vid_id = db.add_video("https://youtube.com/watch?v=u3", "Test", 0, 0)
        db.mark_unwatched_silent(vid_id)
        row = db.get_video_by_url("https://youtube.com/watch?v=u3")
        assert row[1] == 0
