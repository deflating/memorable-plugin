import io
import json
import os
import sys
import tempfile
import unittest
import zipfile
from datetime import datetime, timedelta, timezone
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
        self.orig_reliability_metrics_path = server_api.RELIABILITY_METRICS_PATH
        self.orig_load_config = server_api.load_config
        self.orig_save_config = server_api.save_config

    def tearDown(self):
        server_api.DATA_DIR = self.orig_data_dir
        server_api.NOTES_DIR = self.orig_notes_dir
        server_api.FILES_DIR = self.orig_files_dir
        server_api.SESSIONS_DIR = self.orig_sessions_dir
        server_api.SEEDS_DIR = self.orig_seeds_dir
        server_api.NOTE_USAGE_PATH = self.orig_note_usage_path
        server_api.RELIABILITY_METRICS_PATH = self.orig_reliability_metrics_path
        server_api.load_config = self.orig_load_config
        server_api.save_config = self.orig_save_config

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

    def test_handle_post_settings_rejects_unknown_key(self):
        status, data = server_api.handle_post_settings({"mystery": 1})
        self.assertEqual(400, status)
        self.assertEqual("INVALID_SETTINGS_KEY", data["error"]["code"])

    def test_handle_post_settings_rejects_invalid_types(self):
        status, data = server_api.handle_post_settings({"token_budget": "200000"})
        self.assertEqual(400, status)
        self.assertEqual("INVALID_TOKEN_BUDGET", data["error"]["code"])

        status, data = server_api.handle_post_settings({"daemon": {"enabled": "true"}})
        self.assertEqual(400, status)
        self.assertEqual("INVALID_DAEMON_ENABLED", data["error"]["code"])

        status, data = server_api.handle_post_settings({"llm_provider": {"model": 123}})
        self.assertEqual(400, status)
        self.assertEqual("INVALID_LLM_PROVIDER_MODEL", data["error"]["code"])

        status, data = server_api.handle_post_settings({"llm_routing": {"now_md": 123}})
        self.assertEqual(400, status)
        self.assertEqual("INVALID_LLM_ROUTING_NOW_MD", data["error"]["code"])

        status, data = server_api.handle_post_settings({"claude_cli": {"command": 123}})
        self.assertEqual(400, status)
        self.assertEqual("INVALID_CLAUDE_CLI_COMMAND", data["error"]["code"])

    def test_handle_post_settings_rejects_invalid_ranges(self):
        status, data = server_api.handle_post_settings({"server_port": 70000})
        self.assertEqual(400, status)
        self.assertEqual("INVALID_SERVER_PORT", data["error"]["code"])

        status, data = server_api.handle_post_settings({"daemon": {"idle_threshold": 0}})
        self.assertEqual(400, status)
        self.assertEqual("INVALID_DAEMON_IDLE_THRESHOLD", data["error"]["code"])

        status, data = server_api.handle_post_settings({"llm_routing": {"now_md": "banana"}})
        self.assertEqual(400, status)
        self.assertEqual("INVALID_LLM_ROUTING_VALUE", data["error"]["code"])

    def test_handle_post_settings_applies_valid_patch(self):
        captured = {}
        existing = {
            "llm_provider": {"endpoint": "https://api.deepseek.com/v1", "api_key": "", "model": "deepseek-chat"},
            "llm_routing": {"session_notes": "deepseek", "now_md": "deepseek", "anchors": "deepseek"},
            "claude_cli": {"command": "claude", "prompt_flag": "-p"},
            "token_budget": 200000,
            "daemon": {"enabled": False, "idle_threshold": 300},
            "server_port": 7777,
            "context_files": [],
        }
        server_api.load_config = lambda: dict(existing)
        server_api.save_config = lambda config: captured.setdefault("config", config)

        status, data = server_api.handle_post_settings(
            {
                "token_budget": 123456,
                "daemon": {"enabled": True, "idle_threshold": 120},
                "llm_provider": {"model": "deepseek-reasoner"},
                "llm_routing": {"now_md": "claude"},
                "claude_cli": {"command": "claude", "prompt_flag": "-p"},
            }
        )
        self.assertEqual(200, status)
        self.assertTrue(data["ok"])
        self.assertIn("config", captured)
        self.assertEqual(123456, captured["config"]["token_budget"])
        self.assertTrue(captured["config"]["daemon"]["enabled"])
        self.assertEqual(120, captured["config"]["daemon"]["idle_threshold"])
        self.assertEqual("deepseek-reasoner", captured["config"]["llm_provider"]["model"])
        self.assertEqual("claude_cli", captured["config"]["llm_routing"]["now_md"])
        self.assertEqual("claude", captured["config"]["claude_cli"]["command"])

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

    def test_handle_get_metrics_summarizes_local_counters(self):
        now = datetime.now(timezone.utc)
        today_iso = now.isoformat().replace("+00:00", "Z")
        yesterday_iso = (now - timedelta(days=1)).isoformat().replace("+00:00", "Z")
        old_incident = (now - timedelta(days=9)).isoformat().replace("+00:00", "Z")
        recent_incident = (now - timedelta(hours=2)).isoformat().replace("+00:00", "Z")

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            notes_dir = root / "notes"
            notes_dir.mkdir(parents=True, exist_ok=True)
            notes_file = notes_dir / "session_notes.jsonl"
            rows = [
                {"ts": today_iso, "note": "today", "topic_tags": []},
                {"ts": yesterday_iso, "note": "yesterday", "topic_tags": []},
                {
                    "ts": today_iso,
                    "note": "weekly synthesis",
                    "topic_tags": [],
                    "synthesis_level": "weekly",
                },
            ]
            with notes_file.open("w", encoding="utf-8") as fh:
                for row in rows:
                    fh.write(json.dumps(row) + "\n")

            metrics_path = root / "reliability_metrics.json"
            metrics_path.write_text(
                json.dumps(
                    {
                        "import": {"success": 3, "failure": 1},
                        "export": {"success": 2, "failure": 4},
                        "lag_incidents": [
                            {"ts": old_incident, "source_ts": "old", "lag_seconds": 7200},
                            {"ts": recent_incident, "source_ts": "recent", "lag_seconds": 1800},
                        ],
                    }
                ),
                encoding="utf-8",
            )

            server_api.NOTES_DIR = notes_dir
            server_api.RELIABILITY_METRICS_PATH = metrics_path
            status, data = server_api.handle_get_metrics()
            self.assertEqual(200, status)
            self.assertEqual(1, data["notes_generated_today"])
            self.assertEqual(7, len(data["notes_generated_last_7_days"]))
            self.assertEqual(2, data["lag_incidents_total"])
            self.assertEqual(1, data["lag_incidents_7d"])
            self.assertEqual(3, data["import"]["success"])
            self.assertEqual(1, data["import"]["failure"])
            self.assertEqual(2, data["export"]["success"])
            self.assertEqual(4, data["export"]["failure"])

    def test_handle_get_export_updates_reliability_counters(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            data_dir = root / "data"
            data_dir.mkdir(parents=True, exist_ok=True)
            (data_dir / "note_usage.json").write_text("{}", encoding="utf-8")

            server_api.DATA_DIR = data_dir
            server_api.RELIABILITY_METRICS_PATH = data_dir / "reliability_metrics.json"

            status, data = server_api.handle_get_export()
            self.assertEqual(200, status)
            self.assertIn("payload", data)

            metrics = json.loads(server_api.RELIABILITY_METRICS_PATH.read_text(encoding="utf-8"))
            self.assertEqual(1, metrics["export"]["success"])
            self.assertEqual(0, metrics["export"]["failure"])

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
            for d in (files_dir, notes_dir, sessions_dir, seeds_dir):
                d.mkdir(parents=True, exist_ok=True)

            # Create a session file so activity is detected
            (sessions_dir / "s1.json").write_text('{"date":"2026-01-01"}', encoding="utf-8")

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

    def test_handle_get_status_detects_lagging_notes_when_sessions_are_newer(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            files_dir = root / "files"
            notes_dir = root / "notes"
            sessions_dir = root / "sessions"
            seeds_dir = root / "seeds"
            for d in (files_dir, notes_dir, sessions_dir, seeds_dir):
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
            (sessions_dir / "latest.json").write_text('{"date":"2026-02-12"}', encoding="utf-8")
            (root / "daemon.pid").write_text(str(os.getpid()), encoding="utf-8")

            server_api.DATA_DIR = root
            server_api.FILES_DIR = files_dir
            server_api.NOTES_DIR = notes_dir
            server_api.SESSIONS_DIR = sessions_dir
            server_api.SEEDS_DIR = seeds_dir
            server_api.RELIABILITY_METRICS_PATH = root / "reliability_metrics.json"
            server_api.load_config = lambda: {
                "daemon": {"enabled": True, "idle_threshold": 60}
            }

            status, data = server_api.handle_get_status()
            self.assertEqual(200, status)
            self.assertTrue(data["daemon_running"])
            self.assertIn("notes_lagging", data["daemon_health"]["issues"])
            self.assertIsNotNone(data["daemon_lag_seconds"])
            self.assertGreater(data["daemon_lag_seconds"], data["daemon_health"]["lag_threshold_seconds"])

            status, data = server_api.handle_get_status()
            self.assertEqual(200, status)

            metrics_status, metrics_data = server_api.handle_get_metrics()
            self.assertEqual(200, metrics_status)
            self.assertEqual(1, metrics_data["lag_incidents_total"])

    def test_handle_put_file_depth_rejects_invalid_depth_and_enabled(self):
        status, data = server_api.handle_put_file_depth("doc.md", {"depth": "banana", "enabled": True})
        self.assertEqual(400, status)
        self.assertEqual("INVALID_DEPTH", data["error"]["code"])

        status, data = server_api.handle_put_file_depth("doc.md", {"depth": 9, "enabled": True})
        self.assertEqual(400, status)
        self.assertEqual("INVALID_DEPTH", data["error"]["code"])

        status, data = server_api.handle_put_file_depth("doc.md", {"depth": 2, "enabled": "true"})
        self.assertEqual(400, status)
        self.assertEqual("INVALID_ENABLED", data["error"]["code"])

    def test_handle_put_file_depth_normalizes_broken_context_files_config(self):
        captured = {}
        server_api.load_config = lambda: {"context_files": {"bad": "shape"}}
        server_api.save_config = lambda config: captured.setdefault("config", config)

        status, data = server_api.handle_put_file_depth("doc.md", {"depth": 2, "enabled": True})
        self.assertEqual(200, status)
        self.assertTrue(data["ok"])
        self.assertIn("config", captured)
        self.assertEqual(
            [{"filename": "doc.md", "depth": 2, "enabled": True}],
            captured["config"]["context_files"],
        )


if __name__ == "__main__":
    unittest.main()
