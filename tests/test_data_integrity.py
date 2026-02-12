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
import server_storage  # noqa: E402


class DataIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.data_dir = root / "data"
        self.seeds_dir = self.data_dir / "seeds"
        self.notes_dir = self.data_dir / "notes"
        self.sessions_dir = self.data_dir / "sessions"
        self.files_dir = self.data_dir / "files"
        self.config_path = self.data_dir / "config.json"
        self.audit_log_path = self.data_dir / "audit.log"
        self._orig = {
            "storage.data": server_storage.DATA_DIR,
            "storage.seeds": server_storage.SEEDS_DIR,
            "storage.notes": server_storage.NOTES_DIR,
            "storage.sessions": server_storage.SESSIONS_DIR,
            "storage.files": server_storage.FILES_DIR,
            "storage.config": server_storage.CONFIG_PATH,
            "storage.audit": server_storage.AUDIT_LOG_PATH,
            "api.data": server_api.DATA_DIR,
            "api.seeds": server_api.SEEDS_DIR,
            "api.notes": server_api.NOTES_DIR,
            "api.sessions": server_api.SESSIONS_DIR,
            "api.files": server_api.FILES_DIR,
            "api.config": server_api.CONFIG_PATH,
        }

        server_storage.DATA_DIR = self.data_dir
        server_storage.SEEDS_DIR = self.seeds_dir
        server_storage.NOTES_DIR = self.notes_dir
        server_storage.SESSIONS_DIR = self.sessions_dir
        server_storage.FILES_DIR = self.files_dir
        server_storage.CONFIG_PATH = self.config_path
        server_storage.AUDIT_LOG_PATH = self.audit_log_path

        server_api.DATA_DIR = self.data_dir
        server_api.SEEDS_DIR = self.seeds_dir
        server_api.NOTES_DIR = self.notes_dir
        server_api.SESSIONS_DIR = self.sessions_dir
        server_api.FILES_DIR = self.files_dir
        server_api.CONFIG_PATH = self.config_path
        server_storage.ensure_dirs()

    def tearDown(self):
        server_storage.DATA_DIR = self._orig["storage.data"]
        server_storage.SEEDS_DIR = self._orig["storage.seeds"]
        server_storage.NOTES_DIR = self._orig["storage.notes"]
        server_storage.SESSIONS_DIR = self._orig["storage.sessions"]
        server_storage.FILES_DIR = self._orig["storage.files"]
        server_storage.CONFIG_PATH = self._orig["storage.config"]
        server_storage.AUDIT_LOG_PATH = self._orig["storage.audit"]

        server_api.DATA_DIR = self._orig["api.data"]
        server_api.SEEDS_DIR = self._orig["api.seeds"]
        server_api.NOTES_DIR = self._orig["api.notes"]
        server_api.SESSIONS_DIR = self._orig["api.sessions"]
        server_api.FILES_DIR = self._orig["api.files"]
        server_api.CONFIG_PATH = self._orig["api.config"]
        self.temp.cleanup()

    def _make_import_handler(self, payload: bytes, token: str = "IMPORT"):
        return SimpleNamespace(
            headers={
                "X-Confirmation-Token": token,
                "Content-Length": str(len(payload)),
                "X-Filename": "memorable-export.zip",
            },
            rfile=io.BytesIO(payload),
        )

    def test_export_reset_import_round_trip_restores_data(self):
        (self.seeds_dir / "user.md").write_text("# User\nAlice", encoding="utf-8")
        (self.seeds_dir / "agent.md").write_text("# Agent\nHelper", encoding="utf-8")
        (self.files_dir / "doc.md").write_text("Knowledge doc body", encoding="utf-8")
        (self.notes_dir / "notes.jsonl").write_text(
            json.dumps({"ts": "2026-02-01T00:00:00Z", "note": "hello", "topic_tags": ["t"]}) + "\n",
            encoding="utf-8",
        )
        server_storage.save_config(
            {
                "token_budget": 777,
                "context_files": [{"filename": "doc.md", "depth": 2, "enabled": True}],
            }
        )

        status, export_data = server_api.handle_get_export()
        self.assertEqual(200, status)
        payload = export_data["payload"]
        self.assertGreater(len(payload), 0)

        status, reset_data = server_api.handle_post_reset({"confirmation_token": "RESET"})
        self.assertEqual(200, status)
        self.assertTrue(reset_data["ok"])
        self.assertFalse((self.seeds_dir / "user.md").exists())
        self.assertFalse((self.files_dir / "doc.md").exists())

        status, import_data = server_api.handle_post_import(self._make_import_handler(payload))
        self.assertEqual(200, status)
        self.assertTrue(import_data["ok"])
        self.assertGreater(import_data["restored_files"], 0)

        self.assertEqual("# User\nAlice", (self.seeds_dir / "user.md").read_text(encoding="utf-8"))
        self.assertEqual("Knowledge doc body", (self.files_dir / "doc.md").read_text(encoding="utf-8"))
        restored_cfg = json.loads(self.config_path.read_text(encoding="utf-8"))
        self.assertEqual(777, restored_cfg["token_budget"])

    def test_import_rolls_back_if_copytree_fails(self):
        (self.files_dir / "keep.txt").write_text("keep-me", encoding="utf-8")

        payload_buf = io.BytesIO()
        with zipfile.ZipFile(payload_buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("files/new.txt", "new-data")
        payload = payload_buf.getvalue()

        original_copytree = server_api.shutil.copytree

        def explode_copytree(*args, **kwargs):
            raise RuntimeError("copytree failed intentionally")

        server_api.shutil.copytree = explode_copytree
        try:
            with self.assertRaises(RuntimeError):
                server_api.import_zip_payload(payload)
        finally:
            server_api.shutil.copytree = original_copytree

        self.assertTrue((self.files_dir / "keep.txt").is_file())
        self.assertEqual("keep-me", (self.files_dir / "keep.txt").read_text(encoding="utf-8"))
        self.assertFalse((self.files_dir / "new.txt").exists())


if __name__ == "__main__":
    unittest.main()
