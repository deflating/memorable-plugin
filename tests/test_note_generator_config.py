import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[1]
DAEMON_DIR = REPO_ROOT / "daemon"
if str(DAEMON_DIR) not in sys.path:
    sys.path.insert(0, str(DAEMON_DIR))

import note_generator  # noqa: E402


class NoteGeneratorConfigTests(unittest.TestCase):
    def test_get_config_reads_canonical_and_keeps_legacy_summarizer(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            canonical = root / "data-config.json"
            legacy = root / "legacy-config.json"

            canonical.write_text(
                json.dumps(
                    {
                        "llm_provider": {
                            "endpoint": "https://api.deepseek.com/v1",
                            "api_key": "",
                            "model": "deepseek-chat",
                        }
                    }
                ),
                encoding="utf-8",
            )
            legacy.write_text(
                json.dumps(
                    {
                        "summarizer": {
                            "provider": "deepseek",
                            "api_key": "legacy-key",
                            "enabled": True,
                        }
                    }
                ),
                encoding="utf-8",
            )

            with mock.patch.object(note_generator, "CONFIG_PATH", canonical), mock.patch.object(
                note_generator, "LEGACY_CONFIG_PATH", legacy
            ):
                cfg = note_generator.get_config()

            self.assertIn("llm_provider", cfg)
            self.assertIn("summarizer", cfg)
            self.assertEqual("legacy-key", cfg["summarizer"]["api_key"])

    def test_call_llm_uses_llm_provider_for_deepseek(self):
        cfg = {
            "llm_provider": {
                "endpoint": "https://api.deepseek.com/v1",
                "api_key": "deepseek-key",
                "model": "deepseek-chat",
            }
        }

        with mock.patch.object(note_generator, "call_deepseek", return_value="ok") as call_deepseek:
            result = note_generator.call_llm("hello", cfg)

        self.assertEqual("ok", result)
        call_deepseek.assert_called_once_with(
            "hello",
            "deepseek-key",
            "deepseek-chat",
            "https://api.deepseek.com/v1",
        )

    def test_call_llm_infers_provider_from_model_name(self):
        cfg = {
            "llm_provider": {
                "api_key": "anthropic-key",
                "model": "claude-3-5-sonnet-20241022",
            }
        }

        with mock.patch.object(note_generator, "call_claude", return_value="ok") as call_claude:
            result = note_generator.call_llm("hello", cfg)

        self.assertEqual("ok", result)
        call_claude.assert_called_once()

    def test_call_llm_falls_back_to_legacy_summarizer(self):
        cfg = {
            "summarizer": {
                "provider": "gemini",
                "api_key": "gemini-key",
                "model": "gemini-2.5-flash",
            }
        }

        with mock.patch.object(note_generator, "call_gemini", return_value="ok") as call_gemini:
            result = note_generator.call_llm("hello", cfg)

        self.assertEqual("ok", result)
        call_gemini.assert_called_once_with("hello", "gemini-key", "gemini-2.5-flash")

    def test_call_llm_routes_now_md_to_claude_cli(self):
        cfg = {
            "llm_provider": {
                "endpoint": "https://api.deepseek.com/v1",
                "api_key": "deepseek-key",
                "model": "deepseek-chat",
            },
            "llm_routing": {
                "session_notes": "deepseek",
                "now_md": "claude",
            },
            "claude_cli": {
                "command": "claude",
                "prompt_flag": "-p",
            },
        }

        with mock.patch.object(note_generator, "call_claude_cli", return_value="from-cli") as call_cli, mock.patch.object(
            note_generator, "call_deepseek", return_value="from-deepseek"
        ) as call_deepseek:
            result = note_generator.call_llm("hello", cfg, task="now_md")

        self.assertEqual("from-cli", result)
        call_cli.assert_called_once_with("hello", cfg)
        call_deepseek.assert_not_called()

    def test_call_llm_accepts_claude_api_provider_alias(self):
        cfg = {
            "llm_provider": {
                "provider": "claude_api",
                "api_key": "anthropic-key",
            }
        }

        with mock.patch.object(note_generator, "call_claude", return_value="from-api") as call_claude, mock.patch.object(
            note_generator, "call_deepseek", return_value="from-deepseek"
        ) as call_deepseek:
            result = note_generator.call_llm("hello", cfg)

        self.assertEqual("from-api", result)
        call_claude.assert_called_once()
        call_deepseek.assert_not_called()

    def test_call_llm_accepts_claude_cli_provider_alias_without_routing(self):
        cfg = {
            "llm_provider": {
                "provider": "claude_cli",
            },
            "claude_cli": {
                "command": "claude",
                "prompt_flag": "-p",
            },
        }

        with mock.patch.object(note_generator, "call_claude_cli", return_value="from-cli") as call_cli, mock.patch.object(
            note_generator, "call_deepseek", return_value="from-deepseek"
        ) as call_deepseek:
            result = note_generator.call_llm("hello", cfg)

        self.assertEqual("from-cli", result)
        call_cli.assert_called_once_with("hello", cfg)
        call_deepseek.assert_not_called()


if __name__ == "__main__":
    unittest.main()
