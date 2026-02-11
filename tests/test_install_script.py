import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
INSTALL_SCRIPT = REPO_ROOT / "plugin" / "install.sh"
PLUGIN_DIR = (REPO_ROOT / "plugin").resolve()


class InstallScriptTests(unittest.TestCase):
    def _run_install(self, home_dir: Path):
        env = os.environ.copy()
        env["HOME"] = str(home_dir)
        subprocess.run(
            ["bash", str(INSTALL_SCRIPT)],
            cwd=str(REPO_ROOT),
            env=env,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

    def test_fresh_install_creates_expected_structure(self):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            self._run_install(home)

            data_dir = home / ".memorable" / "data"
            for rel in ("seeds", "notes", "sessions", "files", "transcripts"):
                self.assertTrue((data_dir / rel).is_dir(), rel)

            config = json.loads((data_dir / "config.json").read_text(encoding="utf-8"))
            self.assertIn("token_budget", config)
            self.assertIn("server_port", config)
            self.assertIn("llm_provider", config)
            self.assertIn("daemon", config)
            self.assertIn("context_files", config)

            plugin_link = home / ".memorable" / "plugin"
            self.assertTrue(plugin_link.is_symlink())
            self.assertEqual(PLUGIN_DIR, plugin_link.resolve())

            hooks_file = home / ".claude" / "hooks" / "hooks.json"
            hooks = json.loads(hooks_file.read_text(encoding="utf-8"))
            self.assertIn("SessionStart", hooks)
            self.assertIn("PreCompact", hooks)
            self.assertIn("UserPromptSubmit", hooks)

            session_start_cmds = [
                h["command"]
                for entry in hooks["SessionStart"]
                for h in entry.get("hooks", [])
                if h.get("type") == "command"
            ]
            self.assertIn(f"python3 {PLUGIN_DIR}/hooks/scripts/session_start.py", session_start_cmds)

    def test_install_replaces_stale_memorable_entries_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            hooks_dir = home / ".claude" / "hooks"
            hooks_dir.mkdir(parents=True, exist_ok=True)
            hooks_file = hooks_dir / "hooks.json"

            hooks_file.write_text(
                json.dumps(
                    {
                        "SessionStart": [
                            {
                                "matcher": "*",
                                "hooks": [
                                    {
                                        "type": "command",
                                        "command": "python3 /old/path/hooks/scripts/session_start.py",
                                        "timeout": 15,
                                    }
                                ],
                            }
                        ],
                        "PreCompact": [
                            {
                                "matcher": "*",
                                "hooks": [
                                    {
                                        "type": "command",
                                        "command": "python3 /old/path/hooks/scripts/session_start.py --compact",
                                        "timeout": 15,
                                    }
                                ],
                            }
                        ],
                        "UserPromptSubmit": [
                            {
                                "matcher": "*",
                                "hooks": [
                                    {
                                        "type": "command",
                                        "command": "python3 /old/path/hooks/scripts/user_prompt.py",
                                        "timeout": 5,
                                    }
                                ],
                            }
                        ],
                        "Stop": [
                            {
                                "matcher": "*",
                                "hooks": [
                                    {
                                        "type": "command",
                                        "command": "echo keep-me",
                                        "timeout": 1,
                                    }
                                ],
                            }
                        ],
                    },
                    indent=2,
                ) + "\n",
                encoding="utf-8",
            )

            self._run_install(home)
            self._run_install(home)

            hooks = json.loads(hooks_file.read_text(encoding="utf-8"))

            # Ensure unrelated hooks are preserved.
            self.assertIn("Stop", hooks)
            self.assertEqual("echo keep-me", hooks["Stop"][0]["hooks"][0]["command"])

            def count_memorable(event_name: str, needle: str):
                return sum(
                    1
                    for entry in hooks.get(event_name, [])
                    for h in entry.get("hooks", [])
                    if h.get("command") == needle
                )

            self.assertEqual(
                1,
                count_memorable(
                    "SessionStart",
                    f"python3 {PLUGIN_DIR}/hooks/scripts/session_start.py",
                ),
            )
            self.assertEqual(
                1,
                count_memorable(
                    "PreCompact",
                    f"python3 {PLUGIN_DIR}/hooks/scripts/session_start.py --compact",
                ),
            )
            self.assertEqual(
                1,
                count_memorable(
                    "UserPromptSubmit",
                    f"python3 {PLUGIN_DIR}/hooks/scripts/user_prompt.py",
                ),
            )

            # Ensure stale entries from old paths are gone.
            all_cmds = [
                h.get("command", "")
                for entries in hooks.values()
                if isinstance(entries, list)
                for entry in entries
                if isinstance(entry, dict)
                for h in entry.get("hooks", [])
                if isinstance(h, dict)
            ]
            self.assertNotIn("python3 /old/path/hooks/scripts/session_start.py", all_cmds)
            self.assertNotIn("python3 /old/path/hooks/scripts/session_start.py --compact", all_cmds)
            self.assertNotIn("python3 /old/path/hooks/scripts/user_prompt.py", all_cmds)


if __name__ == "__main__":
    unittest.main()
