import io
import json
import os
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace

REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_DIR = REPO_ROOT / "plugin"
if str(PLUGIN_DIR) not in sys.path:
    sys.path.insert(0, str(PLUGIN_DIR))

import server_api  # noqa: E402


class ServerApiTests(unittest.TestCase):
    def setUp(self):
        self.orig_data_dir = server_api.DATA_DIR
        self.orig_notes_dir = server_api.NOTES_DIR
        self.orig_files_dir = server_api.FILES_DIR
        self.orig_sessions_dir = server_api.SESSIONS_DIR
        self.orig_seeds_dir = server_api.SEEDS_DIR
        self.orig_note_usage_path = server_api.NOTE_USAGE_PATH
        self.orig_load_config = server_api.load_config

    def tearDown(self):
        server_api.DATA_DIR = self.orig_data_dir
        server_api.NOTES_DIR = self.orig_notes_dir
        server_api.FILES_DIR = self.orig_files_dir
        server_api.SESSIONS_DIR = self.orig_sessions_dir
        server_api.SEEDS_DIR = self.orig_seeds_dir
        server_api.NOTE_USAGE_PATH = self.orig_note_usage_path
        server_api.load_config = self.orig_load_config

    def test_load_all_notes_survives_non_string_note_rows(self):
        with tempfile.TemporaryDirectory() as td:
            notes_dir = Path(td)
            notes_file = notes_dir / "notes.jsonl"
            rows = [
                {"ts": "2026-01-01T00:00:00Z", "note": "ok1", "topic_tags": []},
                {"ts": "2026-01-02T00:00:00Z", "note": 123, "topic_tags": []},
                {"ts": "2026-01-03T00:00:00Z", "note": "ok2", "topic_tags": []},
            ]
            with notes_file.open("w", encoding="utf-8") as fh:
                for row in rows:
                    fh.write(json.dumps(row) + "\n")

            server_api.NOTES_DIR = notes_dir
            notes = server_api.load_all_notes()

            self.assertEqual(3, len(notes))
            self.assertEqual(["ok1", "123", "ok2"], [n["summary"] for n in notes])

    def test_handle_get_files_hides_internal_cache_files(self):
        with tempfile.TemporaryDirectory() as td:
            files_dir = Path(td)
            (files_dir / ".cache-test-depth1.md").write_text("cache", encoding="utf-8")
            (files_dir / "doc.md").write_text("hello", encoding="utf-8")
            (files_dir / "doc.md.anchored").write_text("\u26930\ufe0f\u20e3 a\nb \u2693", encoding="utf-8")

            server_api.FILES_DIR = files_dir
            server_api.load_config = lambda: {
                "context_files": [{"filename": "doc.md", "enabled": True, "depth": 2}]
            }

            status, data = server_api.handle_get_files()
            self.assertEqual(200, status)
            self.assertEqual(["doc.md"], [f["name"] for f in data["files"]])
            self.assertTrue(data["files"][0]["anchored"])

    def test_handle_post_file_upload_rejects_invalid_content_length(self):
        handler = SimpleNamespace(
            headers={"Content-Type": "application/json", "Content-Length": "abc"},
            rfile=io.BytesIO(b"{}"),
        )

        status, data = server_api.handle_post_file_upload(handler)
        self.assertEqual(400, status)
        self.assertEqual("INVALID_CONTENT_LENGTH", data["error"]["code"])

    def test_handle_post_file_upload_rejects_non_object_json_payload(self):
        body = b"[1,2,3]"
        handler = SimpleNamespace(
            headers={
                "Content-Type": "application/json",
                "Content-Length": str(len(body)),
            },
            rfile=io.BytesIO(body),
        )

        status, data = server_api.handle_post_file_upload(handler)
        self.assertEqual(400, status)
        self.assertEqual("INVALID_JSON_OBJECT", data["error"]["code"])

    def test_handle_post_file_upload_rejects_negative_content_length(self):
        handler = SimpleNamespace(
            headers={"Content-Type": "application/json", "Content-Length": "-1"},
            rfile=io.BytesIO(b"{}"),
        )

        status, data = server_api.handle_post_file_upload(handler)
        self.assertEqual(400, status)
        self.assertEqual("INVALID_CONTENT_LENGTH", data["error"]["code"])

    def test_handle_post_file_upload_rejects_non_string_json_content(self):
        body = b'{"filename":"x.md","content":123}'
        handler = SimpleNamespace(
            headers={
                "Content-Type": "application/json",
                "Content-Length": str(len(body)),
            },
            rfile=io.BytesIO(body),
        )

        status, data = server_api.handle_post_file_upload(handler)
        self.assertEqual(400, status)
        self.assertEqual("INVALID_UPLOAD_FIELDS_TYPE", data["error"]["code"])

    def test_handle_post_seeds_rejects_non_string_content(self):
        status, data = server_api.handle_post_seeds({"files": {"user.md": 123}})
        self.assertEqual(400, status)
        self.assertEqual("INVALID_FILE_CONTENT", data["error"]["code"])

    def test_handle_post_deploy_rejects_non_string_content(self):
        status, data = server_api.handle_post_deploy({"files": {"user.md": 123}})
        self.assertEqual(400, status)
        self.assertEqual("INVALID_FILE_CONTENT", data["error"]["code"])

    def test_handle_post_process_rejects_non_string_content(self):
        status, data = server_api.handle_post_process({"filename": "doc.md", "content": 123})
        self.assertEqual(400, status)
        self.assertEqual("INVALID_CONTENT_TYPE", data["error"]["code"])

    def test_import_zip_rejects_unsafe_member_paths(self):
        payload = io.BytesIO()
        with zipfile.ZipFile(payload, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("../evil.txt", "x")

        with self.assertRaises(ValueError):
            server_api.import_zip_payload(payload.getvalue())

    def test_handle_get_memory_insights_summarizes_usage(self):
        with tempfile.TemporaryDirectory() as td:
            usage_path = Path(td) / "note_usage.json"
            usage_path.write_text(
                json.dumps(
                    {
                        "notes": {
                            "a1": {
                                "session_short": "sess-a1",
                                "loaded_count": 6,
                                "referenced_count": 1,
                            },
                            "b2": {
                                "session_short": "sess-b2",
                                "loaded_count": 4,
                                "referenced_count": 3,
                            },
                            "c3": {
                                "session_short": "sess-c3",
                                "loaded_count": 3,
                                "referenced_count": 0,
                            },
                        }
                    }
                ),
                encoding="utf-8",
            )
            server_api.NOTE_USAGE_PATH = usage_path

            status, data = server_api.handle_get_memory_insights()
            self.assertEqual(200, status)
            self.assertEqual(3, data["tracked_notes"])
            self.assertEqual(13, data["total_loaded"])
            self.assertEqual(4, data["total_referenced"])
            self.assertEqual(1, data["never_referenced_count"])
            self.assertEqual(2, data["low_effectiveness_count"])
            self.assertEqual("sess-b2", data["top_referenced"][0]["session"])
            self.assertEqual("sess-a1", data["high_load_low_reference"][0]["session"])

    def test_handle_get_notes_filters_by_session_prefix(self):
        with tempfile.TemporaryDirectory() as td:
            notes_dir = Path(td)
            notes_file = notes_dir / "notes.jsonl"
            rows = [
                {
                    "ts": "2026-01-01T00:00:00Z",
                    "session": "abcdef123456",
                    "note": "alpha",
                    "topic_tags": ["one"],
                },
                {
                    "ts": "2026-01-02T00:00:00Z",
                    "session": "zzz999",
                    "note": "beta",
                    "topic_tags": ["two"],
                },
            ]
            with notes_file.open("w", encoding="utf-8") as fh:
                for row in rows:
                    fh.write(json.dumps(row) + "\n")

            server_api.NOTES_DIR = notes_dir
            status, data = server_api.handle_get_notes({"session": ["AbCdEf12"]})
            self.assertEqual(200, status)
            self.assertEqual(1, data["total"])
            self.assertEqual("abcdef123456", data["notes"][0]["session"])

    def test_handle_get_notes_negative_offset_is_clamped(self):
        with tempfile.TemporaryDirectory() as td:
            notes_dir = Path(td)
            notes_file = notes_dir / "notes.jsonl"
            rows = [
                {"ts": "2026-01-01T00:00:00Z", "session": "a", "note": "alpha", "topic_tags": []},
                {"ts": "2026-01-02T00:00:00Z", "session": "b", "note": "beta", "topic_tags": []},
            ]
            with notes_file.open("w", encoding="utf-8") as fh:
                for row in rows:
                    fh.write(json.dumps(row) + "\n")

            server_api.NOTES_DIR = notes_dir
            status, data = server_api.handle_get_notes({"offset": ["-9"]})
            self.assertEqual(200, status)
            self.assertEqual(2, data["total"])
            self.assertEqual(2, len(data["notes"]))

    def test_handle_get_notes_excludes_archived_by_default(self):
        with tempfile.TemporaryDirectory() as td:
            notes_dir = Path(td)
            notes_file = notes_dir / "notes.jsonl"
            rows = [
                {"ts": "2026-01-01T00:00:00Z", "session": "a", "note": "active note", "topic_tags": []},
                {"ts": "2026-01-02T00:00:00Z", "session": "b", "note": "archived note", "topic_tags": [], "archived": True},
            ]
            with notes_file.open("w", encoding="utf-8") as fh:
                for row in rows:
                    fh.write(json.dumps(row) + "\n")

            server_api.NOTES_DIR = notes_dir

            status, data = server_api.handle_get_notes({})
            self.assertEqual(200, status)
            self.assertEqual(1, data["total"])
            self.assertEqual("active note", data["notes"][0]["summary"])

            status, data = server_api.handle_get_notes({"archived": ["include"]})
            self.assertEqual(200, status)
            self.assertEqual(2, data["total"])

            status, data = server_api.handle_get_notes({"archived": ["only"]})
            self.assertEqual(200, status)
            self.assertEqual(1, data["total"])
            self.assertTrue(data["notes"][0]["archived"])

    def test_handle_post_note_review_updates_persistence_and_filters(self):
        with tempfile.TemporaryDirectory() as td:
            notes_dir = Path(td)
            notes_file = notes_dir / "notes.jsonl"
            rows = [
                {
                    "ts": "2026-01-01T00:00:00Z",
                    "session": "abcdef123456",
                    "note": "alpha",
                    "topic_tags": ["one"],
                    "salience": 1.0,
                }
            ]
            with notes_file.open("w", encoding="utf-8") as fh:
                for row in rows:
                    fh.write(json.dumps(row) + "\n")

            server_api.NOTES_DIR = notes_dir
            status, data = server_api.handle_get_notes({"archived": ["include"]})
            self.assertEqual(200, status)
            note = data["notes"][0]
            note_id = note["id"]

            status, data = server_api.handle_post_note_review({"note_id": note_id, "action": "pin"})
            self.assertEqual(200, status)
            self.assertTrue(data["note"]["pinned"])

            status, _ = server_api.handle_post_note_review({"note_id": note_id, "action": "promote"})
            self.assertEqual(200, status)

            status, data = server_api.handle_post_note_review(
                {"note_id": note_id, "action": "retag", "tags": ["work", "release"]}
            )
            self.assertEqual(200, status)
            self.assertEqual(["work", "release"], data["note"]["tags"])

            status, _ = server_api.handle_post_note_review({"note_id": note_id, "action": "archive"})
            self.assertEqual(200, status)

            status, data = server_api.handle_get_notes({})
            self.assertEqual(200, status)
            self.assertEqual(0, data["total"])

            status, data = server_api.handle_get_notes({"archived": ["only"]})
            self.assertEqual(200, status)
            self.assertEqual(1, data["total"])
            self.assertTrue(data["notes"][0]["archived"])
            self.assertTrue(data["notes"][0]["pinned"])
            self.assertEqual(["work", "release"], data["notes"][0]["tags"])
            self.assertAlmostEqual(1.25, data["notes"][0]["salience"])

    def test_handle_post_note_review_rejects_invalid_tags_payload(self):
        with tempfile.TemporaryDirectory() as td:
            notes_dir = Path(td)
            notes_file = notes_dir / "notes.jsonl"
            notes_file.write_text(
                json.dumps(
                    {
                        "ts": "2026-01-01T00:00:00Z",
                        "session": "abcdef123456",
                        "note": "alpha",
                        "topic_tags": ["one"],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            server_api.NOTES_DIR = notes_dir
            status, data = server_api.handle_get_notes({"archived": ["include"]})
            self.assertEqual(200, status)
            note_id = data["notes"][0]["id"]

            status, data = server_api.handle_post_note_review(
                {"note_id": note_id, "action": "retag", "tags": "not-a-list"}
            )
            self.assertEqual(400, status)
            self.assertEqual("INVALID_TAGS", data["error"]["code"])

    def test_handle_get_status_file_count_ignores_internal_artifacts(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            files_dir = root / "files"
            notes_dir = root / "notes"
            sessions_dir = root / "sessions"
            seeds_dir = root / "seeds"
            for d in (files_dir, notes_dir, sessions_dir, seeds_dir):
                d.mkdir(parents=True, exist_ok=True)

            (files_dir / "doc.md").write_text("hello", encoding="utf-8")
            (files_dir / "doc.md.anchored").write_text("anchored", encoding="utf-8")
            (files_dir / ".cache-doc-depth1.md").write_text("cache", encoding="utf-8")

            server_api.FILES_DIR = files_dir
            server_api.NOTES_DIR = notes_dir
            server_api.SESSIONS_DIR = sessions_dir
            server_api.SEEDS_DIR = seeds_dir

            status, data = server_api.handle_get_status()
            self.assertEqual(200, status)
            self.assertEqual(1, data["file_count"])

    def test_handle_get_status_reports_daemon_not_running_when_enabled(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            files_dir = root / "files"
            notes_dir = root / "notes"
            sessions_dir = root / "sessions"
            seeds_dir = root / "seeds"
            transcripts_dir = root / "transcripts"
            for d in (files_dir, notes_dir, sessions_dir, seeds_dir, transcripts_dir):
                d.mkdir(parents=True, exist_ok=True)

            (transcripts_dir / "s1.txt").write_text("transcript", encoding="utf-8")

            server_api.DATA_DIR = root
            server_api.FILES_DIR = files_dir
            server_api.NOTES_DIR = notes_dir
            server_api.SESSIONS_DIR = sessions_dir
            server_api.SEEDS_DIR = seeds_dir
            server_api.load_config = lambda: {
                "daemon": {"enabled": True, "idle_threshold": 300}
            }

            status, data = server_api.handle_get_status()
            self.assertEqual(200, status)
            self.assertTrue(data["daemon_enabled"])
            self.assertFalse(data["daemon_running"])
            self.assertEqual("attention", data["daemon_health"]["state"])
            self.assertIn("daemon_not_running", data["daemon_health"]["issues"])

    def test_handle_get_status_detects_lagging_notes_when_transcripts_are_newer(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            files_dir = root / "files"
            notes_dir = root / "notes"
            sessions_dir = root / "sessions"
            seeds_dir = root / "seeds"
            transcripts_dir = root / "transcripts"
            for d in (files_dir, notes_dir, sessions_dir, seeds_dir, transcripts_dir):
                d.mkdir(parents=True, exist_ok=True)

            (notes_dir / "session_notes.jsonl").write_text(
                json.dumps(
                    {
                        "ts": "2026-01-01T00:00:00Z",
                        "note": "old note",
                        "topic_tags": [],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            (transcripts_dir / "latest.txt").write_text("new transcript", encoding="utf-8")
            (root / "daemon.pid").write_text(str(os.getpid()), encoding="utf-8")

            server_api.DATA_DIR = root
            server_api.FILES_DIR = files_dir
            server_api.NOTES_DIR = notes_dir
            server_api.SESSIONS_DIR = sessions_dir
            server_api.SEEDS_DIR = seeds_dir
            server_api.load_config = lambda: {
                "daemon": {"enabled": True, "idle_threshold": 60}
            }

            status, data = server_api.handle_get_status()
            self.assertEqual(200, status)
            self.assertTrue(data["daemon_running"])
            self.assertIn("notes_lagging", data["daemon_health"]["issues"])
            self.assertIsNotNone(data["daemon_lag_seconds"])
            self.assertGreater(data["daemon_lag_seconds"], data["daemon_health"]["lag_threshold_seconds"])


if __name__ == "__main__":
    unittest.main()
