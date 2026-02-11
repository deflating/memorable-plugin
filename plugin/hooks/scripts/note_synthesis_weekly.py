#!/usr/bin/env python3
"""Weekly synthesis generation helpers."""

from datetime import date, datetime, timedelta

from note_constants import (
    MAX_WEEKLY_BULLETS_PER_TAG,
    MAX_WEEKLY_TAGS,
    WEEKLY_SYNTHESIS_PATH,
)
from note_synthesis_shared import (
    append_jsonl_entries,
    bounded_average_salience,
    build_missing_synthesis_entries,
    load_existing_periods,
    ranked_tags,
    score_entries_by_tag,
)
from note_utils import (
    is_synthesis_entry,
    note_datetime,
    note_salience,
    note_summary,
    note_timestamp,
    period_end_iso,
    utc_now_iso,
    week_start,
)


def weekly_theme_lines(
    top_tags: list[str],
    tag_buckets: dict[str, list[dict]],
) -> list[str]:
    lines: list[str] = []
    for tag in top_tags:
        lines.extend(["", f"### {tag}"])
        items = sorted(tag_buckets.get(tag, []), key=note_salience, reverse=True)
        for entry in items[:MAX_WEEKLY_BULLETS_PER_TAG]:
            ts = note_timestamp(entry)[:10]
            sid = str(entry.get("session", "")).strip()[:8]
            sid_suffix = f" [{sid}]" if sid else ""
            lines.append(f"- {ts}{sid_suffix}: {note_summary(entry)}")
    return lines


def weekly_synthesis_payload(
    week_start_date: date,
    week_end_date: date,
    week_entries: list[dict],
    lines: list[str],
    top_tags: list[str],
    avg_salience: float,
    generated_at: str,
) -> dict:
    return {
        "ts": period_end_iso(week_end_date),
        "first_ts": period_end_iso(week_start_date),
        "session": f"weekly-{week_start_date.isoformat()}",
        "note": "\n".join(lines).strip(),
        "topic_tags": top_tags,
        "salience": round(max(0.2, min(2.0, avg_salience)), 3),
        "synthesis_level": "weekly",
        "period_start": week_start_date.isoformat(),
        "period_end": week_end_date.isoformat(),
        "source_count": len(week_entries),
        "generated_at": generated_at,
    }


def build_weekly_synthesis_entry(
    week_start_date: date,
    week_entries: list[dict],
    generated_at: str,
) -> dict | None:
    if not week_entries:
        return None
    week_end_date = week_start_date + timedelta(days=6)
    scored = sorted(week_entries, key=note_salience, reverse=True)
    tag_buckets, tag_scores = score_entries_by_tag(scored)
    if not tag_buckets:
        return None
    top_tags = ranked_tags(tag_buckets, tag_scores, MAX_WEEKLY_TAGS)
    lines = [
        "## Summary",
        f"Weekly synthesis for {week_start_date.isoformat()} to {week_end_date.isoformat()}.",
    ]
    lines.extend(weekly_theme_lines(top_tags, tag_buckets))
    if not top_tags:
        lines.extend(["", "- No theme clusters identified"])
    avg_salience = bounded_average_salience(scored, 12, 0.2)
    return weekly_synthesis_payload(
        week_start_date,
        week_end_date,
        week_entries,
        lines,
        top_tags,
        avg_salience,
        generated_at,
    )


def weekly_entries_by_period(
    entries: list[dict],
    current_week: date,
) -> dict[date, list[dict]]:
    grouped: dict[date, list[dict]] = {}
    for entry in entries:
        if is_synthesis_entry(entry):
            continue
        dt = note_datetime(entry)
        if not dt:
            continue
        start = week_start(dt.date())
        if start < current_week:
            grouped.setdefault(start, []).append(entry)
    return grouped


def create_missing_weekly_syntheses(entries: list[dict], now: datetime) -> int:
    existing = load_existing_periods(WEEKLY_SYNTHESIS_PATH, "weekly")
    current_week = week_start(now.date())
    by_week = weekly_entries_by_period(entries, current_week)
    if not by_week:
        return 0
    generated_at = utc_now_iso()
    new_entries = build_missing_synthesis_entries(
        by_week, existing, build_weekly_synthesis_entry, generated_at
    )
    append_jsonl_entries(WEEKLY_SYNTHESIS_PATH, new_entries)
    return len(new_entries)
