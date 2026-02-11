#!/usr/bin/env python3
"""Persistence helpers for note maintenance data."""

import json
from pathlib import Path

from note_constants import NOTE_MAINTENANCE_PATH


def load_note_maintenance_state() -> dict:
    try:
        if NOTE_MAINTENANCE_PATH.exists():
            data = json.loads(NOTE_MAINTENANCE_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return {}


def save_note_maintenance_state(state: dict):
    try:
        NOTE_MAINTENANCE_PATH.write_text(
            json.dumps(state, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception:
        pass


def load_all_notes(notes_dir: Path) -> list[dict]:
    entries = []
    for jsonl_file in notes_dir.glob("*.jsonl"):
        try:
            with open(jsonl_file) as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                        if not isinstance(obj, dict):
                            continue
                        if bool(obj.get("archived", False)):
                            continue
                        entries.append(obj)
                    except json.JSONDecodeError:
                        continue
        except OSError:
            continue
    return entries
