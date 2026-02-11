#!/usr/bin/env python3
"""Low-salience note archival helpers."""

import json
from datetime import datetime, timedelta
from pathlib import Path

from note_constants import (
    ARCHIVE_AFTER_DAYS,
    ARCHIVE_DIRNAME,
    ARCHIVE_MIN_SALIENCE,
    MONTHLY_SYNTHESIS_PATH,
    WEEKLY_SYNTHESIS_PATH,
)
from note_utils import is_synthesis_entry, note_datetime, note_salience


def should_archive_entry(entry: dict, cutoff: datetime) -> bool:
    if is_synthesis_entry(entry):
        return False
    if note_salience(entry) >= ARCHIVE_MIN_SALIENCE:
        return False
    dt = note_datetime(entry)
    if not dt:
        return False
    return dt < cutoff


def archive_source_files(notes_dir: Path) -> list[Path]:
    excluded = {WEEKLY_SYNTHESIS_PATH.name, MONTHLY_SYNTHESIS_PATH.name}
    return [path for path in notes_dir.glob("*.jsonl") if path.name not in excluded]


def partition_archive_lines(jsonl_file: Path, cutoff: datetime):
    keep_lines: list[str] = []
    archive_lines: list[str] = []
    original_lines: list[str] = []
    with jsonl_file.open("r", encoding="utf-8") as fh:
        for raw_line in fh:
            line = raw_line.strip()
            if not line:
                continue
            normalized = raw_line if raw_line.endswith("\n") else raw_line + "\n"
            original_lines.append(normalized)
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                keep_lines.append(normalized)
                continue
            if should_archive_entry(obj, cutoff):
                archive_lines.append(normalized)
            else:
                keep_lines.append(normalized)
    return keep_lines, archive_lines, original_lines


def restore_archived_source(
    jsonl_file: Path,
    original_lines: list[str],
    tmp_path: Path,
    rollback_path: Path,
):
    try:
        if original_lines:
            with rollback_path.open("w", encoding="utf-8") as fh:
                fh.writelines(original_lines)
            rollback_path.replace(jsonl_file)
    except OSError:
        pass
    try:
        if tmp_path.exists():
            tmp_path.unlink()
    except OSError:
        pass
    try:
        if rollback_path.exists():
            rollback_path.unlink()
    except OSError:
        pass


def persist_archived_lines(
    jsonl_file: Path,
    archive_dir: Path,
    keep_lines: list[str],
    archive_lines: list[str],
):
    tmp_path = jsonl_file.with_suffix(jsonl_file.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as fh:
        fh.writelines(keep_lines)
    tmp_path.replace(jsonl_file)
    archive_path = archive_dir / jsonl_file.name
    with archive_path.open("a", encoding="utf-8") as fh:
        fh.writelines(archive_lines)


def archive_low_salience_notes(notes_dir: Path, now: datetime) -> int:
    archive_dir = notes_dir / ARCHIVE_DIRNAME
    archive_dir.mkdir(parents=True, exist_ok=True)
    cutoff = now - timedelta(days=ARCHIVE_AFTER_DAYS)
    archived_count = 0
    for jsonl_file in archive_source_files(notes_dir):
        try:
            keep_lines, archive_lines, original_lines = partition_archive_lines(
                jsonl_file, cutoff
            )
        except OSError:
            continue
        if not archive_lines:
            continue
        try:
            persist_archived_lines(jsonl_file, archive_dir, keep_lines, archive_lines)
            archived_count += len(archive_lines)
        except OSError:
            tmp_path = jsonl_file.with_suffix(jsonl_file.suffix + ".tmp")
            rollback_path = jsonl_file.with_suffix(
                jsonl_file.suffix + ".rollback.tmp"
            )
            restore_archived_source(jsonl_file, original_lines, tmp_path, rollback_path)
    return archived_count
