#!/usr/bin/env python3
"""Shared helpers for synthesis generation."""

import json
from datetime import date
from pathlib import Path

from note_utils import note_salience, note_tags


def load_existing_periods(path: Path, level: str) -> set[str]:
    periods: set[str] = set()
    try:
        if not path.exists():
            return periods
        with path.open("r", encoding="utf-8") as fh:
            for raw_line in fh:
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if str(obj.get("synthesis_level", "")).strip().lower() != level:
                    continue
                period = str(obj.get("period_start", "")).strip()
                if period:
                    periods.add(period)
    except OSError:
        pass
    return periods


def append_jsonl_entries(path: Path, entries: list[dict]):
    if not entries:
        return
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            for entry in entries:
                fh.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
    except OSError:
        pass


def score_entries_by_tag(entries: list[dict]):
    tag_buckets: dict[str, list[dict]] = {}
    tag_scores: dict[str, float] = {}
    for entry in entries:
        tags = note_tags(entry) or ["untagged"]
        score = max(0.0, note_salience(entry))
        for tag in tags:
            tag_buckets.setdefault(tag, []).append(entry)
            tag_scores[tag] = tag_scores.get(tag, 0.0) + score
    return tag_buckets, tag_scores


def ranked_tags(
    tag_buckets: dict[str, list[dict]],
    tag_scores: dict[str, float],
    limit: int,
) -> list[str]:
    ranked = sorted(
        tag_scores.items(),
        key=lambda kv: (kv[1], len(tag_buckets.get(kv[0], []))),
        reverse=True,
    )[:limit]
    return [tag for tag, _ in ranked]


def bounded_average_salience(entries: list[dict], window: int, fallback: float) -> float:
    baseline = entries[: min(window, len(entries))]
    if not baseline:
        return fallback
    total = sum(max(0.0, note_salience(entry)) for entry in baseline)
    return total / float(len(baseline))


def build_missing_synthesis_entries(
    grouped: dict[date, list[dict]],
    existing: set[str],
    build_entry,
    generated_at: str,
) -> list[dict]:
    new_entries = []
    for start in sorted(grouped):
        if start.isoformat() in existing:
            continue
        built = build_entry(start, grouped[start], generated_at)
        if built:
            new_entries.append(built)
    return new_entries
