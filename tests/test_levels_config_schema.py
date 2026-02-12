import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from processor import levels  # noqa: E402


class LevelsConfigSchemaTests(unittest.TestCase):
    def setUp(self):
        self.orig_llm_config_path = levels.LLM_CONFIG_PATH
        self.orig_files_dir = levels.FILES_DIR
        self.orig_call_deepseek = levels._call_deepseek
        self.orig_call_claude = levels._call_claude
        self.orig_call_claude_cli = levels._call_claude_cli
        self.orig_process_document_llm = levels.process_document_llm

    def tearDown(self):
        levels.LLM_CONFIG_PATH = self.orig_llm_config_path
        levels.FILES_DIR = self.orig_files_dir
        levels._call_deepseek = self.orig_call_deepseek
        levels._call_claude = self.orig_call_claude
        levels._call_claude_cli = self.orig_call_claude_cli
        levels.process_document_llm = self.orig_process_document_llm

    def test_call_llm_requires_llm_provider_key(self):
        with tempfile.TemporaryDirectory() as td:
            cfg_path = Path(td) / "config.json"
            cfg_path.write_text(
                json.dumps({"llm": {"api_key": "x", "model": "deepseek-chat"}}),
                encoding="utf-8",
            )
            levels.LLM_CONFIG_PATH = cfg_path

            with self.assertRaises(ValueError) as ctx:
                levels.call_llm("hello")

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
            levels.LLM_CONFIG_PATH = cfg_path

            captured = {}

            def fake_call(prompt, api_key, model, max_tokens, endpoint=None):
                captured["prompt"] = prompt
                captured["api_key"] = api_key
                captured["model"] = model
                captured["max_tokens"] = max_tokens
                captured["endpoint"] = endpoint
                return "ok"

            levels._call_deepseek = fake_call
            output, model_name = levels.call_llm("hello world", max_tokens=777)

            self.assertEqual("ok", output)
            self.assertEqual("deepseek-chat", model_name)
            self.assertEqual("test-key", captured["api_key"])
            self.assertEqual("deepseek-chat", captured["model"])
            self.assertEqual(777, captured["max_tokens"])
            self.assertEqual("https://api.deepseek.com/v1", captured["endpoint"])

    def test_call_llm_routes_document_levels_to_claude_cli(self):
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
                            "document_levels": "claude",
                        },
                        "claude_cli": {
                            "command": "claude",
                            "prompt_flag": "-p",
                        },
                    }
                ),
                encoding="utf-8",
            )
            levels.LLM_CONFIG_PATH = cfg_path

            called = {}

            def fake_cli(prompt, cfg):
                called["prompt"] = prompt
                called["cfg"] = cfg
                return "ok-cli"

            levels._call_claude_cli = fake_cli
            output, model_name = levels.call_llm("hello world", max_tokens=777)

            self.assertEqual("ok-cli", output)
            self.assertEqual("claude_cli", model_name)
            self.assertEqual("hello world", called["prompt"])

    def test_call_llm_accepts_claude_api_provider_alias(self):
        with tempfile.TemporaryDirectory() as td:
            cfg_path = Path(td) / "config.json"
            cfg_path.write_text(
                json.dumps(
                    {
                        "llm_provider": {
                            "provider": "claude_api",
                            "api_key": "anthropic-key",
                        }
                    }
                ),
                encoding="utf-8",
            )
            levels.LLM_CONFIG_PATH = cfg_path

            called = {}

            def fake_claude(prompt, api_key, model, max_tokens):
                called["prompt"] = prompt
                called["api_key"] = api_key
                called["model"] = model
                called["max_tokens"] = max_tokens
                return "ok-claude"

            levels._call_claude = fake_claude
            levels._call_deepseek = lambda *args, **kwargs: (_ for _ in ()).throw(
                AssertionError("DeepSeek should not be called when provider alias is claude_api")
            )
            output, model_name = levels.call_llm("hello world", max_tokens=321)

            self.assertEqual("ok-claude", output)
            self.assertEqual("claude-haiku-4-5-20251001", model_name)
            self.assertEqual("hello world", called["prompt"])
            self.assertEqual("anthropic-key", called["api_key"])
            self.assertEqual("claude-haiku-4-5-20251001", called["model"])
            self.assertEqual(321, called["max_tokens"])

    def test_call_llm_accepts_claude_cli_provider_alias_without_routing(self):
        with tempfile.TemporaryDirectory() as td:
            cfg_path = Path(td) / "config.json"
            cfg_path.write_text(
                json.dumps(
                    {
                        "llm_provider": {
                            "provider": "claude_cli",
                        },
                        "claude_cli": {
                            "command": "claude",
                            "prompt_flag": "-p",
                        },
                    }
                ),
                encoding="utf-8",
            )
            levels.LLM_CONFIG_PATH = cfg_path

            called = {}

            def fake_cli(prompt, cfg):
                called["prompt"] = prompt
                called["cfg"] = cfg
                return "ok-cli"

            levels._call_claude_cli = fake_cli
            levels._call_deepseek = lambda *args, **kwargs: (_ for _ in ()).throw(
                AssertionError("DeepSeek should not be called when provider alias is claude_cli")
            )
            output, model_name = levels.call_llm("hello world", max_tokens=654)

            self.assertEqual("ok-cli", output)
            self.assertEqual("claude_cli", model_name)
            self.assertEqual("hello world", called["prompt"])

    def test_process_file_writes_levels_sidecar(self):
        with tempfile.TemporaryDirectory() as td:
            files_dir = Path(td)
            levels.FILES_DIR = files_dir
            (files_dir / "doc.md").write_text("# Title\n\nBody text.", encoding="utf-8")

            levels.process_document_llm = lambda text, filename: (
                {
                    "version": 1,
                    "filename": filename,
                    "levels": 2,
                    "generated_at": "2026-02-12T00:00:00+00:00",
                    "model": "test-levels-model",
                    "tokens": {"1": 3, "2": 5},
                    "source_tokens": levels.estimate_tokens(text),
                    "content": {"1": "Brief summary", "2": text},
                },
                "test-levels-model",
            )

            result = levels.process_file("doc.md", force=True)
            self.assertEqual("ok", result["status"])
            self.assertEqual(2, result["levels"])
            self.assertIn("levels_path", result)

            levels_path = Path(result["levels_path"])
            self.assertTrue(levels_path.is_file())

            loaded = levels.read_levels_file("doc.md")
            self.assertIsInstance(loaded, dict)
            self.assertEqual("doc.md", loaded["filename"])
            self.assertEqual(2, loaded["levels"])
            self.assertIn("1", loaded["content"])
            self.assertIn("2", loaded["content"])
            self.assertEqual("test-levels-model", loaded["model"])


if __name__ == "__main__":
    unittest.main()
