"""Tests for ObsidianExporter two-way sync (watched state)."""

import os
import pytest
from src.database import Database
from src.obsidian_export import ObsidianExporter


@pytest.fixture
def db(qapp, tmp_path):
    database = Database(str(tmp_path / "test.db"))
    yield database
    database.close()


@pytest.fixture
def exporter(qapp, db):
    exp = ObsidianExporter(db)
    yield exp
    exp.shutdown()


@pytest.fixture
def lavida_dir(tmp_path):
    d = tmp_path / "vault" / "Lavida"
    d.mkdir(parents=True)
    return d


class TestFormatTab:
    def test_watched_video_uses_x_checkbox(self, exporter):
        content = exporter._format_tab("Tab1", [("My Video", "http://url", 1)])
        assert "- [x] [My Video](http://url)" in content

    def test_unwatched_video_uses_space_checkbox(self, exporter):
        content = exporter._format_tab("Tab1", [("My Video", "http://url", 0)])
        assert "- [ ] [My Video](http://url)" in content

    def test_includes_h1_header(self, exporter):
        content = exporter._format_tab("MyTab", [])
        assert content.startswith("# MyTab\n")

    def test_empty_tab_has_only_header(self, exporter):
        content = exporter._format_tab("Empty", [])
        assert content == "# Empty\n\n"

    def test_multiple_videos_all_present(self, exporter):
        videos = [("A", "http://a", 0), ("B", "http://b", 1)]
        content = exporter._format_tab("Tab", videos)
        assert "- [ ] [A](http://a)" in content
        assert "- [x] [B](http://b)" in content


class TestReadVault:
    def test_marks_video_watched_from_markdown(self, exporter, db, lavida_dir):
        vid_id = db.add_video("https://youtube.com/watch?v=abc", "Test", 0, 0)
        (lavida_dir / "Tab1.md").write_text(
            "# Tab1\n\n- [x] [Test](https://youtube.com/watch?v=abc)\n"
        )
        exporter._lavida_dir = str(lavida_dir)

        exporter._read_vault()

        assert db.get_video_by_url("https://youtube.com/watch?v=abc")[1] == 1

    def test_marks_video_unwatched_from_markdown(self, exporter, db, lavida_dir):
        vid_id = db.add_video("https://youtube.com/watch?v=xyz", "Test", 0, 0)
        db.mark_watched(vid_id)
        (lavida_dir / "Tab1.md").write_text(
            "# Tab1\n\n- [ ] [Test](https://youtube.com/watch?v=xyz)\n"
        )
        exporter._lavida_dir = str(lavida_dir)

        exporter._read_vault()

        assert db.get_video_by_url("https://youtube.com/watch?v=xyz")[1] == 0

    def test_emits_import_complete_when_state_changed(self, exporter, db, lavida_dir):
        db.add_video("https://youtube.com/watch?v=abc", "Test", 0, 0)
        (lavida_dir / "Tab1.md").write_text(
            "# Tab1\n\n- [x] [Test](https://youtube.com/watch?v=abc)\n"
        )
        exporter._lavida_dir = str(lavida_dir)
        emitted = []
        exporter.import_complete.connect(lambda: emitted.append(1))

        exporter._read_vault()

        assert emitted == [1]

    def test_does_not_emit_import_complete_when_no_changes(self, exporter, db, lavida_dir):
        vid_id = db.add_video("https://youtube.com/watch?v=abc", "Test", 0, 0)
        db.mark_watched(vid_id)
        # Markdown matches DB state — already watched
        (lavida_dir / "Tab1.md").write_text(
            "# Tab1\n\n- [x] [Test](https://youtube.com/watch?v=abc)\n"
        )
        exporter._lavida_dir = str(lavida_dir)
        emitted = []
        exporter.import_complete.connect(lambda: emitted.append(1))

        exporter._read_vault()

        assert emitted == []

    def test_skips_urls_not_in_db(self, exporter, db, lavida_dir):
        (lavida_dir / "Tab1.md").write_text(
            "# Tab1\n\n- [x] [Ghost](https://youtube.com/watch?v=notindb)\n"
        )
        exporter._lavida_dir = str(lavida_dir)
        emitted = []
        exporter.import_complete.connect(lambda: emitted.append(1))

        exporter._read_vault()

        assert emitted == []  # No crash, no import_complete

    def test_processes_multiple_files(self, exporter, db, lavida_dir):
        id1 = db.add_video("https://youtube.com/watch?v=v1", "V1", 0, 0)
        id2 = db.add_video("https://youtube.com/watch?v=v2", "V2", 0, 0)
        (lavida_dir / "Tab1.md").write_text(
            "# Tab1\n\n- [x] [V1](https://youtube.com/watch?v=v1)\n"
        )
        (lavida_dir / "Tab2.md").write_text(
            "# Tab2\n\n- [x] [V2](https://youtube.com/watch?v=v2)\n"
        )
        exporter._lavida_dir = str(lavida_dir)

        exporter._read_vault()

        assert db.get_video_by_url("https://youtube.com/watch?v=v1")[1] == 1
        assert db.get_video_by_url("https://youtube.com/watch?v=v2")[1] == 1

    def test_ignores_non_md_files(self, exporter, db, lavida_dir):
        db.add_video("https://youtube.com/watch?v=abc", "Test", 0, 0)
        (lavida_dir / "notes.txt").write_text(
            "- [x] [Test](https://youtube.com/watch?v=abc)\n"
        )
        exporter._lavida_dir = str(lavida_dir)
        emitted = []
        exporter.import_complete.connect(lambda: emitted.append(1))

        exporter._read_vault()

        assert emitted == []  # .txt not processed, state unchanged


class TestLoopPrevention:
    def test_on_files_changed_ignored_when_writing(self, exporter):
        exporter._writing = True
        exporter._read_timer.stop()

        exporter._on_files_changed()

        assert not exporter._read_timer.isActive()

    def test_on_files_changed_starts_timer_when_not_writing(self, exporter):
        exporter._writing = False
        exporter._read_timer.stop()

        exporter._on_files_changed()

        assert exporter._read_timer.isActive()
        exporter._read_timer.stop()

    def test_write_vault_sets_writing_flag(self, exporter, db, tmp_path):
        lavida_dir = tmp_path / "vault" / "Lavida"
        lavida_dir.mkdir(parents=True)
        exporter._vault_path = str(tmp_path / "vault")
        exporter._lavida_dir = str(lavida_dir)
        exporter._tab_names = ["Tab1"]
        exporter._writing = False

        exporter._write_vault()

        assert exporter._writing is True
        exporter._read_timer.stop()


class TestWriteVault:
    def test_creates_tab_markdown_files(self, exporter, db, tmp_path):
        lavida_dir = tmp_path / "vault" / "Lavida"
        lavida_dir.mkdir(parents=True)
        exporter._vault_path = str(tmp_path / "vault")
        exporter._lavida_dir = str(lavida_dir)
        exporter._tab_names = ["Watch Later"]
        db.add_video("https://youtube.com/watch?v=abc", "My Video", 0, 0)

        exporter._write_vault()

        tab_file = lavida_dir / "Watch Later.md"
        assert tab_file.exists()
        content = tab_file.read_text()
        assert "My Video" in content
        assert "https://youtube.com/watch?v=abc" in content

    def test_creates_history_file(self, exporter, db, tmp_path):
        lavida_dir = tmp_path / "vault" / "Lavida"
        lavida_dir.mkdir(parents=True)
        exporter._vault_path = str(tmp_path / "vault")
        exporter._lavida_dir = str(lavida_dir)
        exporter._tab_names = ["Tab1"]
        vid_id = db.add_video("https://youtube.com/watch?v=del", "Deleted", 0, 0)
        db.soft_delete_video(vid_id)

        exporter._write_vault()

        history_file = lavida_dir / "History.md"
        assert history_file.exists()
        assert "Deleted" in history_file.read_text()

    def test_watched_video_written_as_checked(self, exporter, db, tmp_path):
        lavida_dir = tmp_path / "vault" / "Lavida"
        lavida_dir.mkdir(parents=True)
        exporter._vault_path = str(tmp_path / "vault")
        exporter._lavida_dir = str(lavida_dir)
        exporter._tab_names = ["Tab1"]
        vid_id = db.add_video("https://youtube.com/watch?v=w1", "Watched", 0, 0)
        db.mark_watched(vid_id)

        exporter._write_vault()

        content = (lavida_dir / "Tab1.md").read_text()
        assert "- [x] [Watched]" in content

    def test_skipped_when_no_vault_path(self, exporter, db, tmp_path):
        exporter._vault_path = ""
        exporter._lavida_dir = ""
        # Should not raise
        exporter._write_vault()


class TestConfigure:
    def test_sets_vault_path_and_lavida_dir(self, exporter, tmp_path):
        vault = tmp_path / "vault"
        vault.mkdir()
        exporter.configure(str(vault), ["Tab1"])
        assert exporter._vault_path == str(vault)
        assert exporter._lavida_dir == str(vault / "Lavida")

    def test_creates_lavida_dir(self, exporter, tmp_path):
        vault = tmp_path / "vault"
        vault.mkdir()
        exporter.configure(str(vault), ["Tab1"])
        assert (vault / "Lavida").is_dir()

    def test_clears_state_when_no_vault_path(self, exporter, tmp_path):
        vault = tmp_path / "vault"
        vault.mkdir()
        exporter.configure(str(vault), ["Tab1"])
        exporter.configure("", ["Tab1"])
        assert exporter._vault_path == ""
        assert exporter._lavida_dir == ""

    def test_writes_vault_on_configure(self, exporter, db, tmp_path):
        vault = tmp_path / "vault"
        vault.mkdir()
        db.add_video("https://youtube.com/watch?v=abc", "Test", 0, 0)
        exporter.configure(str(vault), ["Tab1"])
        assert (vault / "Lavida" / "Tab1.md").exists()


class TestResetWriting:
    def test_reset_writing_clears_flag(self, exporter):
        exporter._writing = True
        exporter._reset_writing()
        assert exporter._writing is False


class TestShutdown:
    def test_shutdown_stops_write_timer(self, exporter, tmp_path):
        vault = tmp_path / "vault"
        vault.mkdir()
        exporter.configure(str(vault), ["Tab1"])
        exporter._timer.start()
        exporter.shutdown()
        assert not exporter._timer.isActive()

    def test_shutdown_stops_read_timer(self, exporter):
        exporter._read_timer.start()
        exporter.shutdown()
        assert not exporter._read_timer.isActive()

    def test_shutdown_clears_watcher(self, exporter, tmp_path):
        vault = tmp_path / "vault"
        vault.mkdir()
        exporter.configure(str(vault), ["Tab1"])
        exporter.shutdown()
        assert exporter._watcher.directories() == []


class TestScheduleWrite:
    def test_starts_timer_when_vault_configured(self, exporter, tmp_path):
        vault = tmp_path / "vault"
        vault.mkdir()
        exporter._vault_path = str(vault)
        exporter._timer.stop()

        exporter._schedule_write()

        assert exporter._timer.isActive()
        exporter._timer.stop()

    def test_no_op_when_vault_not_configured(self, exporter):
        exporter._vault_path = ""
        exporter._timer.stop()

        exporter._schedule_write()

        assert not exporter._timer.isActive()


class TestReadVaultEdgeCases:
    def test_read_vault_no_op_when_lavida_dir_empty(self, exporter):
        exporter._lavida_dir = ""
        emitted = []
        exporter.import_complete.connect(lambda: emitted.append(1))
        exporter._read_vault()
        assert emitted == []

    def test_read_vault_no_op_when_dir_missing(self, exporter, tmp_path):
        exporter._lavida_dir = str(tmp_path / "nonexistent")
        emitted = []
        exporter.import_complete.connect(lambda: emitted.append(1))
        exporter._read_vault()
        assert emitted == []


class TestUpdateTabNames:
    def test_renames_tab_file(self, exporter, db, tmp_path):
        vault = tmp_path / "vault"
        vault.mkdir()
        exporter.configure(str(vault), ["OldName"])
        old_file = vault / "Lavida" / "OldName.md"
        assert old_file.exists()

        exporter.update_tab_names(["NewName"])

        assert not old_file.exists()
        assert (vault / "Lavida" / "NewName.md").exists()

    def test_updates_tab_names_list(self, exporter, db, tmp_path):
        vault = tmp_path / "vault"
        vault.mkdir()
        exporter.configure(str(vault), ["Tab1", "Tab2"])
        exporter.update_tab_names(["Alpha", "Beta"])
        assert exporter._tab_names == ["Alpha", "Beta"]
