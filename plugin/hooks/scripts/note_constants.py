#!/usr/bin/env python3
"""Shared paths and constants for note maintenance."""

from pathlib import Path

BASE_DIR = Path.home() / ".memorable"
DATA_DIR = BASE_DIR / "data"
NOTES_DIR = DATA_DIR / "notes"

NOTE_MAINTENANCE_PATH = DATA_DIR / "note_maintenance.json"

WEEKLY_SYNTHESIS_PATH = NOTES_DIR / "synthesis_weekly.jsonl"
MONTHLY_SYNTHESIS_PATH = NOTES_DIR / "synthesis_monthly.jsonl"

ARCHIVE_DIRNAME = "archive"
ARCHIVE_MIN_SALIENCE = 0.1
ARCHIVE_AFTER_DAYS = 90
MAINTENANCE_INTERVAL_HOURS = 24
