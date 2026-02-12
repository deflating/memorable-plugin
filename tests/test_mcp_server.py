import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_DIR = REPO_ROOT / "plugin"
if str(PLUGIN_DIR) not in sys.path:
    sys.path.insert(0, str(PLUGIN_DIR))

import mcp_server  # noqa: E402


class McpServerTests(unittest.TestCase):
    def setUp(self):
        self.orig_files_dir = mcp_server.FILES_DIR

    def tearDown(self):
        mcp_server.FILES_DIR = self.orig_files_dir

    def test_get_document_level_returns_selected_level_content(self):
        with tempfile.TemporaryDirectory() as td:
            files_dir = Path(td)
            mcp_server.FILES_DIR = files_dir
            (files_dir / "doc.md").write_text("# Title\n\nFull", encoding="utf-8")
            (files_dir / "doc.md.levels.json").write_text(
                json.dumps(
                    {
                        "levels": 3,
                        "content": {"1": "short", "2": "medium", "3": "# Title\n\nFull"},
                    }
                ),
                encoding="utf-8",
            )

            server = mcp_server.MemorableMCP()
            raw = server._tool_get_document_level({"filename": "doc.md", "level": 1})
            payload = json.loads(raw)
            self.assertEqual("doc.md", payload["filename"])
            self.assertEqual(1, payload["resolved_level"])
            self.assertEqual("levels", payload["source"])
            self.assertEqual("short", payload["content"])

    def test_get_document_level_falls_back_to_raw_when_level_missing(self):
        with tempfile.TemporaryDirectory() as td:
            files_dir = Path(td)
            mcp_server.FILES_DIR = files_dir
            full = "# Title\n\nFull document"
            (files_dir / "doc.md").write_text(full, encoding="utf-8")
            (files_dir / "doc.md.levels.json").write_text(
                json.dumps({"levels": 1, "content": {"1": "short"}}),
                encoding="utf-8",
            )

            server = mcp_server.MemorableMCP()
            raw = server._tool_get_document_level({"filename": "doc.md", "level": 4})
            payload = json.loads(raw)
            self.assertEqual(-1, payload["resolved_level"])
            self.assertEqual("raw", payload["source"])
            self.assertEqual(full, payload["content"])

    def test_list_documents_includes_levels_state(self):
        with tempfile.TemporaryDirectory() as td:
            files_dir = Path(td)
            mcp_server.FILES_DIR = files_dir
            (files_dir / "a.md").write_text("a", encoding="utf-8")
            (files_dir / "b.md").write_text("b", encoding="utf-8")
            (files_dir / "a.md.levels.json").write_text(
                json.dumps({"levels": 2, "content": {"1": "a", "2": "a"}}),
                encoding="utf-8",
            )

            server = mcp_server.MemorableMCP()
            out = server._tool_list_documents({})
            self.assertIn("a.md (levels: 2)", out)
            self.assertIn("b.md (raw only)", out)


if __name__ == "__main__":
    unittest.main()
