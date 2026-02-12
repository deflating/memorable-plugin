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
import note_selection  # noqa: E402


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

    def test_collect_files_ignores_invalid_context_files_shape(self):
        config = {"context_files": {"invalid": "shape"}}
        files = session_start.collect_files(config)
        self.assertIsInstance(files, list)

    def test_parse_context_depth_clamps_invalid_values(self):
        self.assertEqual(2, session_start.parse_context_depth("2", -1))
        self.assertEqual(-1, session_start.parse_context_depth("banana", -1))
        self.assertEqual(9, session_start.parse_context_depth(9, -1))
        self.assertEqual(-1, session_start.parse_context_depth(99, -1))

    def test_core_seed_paths_includes_knowledge_seed_when_present(self):
        with tempfile.TemporaryDirectory() as td:
            seeds_dir = Path(td)
            for name in ("user.md", "agent.md", "now.md", "knowledge.md"):
                (seeds_dir / name).write_text(f"# {name}", encoding="utf-8")

            with mock.patch.object(session_start, "SEEDS_DIR", seeds_dir):
                seed_paths = session_start.core_seed_paths()

            self.assertEqual(4, len(seed_paths))
            self.assertTrue(any(path.endswith("knowledge.md") for path in seed_paths))

    def test_build_context_plan_deescalates_low_relevance_when_budget_tight(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            seeds_dir = root / "seeds"
            files_dir = root / "files"
            data_dir = root / "data"
            seeds_dir.mkdir(parents=True, exist_ok=True)
            files_dir.mkdir(parents=True, exist_ok=True)
            data_dir.mkdir(parents=True, exist_ok=True)

            for name in ("user.md", "agent.md", "now.md"):
                (seeds_dir / name).write_text(f"# {name}\n", encoding="utf-8")

            for filename in ("high.md", "low.md"):
                (files_dir / filename).write_text("# Title\n\nBody", encoding="utf-8")
                (files_dir / f"{filename}.levels.json").write_text(
                    json.dumps(
                        {
                            "levels": 3,
                            "tokens": {"1": 40, "2": 100, "3": 220},
                            "content": {"1": "summary", "2": "detail", "3": "full-ish"},
                        }
                    ),
                    encoding="utf-8",
                )

            config = {
                "token_budget": 300,
                "context_files": [
                    {"filename": "high.md", "depth": 3, "enabled": True},
                    {"filename": "low.md", "depth": 3, "enabled": True},
                ],
            }

            with mock.patch.object(session_start, "SEEDS_DIR", seeds_dir), \
                 mock.patch.object(session_start, "FILES_DIR", files_dir), \
                 mock.patch.object(session_start, "DATA_DIR", data_dir), \
                 mock.patch.object(session_start, "collect_relevance_tokens", return_value={"high"}):
                plan = session_start.build_context_plan(config)

            semantic_entries = [item for item in plan if item.get("type") == "semantic"]
            by_file = {item["filename"]: item for item in semantic_entries}
            self.assertEqual(3, by_file["high.md"]["depth"])
            self.assertEqual(1, by_file["low.md"]["depth"])
            self.assertEqual("deescalated_for_budget", by_file["low.md"]["reason"])

    def test_build_context_plan_does_not_escalate_above_configured_depth(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            seeds_dir = root / "seeds"
            files_dir = root / "files"
            data_dir = root / "data"
            seeds_dir.mkdir(parents=True, exist_ok=True)
            files_dir.mkdir(parents=True, exist_ok=True)
            data_dir.mkdir(parents=True, exist_ok=True)

            for filename in ("high.md", "low.md"):
                (files_dir / filename).write_text("# Title\n\nBody", encoding="utf-8")
                (files_dir / f"{filename}.levels.json").write_text(
                    json.dumps(
                        {
                            "levels": 3,
                            "tokens": {"1": 30, "2": 70, "3": 110},
                            "content": {"1": "summary", "2": "detail", "3": "full-ish"},
                        }
                    ),
                    encoding="utf-8",
                )

            config = {
                "token_budget": 150,
                "context_files": [
                    {"filename": "high.md", "depth": 1, "enabled": True},
                    {"filename": "low.md", "depth": 1, "enabled": True},
                ],
            }

            with mock.patch.object(session_start, "SEEDS_DIR", seeds_dir), \
                 mock.patch.object(session_start, "FILES_DIR", files_dir), \
                 mock.patch.object(session_start, "DATA_DIR", data_dir), \
                 mock.patch.object(session_start, "collect_relevance_tokens", return_value={"high"}):
                plan = session_start.build_context_plan(config)

            semantic_entries = [item for item in plan if item.get("type") == "semantic"]
            by_file = {item["filename"]: item for item in semantic_entries}
            self.assertEqual(1, by_file["high.md"]["depth"])
            self.assertEqual(1, by_file["low.md"]["depth"])
            self.assertEqual("default_level", by_file["high.md"]["reason"])


class ContextualRetrievalTests(unittest.TestCase):
    def test_build_tag_cooccurrence_graph_tracks_pair_weights(self):
        entries = [
            {"topic_tags": ["python", "testing"]},
            {"topic_tags": ["python", "release"]},
        ]
        graph = note_selection.build_tag_cooccurrence_graph(entries)

        self.assertEqual(1, graph["python"]["testing"])
        self.assertEqual(1, graph["testing"]["python"])
        self.assertEqual(1, graph["python"]["release"])
        self.assertEqual(1, graph["release"]["python"])

    def test_spread_tag_activation_reaches_second_hop(self):
        graph = {
            "python": {"testing": 2},
            "testing": {"python": 2, "release": 1},
            "release": {"testing": 1},
        }

        activation = note_selection.spread_tag_activation(graph, {"python"}, max_hops=2, decay=0.5)

        self.assertAlmostEqual(1.0, activation["python"])
        self.assertGreater(activation["testing"], 0.0)
        self.assertGreater(activation["release"], 0.0)

    def test_contextual_activation_changes_score_order(self):
        ts = datetime.now(timezone.utc).isoformat()
        entries = [
            {
                "ts": ts,
                "note": "status update",
                "salience": 1.0,
                "topic_tags": ["python"],
            },
            {
                "ts": ts,
                "note": "status update",
                "salience": 1.0,
                "topic_tags": ["gardening"],
            },
        ]
        scored = note_selection.score_entries(entries, {"tag_activation": {"python": 1.0}})
        top_score, top_entry = scored[0]
        low_score, low_entry = scored[1]

        self.assertEqual(["python"], top_entry["topic_tags"])
        self.assertEqual(["gardening"], low_entry["topic_tags"])
        self.assertGreater(top_score, low_score)


if __name__ == "__main__":
    unittest.main()
