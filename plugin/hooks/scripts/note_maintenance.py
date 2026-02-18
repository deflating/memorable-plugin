#!/usr/bin/env python3
"""Note maintenance orchestration with a small public API."""

from datetime import datetime, timedelta, timezone
from pathlib import Path

from knowledge_builder import update_knowledge_seed
from note_archive import archive_low_salience_notes
from note_consolidation import run_consolidation
from note_constants import ARCHIVE_AFTER_DAYS, ARCHIVE_DIRNAME, MAINTENANCE_INTERVAL_HOURS
from note_store import load_all_notes, load_note_maintenance_state, save_note_maintenance_state
from note_utils import parse_iso_datetime, utc_now_iso

__all__ = [
    "ARCHIVE_AFTER_DAYS",
    "ARCHIVE_DIRNAME",
    "archive_low_salience_notes",
    "load_all_notes",
    "run_hierarchical_consolidation",
    "run_maintenance_cycle",
]


def _get_config() -> dict:
    """Load Memorable config for LLM access during consolidation."""
    import json
    config_path = Path.home() / ".memorable" / "data" / "config.json"
    try:
        if config_path.exists():
            return json.loads(config_path.read_text())
    except Exception:
        pass
    return {}


def run_maintenance_cycle(notes_dir: Path, entries: list[dict], now: datetime):
    # Step 1: LLM-based consolidation of fading notes (before archival)
    consolidated = 0
    try:
        cfg = _get_config()
        consolidated = run_consolidation(notes_dir, cfg)
        if consolidated:
            entries = load_all_notes(notes_dir)
    except Exception:
        pass  # non-fatal — consolidation is best-effort

    # Step 2: Archive notes that have decayed below threshold
    archived = archive_low_salience_notes(notes_dir, now)
    entries = load_all_notes(notes_dir)

    # Step 3: Update knowledge seed
    knowledge_facts = update_knowledge_seed(entries, now)
    return entries, archived, knowledge_facts


def run_hierarchical_consolidation(notes_dir: Path, entries: list[dict]) -> list[dict]:
    now = datetime.now(timezone.utc)
    state = load_note_maintenance_state()
    last_run = parse_iso_datetime(state.get("last_run", ""))
    if last_run and (now - last_run) < timedelta(hours=MAINTENANCE_INTERVAL_HOURS):
        return entries

    archived = knowledge_facts = 0
    try:
        entries, archived, knowledge_facts = run_maintenance_cycle(
            notes_dir, entries, now
        )
    finally:
        save_note_maintenance_state(
            {
                "last_run": utc_now_iso(),
                "archived": archived,
                "knowledge_facts": knowledge_facts,
            }
        )

    if archived or knowledge_facts:
        print(
            f"\n[Memorable] Maintenance: archived={archived}, "
            f"knowledge_facts={knowledge_facts}."
        )
    return entries
