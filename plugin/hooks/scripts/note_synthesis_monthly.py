#!/usr/bin/env python3
"""Monthly synthesis generation helpers."""

from datetime import date, datetime, timedelta

from note_constants import MAX_MONTHLY_WEEKS, MAX_WEEKLY_TAGS, MONTHLY_SYNTHESIS_PATH
from note_synthesis_shared import (
    append_jsonl_entries,
    bounded_average_salience,
    build_missing_synthesis_entries,
    load_existing_periods,
)
from note_utils import (
    month_start,
    next_month_start,
    note_datetime,
    note_summary,
    note_tags,
    note_timestamp,
    parse_iso_datetime,
    period_end_iso,
    utc_now_iso,
)


def monthly_tag_counts(entries: list[dict]) -> dict[str, int]:
    tag_counts: dict[str, int] = {}
    for entry in entries:
        for tag in note_tags(entry):
            tag_counts[tag] = tag_counts.get(tag, 0) + 1
    return tag_counts


def top_monthly_tags(tag_counts: dict[str, int]) -> list[str]:
    ranked = sorted(tag_counts.items(), key=lambda kv: (kv[1], kv[0]), reverse=True)
    return [tag for tag, _ in ranked[:MAX_WEEKLY_TAGS]]


def monthly_theme_lines(top_tags: list[str], tag_counts: dict[str, int]) -> list[str]:
    if not top_tags:
        return ["- No recurring themes detected"]
    return [f"- {tag} ({tag_counts.get(tag, 0)} weeks)" for tag in top_tags]


def monthly_highlight_lines(sorted_weeklies: list[dict]) -> list[str]:
    lines: list[str] = []
    for weekly in sorted_weeklies[:MAX_MONTHLY_WEEKS]:
        period = str(weekly.get("period_start", "")).strip()[:10]
        period_label = period if period else note_timestamp(weekly)[:10]
        lines.append(f"- Week of {period_label}: {note_summary(weekly)}")
    return lines


def monthly_synthesis_payload(
    month_start_date: date,
    month_end_date: date,
    month_weeklies: list[dict],
    lines: list[str],
    top_tags: list[str],
    avg_salience: float,
    generated_at: str,
) -> dict:
    return {
        "ts": period_end_iso(month_end_date),
        "first_ts": period_end_iso(month_start_date),
        "session": f"monthly-{month_start_date.strftime('%Y-%m')}",
        "note": "\n".join(lines).strip(),
        "topic_tags": top_tags,
        "salience": round(max(0.25, min(2.0, avg_salience)), 3),
        "synthesis_level": "monthly",
        "period_start": month_start_date.isoformat(),
        "period_end": month_end_date.isoformat(),
        "source_count": len(month_weeklies),
        "generated_at": generated_at,
    }


def build_monthly_synthesis_entry(
    month_start_date: date,
    month_weeklies: list[dict],
    generated_at: str,
) -> dict | None:
    if not month_weeklies:
        return None
    month_end_date = next_month_start(month_start_date) - timedelta(days=1)
    sorted_weeklies = sorted(month_weeklies, key=note_timestamp, reverse=True)
    tag_counts = monthly_tag_counts(month_weeklies)
    top_tags = top_monthly_tags(tag_counts)
    lines = [
        "## Summary",
        f"Monthly synthesis for {month_start_date.strftime('%Y-%m')} from {len(month_weeklies)} weekly synthesis notes.",
        "",
        "### Recurring themes",
    ]
    lines.extend(monthly_theme_lines(top_tags, tag_counts))
    lines.extend(["", "### Weekly highlights"])
    lines.extend(monthly_highlight_lines(sorted_weeklies))
    avg_salience = bounded_average_salience(sorted_weeklies, 8, 0.25)
    return monthly_synthesis_payload(
        month_start_date,
        month_end_date,
        month_weeklies,
        lines,
        top_tags,
        avg_salience,
        generated_at,
    )


def monthly_entries_by_period(
    entries: list[dict],
    current_month: date,
) -> dict[date, list[dict]]:
    grouped: dict[date, list[dict]] = {}
    for entry in entries:
        if str(entry.get("synthesis_level", "")).strip().lower() != "weekly":
            continue
        dt = parse_iso_datetime(str(entry.get("period_start", "")).strip()) or note_datetime(
            entry
        )
        if not dt:
            continue
        start = month_start(dt.date())
        if start < current_month:
            grouped.setdefault(start, []).append(entry)
    return grouped


def create_missing_monthly_syntheses(entries: list[dict], now: datetime) -> int:
    existing = load_existing_periods(MONTHLY_SYNTHESIS_PATH, "monthly")
    current_month = month_start(now.date())
    by_month = monthly_entries_by_period(entries, current_month)
    if not by_month:
        return 0
    generated_at = utc_now_iso()
    new_entries = build_missing_synthesis_entries(
        by_month, existing, build_monthly_synthesis_entry, generated_at
    )
    append_jsonl_entries(MONTHLY_SYNTHESIS_PATH, new_entries)
    return len(new_entries)
