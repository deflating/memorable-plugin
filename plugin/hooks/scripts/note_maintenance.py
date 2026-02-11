#!/usr/bin/env python3
"""Note maintenance orchestration with a small public API."""

from datetime import datetime, timedelta, timezone
from pathlib import Path

from note_archive import archive_low_salience_notes
from note_constants import ARCHIVE_AFTER_DAYS, ARCHIVE_DIRNAME, MAINTENANCE_INTERVAL_HOURS
from note_store import load_all_notes, load_note_maintenance_state, save_note_maintenance_state
from note_synthesis import create_missing_monthly_syntheses, create_missing_weekly_syntheses
from note_utils import parse_iso_datetime, utc_now_iso

__all__ = [
    "ARCHIVE_AFTER_DAYS",
    "ARCHIVE_DIRNAME",
    "archive_low_salience_notes",
    "load_all_notes",
    "run_hierarchical_consolidation",
    "run_maintenance_cycle",
]


def run_maintenance_cycle(notes_dir: Path, entries: list[dict], now: datetime):
    archived = archive_low_salience_notes(notes_dir, now)
    entries = load_all_notes(notes_dir)
    weekly_created = create_missing_weekly_syntheses(entries, now)
    if weekly_created:
        entries = load_all_notes(notes_dir)
    monthly_created = create_missing_monthly_syntheses(entries, now)
    if monthly_created:
        entries = load_all_notes(notes_dir)
    return entries, archived, weekly_created, monthly_created


def run_hierarchical_consolidation(notes_dir: Path, entries: list[dict]) -> list[dict]:
    now = datetime.now(timezone.utc)
    state = load_note_maintenance_state()
    last_run = parse_iso_datetime(state.get("last_run", ""))
    if last_run and (now - last_run) < timedelta(hours=MAINTENANCE_INTERVAL_HOURS):
        return entries

    archived = weekly_created = monthly_created = 0
    try:
        entries, archived, weekly_created, monthly_created = run_maintenance_cycle(
            notes_dir, entries, now
        )
    finally:
        save_note_maintenance_state(
            {
                "last_run": utc_now_iso(),
                "archived": archived,
                "weekly_created": weekly_created,
                "monthly_created": monthly_created,
            }
        )

    if archived or weekly_created or monthly_created:
        print(
            f"\n[Memorable] Note consolidation: archived={archived}, "
            f"weekly={weekly_created}, monthly={monthly_created}."
        )
    return entries
