import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from processor import anchor  # noqa: E402


class AnchorConfigSchemaTests(unittest.TestCase):
    def setUp(self):
        self.orig_llm_config_path = anchor.LLM_CONFIG_PATH
        self.orig_call_deepseek = anchor._call_deepseek
        self.orig_call_claude_cli = anchor._call_claude_cli

    def tearDown(self):
        anchor.LLM_CONFIG_PATH = self.orig_llm_config_path
        anchor._call_deepseek = self.orig_call_deepseek
        anchor._call_claude_cli = self.orig_call_claude_cli

    def test_call_llm_requires_llm_provider_key(self):
        with tempfile.TemporaryDirectory() as td:
            cfg_path = Path(td) / "config.json"
            cfg_path.write_text(
                json.dumps({"llm": {"api_key": "x", "model": "deepseek-chat"}}),
                encoding="utf-8",
            )
            anchor.LLM_CONFIG_PATH = cfg_path

            with self.assertRaises(ValueError) as ctx:
                anchor.call_llm("hello")

            self.assertIn("llm_provider", str(ctx.exception))

    def test_call_llm_uses_llm_provider_schema(self):
        with tempfile.TemporaryDirectory() as td:
            cfg_path = Path(td) / "config.json"
            cfg_path.write_text(
                json.dumps(
                    {
                        "llm_provider": {
                            "endpoint": "https://api.deepseek.com/v1",
                            "api_key": "test-key",
                            "model": "deepseek-chat",
                        }
                    }
                ),
                encoding="utf-8",
            )
            anchor.LLM_CONFIG_PATH = cfg_path

            captured = {}

            def fake_call(prompt, api_key, model, max_tokens, endpoint=None):
                captured["prompt"] = prompt
                captured["api_key"] = api_key
                captured["model"] = model
                captured["max_tokens"] = max_tokens
                captured["endpoint"] = endpoint
                return "ok"

            anchor._call_deepseek = fake_call
            result = anchor.call_llm("hello world", max_tokens=777)

            self.assertEqual("ok", result)
            self.assertEqual("test-key", captured["api_key"])
            self.assertEqual("deepseek-chat", captured["model"])
            self.assertEqual(777, captured["max_tokens"])
            self.assertEqual("https://api.deepseek.com/v1", captured["endpoint"])

    def test_call_llm_routes_anchors_to_claude_cli(self):
        with tempfile.TemporaryDirectory() as td:
            cfg_path = Path(td) / "config.json"
            cfg_path.write_text(
                json.dumps(
                    {
                        "llm_provider": {
                            "endpoint": "https://api.deepseek.com/v1",
                            "api_key": "test-key",
                            "model": "deepseek-chat",
                        },
                        "llm_routing": {
                            "anchors": "claude",
                        },
                        "claude_cli": {
                            "command": "claude",
                            "prompt_flag": "-p",
                        },
                    }
                ),
                encoding="utf-8",
            )
            anchor.LLM_CONFIG_PATH = cfg_path

            called = {}

            def fake_cli(prompt, cfg):
                called["prompt"] = prompt
                called["cfg"] = cfg
                return "ok-cli"

            anchor._call_claude_cli = fake_cli
            result = anchor.call_llm("hello world", max_tokens=777)

            self.assertEqual("ok-cli", result)
            self.assertEqual("hello world", called["prompt"])


if __name__ == "__main__":
    unittest.main()
