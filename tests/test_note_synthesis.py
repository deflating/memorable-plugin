import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[1]
HOOKS_DIR = REPO_ROOT / "plugin" / "hooks" / "scripts"
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))

import note_synthesis_monthly  # noqa: E402
import note_synthesis_weekly  # noqa: E402


class WeeklySynthesisTests(unittest.TestCase):
    def test_create_missing_weekly_syntheses_skips_current_week_and_dedupes(self):
        now = datetime(2026, 2, 11, tzinfo=timezone.utc)
        entries = [
            {
                "ts": "2026-02-03T12:00:00Z",
                "session": "sess-old-1",
                "note": "old note one",
                "salience": 0.8,
                "topic_tags": ["backend"],
            },
            {
                "ts": "2026-02-04T10:00:00Z",
                "session": "sess-old-2",
                "note": "old note two",
                "salience": 0.6,
                "topic_tags": ["backend", "infra"],
            },
            {
                "ts": "2026-02-10T09:00:00Z",
                "session": "sess-current",
                "note": "current week note",
                "salience": 0.9,
                "topic_tags": ["release"],
            },
        ]

        with tempfile.TemporaryDirectory() as td:
            weekly_path = Path(td) / "weekly.jsonl"
            with mock.patch.object(note_synthesis_weekly, "WEEKLY_SYNTHESIS_PATH", weekly_path):
                created = note_synthesis_weekly.create_missing_weekly_syntheses(entries, now)
                self.assertEqual(1, created)

                lines = weekly_path.read_text(encoding="utf-8").strip().splitlines()
                self.assertEqual(1, len(lines))
                payload = json.loads(lines[0])
                self.assertEqual("weekly", payload["synthesis_level"])
                self.assertEqual("2026-02-02", payload["period_start"])
                self.assertEqual(2, payload["source_count"])

                created_again = note_synthesis_weekly.create_missing_weekly_syntheses(entries, now)
                self.assertEqual(0, created_again)


class MonthlySynthesisTests(unittest.TestCase):
    def test_create_missing_monthly_syntheses_rolls_up_prior_month_weeklies(self):
        now = datetime(2026, 2, 11, tzinfo=timezone.utc)
        entries = [
            {
                "ts": "2026-01-12T00:00:00+00:00",
                "first_ts": "2026-01-06T00:00:00+00:00",
                "session": "weekly-2026-01-06",
                "note": "## Summary\nBackend work",
                "topic_tags": ["backend", "infra"],
                "salience": 0.7,
                "synthesis_level": "weekly",
                "period_start": "2026-01-06",
                "period_end": "2026-01-12",
                "source_count": 4,
            },
            {
                "ts": "2026-01-19T00:00:00+00:00",
                "first_ts": "2026-01-13T00:00:00+00:00",
                "session": "weekly-2026-01-13",
                "note": "## Summary\nRelease prep",
                "topic_tags": ["release"],
                "salience": 0.65,
                "synthesis_level": "weekly",
                "period_start": "2026-01-13",
                "period_end": "2026-01-19",
                "source_count": 3,
            },
            {
                "ts": "2026-02-10T00:00:00+00:00",
                "first_ts": "2026-02-09T00:00:00+00:00",
                "session": "weekly-2026-02-09",
                "note": "## Summary\nCurrent month weekly",
                "topic_tags": ["current"],
                "salience": 0.75,
                "synthesis_level": "weekly",
                "period_start": "2026-02-09",
                "period_end": "2026-02-15",
                "source_count": 2,
            },
        ]

        with tempfile.TemporaryDirectory() as td:
            monthly_path = Path(td) / "monthly.jsonl"
            with mock.patch.object(
                note_synthesis_monthly, "MONTHLY_SYNTHESIS_PATH", monthly_path
            ):
                created = note_synthesis_monthly.create_missing_monthly_syntheses(entries, now)
                self.assertEqual(1, created)

                lines = monthly_path.read_text(encoding="utf-8").strip().splitlines()
                self.assertEqual(1, len(lines))
                payload = json.loads(lines[0])
                self.assertEqual("monthly", payload["synthesis_level"])
                self.assertEqual("2026-01-01", payload["period_start"])
                self.assertEqual(2, payload["source_count"])

                created_again = note_synthesis_monthly.create_missing_monthly_syntheses(
                    entries, now
                )
                self.assertEqual(0, created_again)


if __name__ == "__main__":
    unittest.main()
