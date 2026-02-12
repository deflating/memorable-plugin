import http.client
import io
import json
import sys
import tempfile
import threading
import unittest
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_DIR = REPO_ROOT / "plugin"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(PLUGIN_DIR) not in sys.path:
    sys.path.insert(0, str(PLUGIN_DIR))

from processor import anchor  # noqa: E402
import server_api  # noqa: E402
import server_http  # noqa: E402
import server_storage  # noqa: E402


class EndToEndSmokeTests(unittest.TestCase):
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
        self._orig_values = {
            "server_storage.DATA_DIR": server_storage.DATA_DIR,
            "server_storage.SEEDS_DIR": server_storage.SEEDS_DIR,
            "server_storage.NOTES_DIR": server_storage.NOTES_DIR,
            "server_storage.SESSIONS_DIR": server_storage.SESSIONS_DIR,
            "server_storage.FILES_DIR": server_storage.FILES_DIR,
            "server_storage.CONFIG_PATH": server_storage.CONFIG_PATH,
            "server_storage.AUDIT_LOG_PATH": server_storage.AUDIT_LOG_PATH,
            "server_api.DATA_DIR": server_api.DATA_DIR,
            "server_api.SEEDS_DIR": server_api.SEEDS_DIR,
            "server_api.NOTES_DIR": server_api.NOTES_DIR,
            "server_api.SESSIONS_DIR": server_api.SESSIONS_DIR,
            "server_api.FILES_DIR": server_api.FILES_DIR,
            "server_api.CONFIG_PATH": server_api.CONFIG_PATH,
            "server_http.DATA_DIR": server_http.DATA_DIR,
            "server_http.FILES_DIR": server_http.FILES_DIR,
            "anchor.DATA_DIR": anchor.DATA_DIR,
            "anchor.FILES_DIR": anchor.FILES_DIR,
            "anchor.LLM_CONFIG_PATH": anchor.LLM_CONFIG_PATH,
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
        server_http.DATA_DIR = self.data_dir
        server_http.FILES_DIR = self.files_dir
        anchor.DATA_DIR = self.data_dir
        anchor.FILES_DIR = self.files_dir
        anchor.LLM_CONFIG_PATH = self.config_path

        server_storage.ensure_dirs()

        self.server = server_http.ThreadingHTTPServer(
            ("127.0.0.1", 0),
            server_http.MemorableHandler,
        )
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.port = self.server.server_address[1]

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

        server_storage.DATA_DIR = self._orig_values["server_storage.DATA_DIR"]
        server_storage.SEEDS_DIR = self._orig_values["server_storage.SEEDS_DIR"]
        server_storage.NOTES_DIR = self._orig_values["server_storage.NOTES_DIR"]
        server_storage.SESSIONS_DIR = self._orig_values["server_storage.SESSIONS_DIR"]
        server_storage.FILES_DIR = self._orig_values["server_storage.FILES_DIR"]
        server_storage.CONFIG_PATH = self._orig_values["server_storage.CONFIG_PATH"]
        server_storage.AUDIT_LOG_PATH = self._orig_values["server_storage.AUDIT_LOG_PATH"]

        server_api.DATA_DIR = self._orig_values["server_api.DATA_DIR"]
        server_api.SEEDS_DIR = self._orig_values["server_api.SEEDS_DIR"]
        server_api.NOTES_DIR = self._orig_values["server_api.NOTES_DIR"]
        server_api.SESSIONS_DIR = self._orig_values["server_api.SESSIONS_DIR"]
        server_api.FILES_DIR = self._orig_values["server_api.FILES_DIR"]
        server_api.CONFIG_PATH = self._orig_values["server_api.CONFIG_PATH"]
        server_http.DATA_DIR = self._orig_values["server_http.DATA_DIR"]
        server_http.FILES_DIR = self._orig_values["server_http.FILES_DIR"]
        anchor.DATA_DIR = self._orig_values["anchor.DATA_DIR"]
        anchor.FILES_DIR = self._orig_values["anchor.FILES_DIR"]
        anchor.LLM_CONFIG_PATH = self._orig_values["anchor.LLM_CONFIG_PATH"]

        self.temp.cleanup()

    def _request_json(self, method: str, path: str, body=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=3)
        payload = None
        headers = {}
        if body is not None:
            payload = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        conn.request(method, path, body=payload, headers=headers)
        resp = conn.getresponse()
        raw = resp.read()
        status = resp.status
        conn.close()
        return status, json.loads(raw.decode("utf-8"))

    def _request_bytes(self, method: str, path: str):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn.request(method, path)
        resp = conn.getresponse()
        status = resp.status
        content_type = resp.getheader("Content-Type", "")
        payload = resp.read()
        conn.close()
        return status, content_type, payload

    def test_core_api_smoke_flow(self):
        status, health = self._request_json("GET", "/api/health")
        self.assertEqual(200, status)
        self.assertIn("ok", health)

        status, base_status = self._request_json("GET", "/api/status")
        self.assertEqual(200, status)
        self.assertFalse(base_status["seeds_present"])
        self.assertEqual(0, base_status["file_count"])

        status, seeds_write = self._request_json(
            "POST",
            "/api/seeds",
            {"files": {"user.md": "# User\nAlice", "agent.md": "# Agent\nHelper"}},
        )
        self.assertEqual(200, status)
        self.assertTrue(seeds_write["ok"])

        status, seeds_read = self._request_json("GET", "/api/seeds")
        self.assertEqual(200, status)
        self.assertIn("user.md", seeds_read["files"])
        self.assertIn("agent.md", seeds_read["files"])

        status, settings_write = self._request_json(
            "POST",
            "/api/settings",
            {
                "token_budget": 12345,
                "daemon": {"enabled": True, "idle_threshold": 120},
            },
        )
        self.assertEqual(200, status)
        self.assertTrue(settings_write["ok"])

        status, settings_read = self._request_json("GET", "/api/settings")
        self.assertEqual(200, status)
        self.assertEqual(12345, settings_read["settings"]["token_budget"])
        self.assertTrue(settings_read["settings"]["daemon"]["enabled"])

        status, upload = self._request_json(
            "POST",
            "/api/files/upload",
            {"filename": "doc.md", "content": "# Title\n\nBody"},
        )
        self.assertEqual(200, status)
        self.assertTrue(upload["ok"])

        status, files = self._request_json("GET", "/api/files")
        self.assertEqual(200, status)
        self.assertEqual(["doc.md"], [f["name"] for f in files["files"]])

        status, levels = self._request_json("GET", "/api/files/doc.md/levels")
        self.assertEqual(200, status)
        self.assertEqual("doc.md", levels["filename"])
        self.assertIn("levels", levels)
        self.assertTrue(levels["recoverability"]["full_recoverable"])

        status, process_payload = self._request_json("POST", "/api/files/doc.md/process")
        self.assertEqual(200, status)
        self.assertEqual("ok", process_payload["status"])

        status, provenance = self._request_json("GET", "/api/files/doc.md/provenance")
        self.assertEqual(200, status)
        self.assertIn("segments", provenance)
        self.assertGreater(len(provenance["segments"]), 0)
        first_segment_id = provenance["segments"][0]["id"]

        status, resolved = self._request_json(
            "GET",
            f"/api/files/doc.md/provenance?segment_id={first_segment_id}&context_lines=1",
        )
        self.assertEqual(200, status)
        self.assertEqual(first_segment_id, resolved["segment"]["id"])
        self.assertIn("text", resolved["excerpt"])

        status, cleanup_upload = self._request_json(
            "POST",
            "/api/files/upload",
            {"filename": "cleanup.md", "content": "temp"},
        )
        self.assertEqual(200, status)
        self.assertTrue(cleanup_upload["ok"])
        (self.files_dir / "cleanup.md.anchored").write_text(
            "\u26930\ufe0f\u20e3 temp\nt \u2693",
            encoding="utf-8",
        )
        (self.files_dir / "cleanup.md.anchored.meta.json").write_text(
            "{}",
            encoding="utf-8",
        )
        status, delete_payload = self._request_json("DELETE", "/api/files/cleanup.md")
        self.assertEqual(200, status)
        self.assertTrue(delete_payload["ok"])
        self.assertTrue(delete_payload["anchored_deleted"])
        self.assertTrue(delete_payload["manifest_deleted"])

        status, depth_update = self._request_json(
            "PUT",
            "/api/files/doc.md/depth",
            {"depth": 2, "enabled": True},
        )
        self.assertEqual(200, status)
        self.assertTrue(depth_update["ok"])

        status, notes = self._request_json("GET", "/api/notes?limit=5")
        self.assertEqual(200, status)
        self.assertEqual([], notes["notes"])

        status, tags = self._request_json("GET", "/api/notes/tags")
        self.assertEqual(200, status)
        self.assertEqual([], tags["tags"])

        status, machines = self._request_json("GET", "/api/machines")
        self.assertEqual(200, status)
        self.assertEqual([], machines["machines"])

        status, budget = self._request_json("GET", "/api/budget")
        self.assertEqual(200, status)
        self.assertTrue(any(item["file"] == "doc.md" for item in budget["breakdown"]))

        status, after_status = self._request_json("GET", "/api/status")
        self.assertEqual(200, status)
        self.assertTrue(after_status["seeds_present"])
        self.assertEqual(1, after_status["file_count"])

        status, content_type, payload = self._request_bytes("GET", "/api/export")
        self.assertEqual(200, status)
        self.assertIn("application/zip", content_type)
        self.assertGreater(len(payload), 0)

        with zipfile.ZipFile(io.BytesIO(payload)) as zf:
            names = set(zf.namelist())
        self.assertIn("config.json", names)
        self.assertIn("files/doc.md", names)
        self.assertIn("seeds/user.md", names)
        self.assertIn("seeds/agent.md", names)


if __name__ == "__main__":
    unittest.main()
