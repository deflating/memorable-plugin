#!/usr/bin/env python3
"""Common note and datetime helpers for maintenance workflows."""

from datetime import date, datetime, timedelta, timezone


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def note_text(entry: dict) -> str:
    text = entry.get("note", "")
    return text if isinstance(text, str) else str(text)


def note_summary(entry: dict) -> str:
    text = note_text(entry)
    for line in text.splitlines():
        stripped = line.strip().lstrip("#").strip()
        if stripped and stripped.lower() != "summary":
            return stripped
    return "No summary"


def note_timestamp(entry: dict) -> str:
    return entry.get("first_ts", entry.get("ts", ""))


def parse_iso_datetime(value: str) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def note_datetime(entry: dict) -> datetime | None:
    return parse_iso_datetime(note_timestamp(entry))


def note_salience(entry: dict) -> float:
    try:
        return float(entry.get("salience", 0.0))
    except (TypeError, ValueError):
        return 0.0


def note_tags(entry: dict) -> list[str]:
    raw = entry.get("topic_tags", [])
    if not isinstance(raw, list):
        return []
    return [str(tag).strip() for tag in raw if str(tag).strip()]


def is_synthesis_entry(entry: dict) -> bool:
    level = str(entry.get("synthesis_level", "")).strip().lower()
    return level in {"weekly", "monthly"}


def week_start(d: date) -> date:
    return d - timedelta(days=d.weekday())


def month_start(d: date) -> date:
    return date(d.year, d.month, 1)


def next_month_start(d: date) -> date:
    if d.month == 12:
        return date(d.year + 1, 1, 1)
    return date(d.year, d.month + 1, 1)


def period_end_iso(d: date) -> str:
    return datetime.combine(d, datetime.min.time(), tzinfo=timezone.utc).isoformat()
