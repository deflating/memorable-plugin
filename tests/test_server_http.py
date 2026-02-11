import http.client
import json
import sys
import threading
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_DIR = REPO_ROOT / "plugin"
if str(PLUGIN_DIR) not in sys.path:
    sys.path.insert(0, str(PLUGIN_DIR))

import server_http  # noqa: E402


class ServerHttpBodyValidationTests(unittest.TestCase):
    def setUp(self):
        self.orig_max_upload_size = server_http.MAX_UPLOAD_SIZE
        server_http.MAX_UPLOAD_SIZE = 64

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
        server_http.MAX_UPLOAD_SIZE = self.orig_max_upload_size

    def _post_settings(self, body: bytes):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=3)
        conn.request(
            "POST",
            "/api/settings",
            body=body,
            headers={"Content-Type": "application/json"},
        )
        resp = conn.getresponse()
        payload = json.loads(resp.read().decode("utf-8"))
        status = resp.status
        conn.close()
        return status, payload

    def _get_json(self, path: str):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=3)
        conn.request("GET", path)
        resp = conn.getresponse()
        payload = json.loads(resp.read().decode("utf-8"))
        status = resp.status
        conn.close()
        return status, payload

    def test_malformed_json_returns_400(self):
        status, payload = self._post_settings(b'{"token_budget":')
        self.assertEqual(400, status)
        self.assertEqual("INVALID_JSON", payload["error"]["code"])

    def test_non_object_json_returns_400(self):
        status, payload = self._post_settings(b"[1,2,3]")
        self.assertEqual(400, status)
        self.assertEqual("INVALID_JSON_OBJECT", payload["error"]["code"])

    def test_oversized_json_returns_413(self):
        status, payload = self._post_settings(b'"' + (b"A" * 80) + b'"')
        self.assertEqual(413, status)
        self.assertEqual("UPLOAD_TOO_LARGE", payload["error"]["code"])

    def test_memory_insights_route_returns_200(self):
        status, payload = self._get_json("/api/memory/insights")
        self.assertEqual(200, status)
        self.assertIn("tracked_notes", payload)


if __name__ == "__main__":
    unittest.main()
