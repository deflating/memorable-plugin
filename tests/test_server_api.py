import io
import json
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
        self.orig_notes_dir = server_api.NOTES_DIR
        self.orig_files_dir = server_api.FILES_DIR
        self.orig_load_config = server_api.load_config

    def tearDown(self):
        server_api.NOTES_DIR = self.orig_notes_dir
        server_api.FILES_DIR = self.orig_files_dir
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

    def test_import_zip_rejects_unsafe_member_paths(self):
        payload = io.BytesIO()
        with zipfile.ZipFile(payload, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("../evil.txt", "x")

        with self.assertRaises(ValueError):
            server_api._import_zip_payload(payload.getvalue())


if __name__ == "__main__":
    unittest.main()
