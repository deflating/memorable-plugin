import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[1]
HOOKS_DIR = REPO_ROOT / "plugin" / "hooks" / "scripts"
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))

import session_start  # noqa: E402
import user_prompt  # noqa: E402


class SessionStartArchiveTests(unittest.TestCase):
    def test_archive_low_salience_notes_archives_eligible_rows(self):
        now = datetime(2026, 2, 11, tzinfo=timezone.utc)

        with tempfile.TemporaryDirectory() as td:
            notes_dir = Path(td)
            notes_file = notes_dir / "session_notes.jsonl"
            archive_file = notes_dir / session_start.ARCHIVE_DIRNAME / notes_file.name

            old_ts = (now - timedelta(days=session_start.ARCHIVE_AFTER_DAYS + 1)).isoformat().replace(
                "+00:00", "Z"
            )
            recent_ts = (now - timedelta(days=1)).isoformat().replace("+00:00", "Z")
            rows = [
                {"ts": old_ts, "salience": 0.01, "note": "archive me"},
                {"ts": old_ts, "salience": 0.8, "note": "keep me"},
                {"ts": recent_ts, "salience": 0.01, "note": "too recent"},
            ]
            with notes_file.open("w", encoding="utf-8") as fh:
                for row in rows:
                    fh.write(json.dumps(row) + "\n")
                fh.write("{not-json}\n")

            archived_count = session_start.archive_low_salience_notes(notes_dir, now)

            self.assertEqual(1, archived_count)
            updated_lines = notes_file.read_text(encoding="utf-8").strip().splitlines()
            self.assertEqual(3, len(updated_lines))
            self.assertIn('{"ts": "%s", "salience": 0.8, "note": "keep me"}' % old_ts, updated_lines)
            self.assertIn('{"ts": "%s", "salience": 0.01, "note": "too recent"}' % recent_ts, updated_lines)
            self.assertIn("{not-json}", updated_lines)

            archive_lines = archive_file.read_text(encoding="utf-8").strip().splitlines()
            self.assertEqual(1, len(archive_lines))
            self.assertIn("archive me", archive_lines[0])

    def test_archive_low_salience_notes_rolls_back_on_archive_write_failure(self):
        now = datetime(2026, 2, 11, tzinfo=timezone.utc)

        with tempfile.TemporaryDirectory() as td:
            notes_dir = Path(td)
            notes_file = notes_dir / "session_notes.jsonl"
            original_content = (
                '{"ts": "2025-01-01T00:00:00Z", "salience": 0.01, "note": "archive me"}\n'
                '{"ts": "2026-02-10T00:00:00Z", "salience": 0.9, "note": "keep me"}\n'
            )
            notes_file.write_text(original_content, encoding="utf-8")

            archive_path = notes_dir / session_start.ARCHIVE_DIRNAME / notes_file.name
            original_open = Path.open

            def fail_archive_append(self, *args, **kwargs):
                mode = kwargs.get("mode")
                if mode is None:
                    mode = args[0] if args else "r"
                if self == archive_path and "a" in mode:
                    raise OSError("simulated archive append failure")
                return original_open(self, *args, **kwargs)

            with mock.patch("pathlib.Path.open", new=fail_archive_append):
                archived_count = session_start.archive_low_salience_notes(notes_dir, now)

            self.assertEqual(0, archived_count)
            self.assertEqual(original_content, notes_file.read_text(encoding="utf-8"))
            self.assertFalse((notes_file.with_suffix(".jsonl.tmp")).exists())
            self.assertFalse((notes_file.with_suffix(".jsonl.rollback.tmp")).exists())


class UserPromptTrackingTests(unittest.TestCase):
    def setUp(self):
        self.orig_note_usage_path = user_prompt.NOTE_USAGE_PATH
        self.orig_loaded_notes_path = user_prompt.CURRENT_LOADED_NOTES_PATH
        self.orig_utc_now_iso = user_prompt._utc_now_iso

    def tearDown(self):
        user_prompt.NOTE_USAGE_PATH = self.orig_note_usage_path
        user_prompt.CURRENT_LOADED_NOTES_PATH = self.orig_loaded_notes_path
        user_prompt._utc_now_iso = self.orig_utc_now_iso

    def test_track_reference_effectiveness_updates_matching_notes(self):
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            usage_path = td_path / "note_usage.json"
            loaded_path = td_path / "current_loaded_notes.json"

            loaded_payload = {
                "notes": [
                    {
                        "key": "note-1",
                        "session": "abc123def",
                        "session_short": "abc123",
                        "tags": ["parser bug", "shipping"],
                    },
                    {
                        "key": "note-2",
                        "session": "zzz999",
                        "session_short": "zzz999",
                        "tags": ["unrelated topic"],
                    },
                ]
            }
            loaded_path.write_text(json.dumps(loaded_payload), encoding="utf-8")
            usage_path.write_text(
                json.dumps(
                    {
                        "notes": {
                            "note-1": {
                                "loaded_count": 4,
                                "referenced_count": 1,
                                "first_loaded": "2026-01-01T00:00:00Z",
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )

            user_prompt.CURRENT_LOADED_NOTES_PATH = loaded_path
            user_prompt.NOTE_USAGE_PATH = usage_path
            user_prompt._utc_now_iso = lambda: "2026-02-11T12:00:00+00:00"

            payload = {"prompt": "Please fix the parser bug before ship today."}
            user_prompt._track_reference_effectiveness(payload)

            usage = json.loads(usage_path.read_text(encoding="utf-8"))
            self.assertEqual(2, usage["notes"]["note-1"]["referenced_count"])
            self.assertEqual(
                "2026-02-11T12:00:00+00:00", usage["notes"]["note-1"]["last_referenced"]
            )
            self.assertEqual("abc123def", usage["notes"]["note-1"]["session"])
            self.assertNotIn("note-2", usage["notes"])


class SessionStartSelectionTests(unittest.TestCase):
    def test_load_all_notes_skips_archived_rows(self):
        with tempfile.TemporaryDirectory() as td:
            notes_dir = Path(td)
            notes_file = notes_dir / "session_notes.jsonl"
            notes_file.write_text(
                json.dumps({"ts": "2026-01-01T00:00:00Z", "note": "active"}) + "\n"
                + json.dumps({"ts": "2026-01-02T00:00:00Z", "note": "archived", "archived": True}) + "\n",
                encoding="utf-8",
            )

            entries = session_start.load_all_notes(notes_dir)
            self.assertEqual(1, len(entries))
            self.assertEqual("active", entries[0]["note"])

    def test_effective_salience_prioritizes_pinned_and_deprioritizes_archived(self):
        ts = datetime.now(timezone.utc).isoformat()
        base = {
            "ts": ts,
            "note": "todo: ship release",
            "salience": 1.0,
            "topic_tags": ["release"],
        }

        normal = session_start.effective_salience(dict(base), {})
        pinned = session_start.effective_salience({**base, "pinned": True}, {})
        archived = session_start.effective_salience({**base, "archived": True}, {})

        self.assertGreater(pinned, normal)
        self.assertEqual(session_start.MIN_SALIENCE, archived)


if __name__ == "__main__":
    unittest.main()
