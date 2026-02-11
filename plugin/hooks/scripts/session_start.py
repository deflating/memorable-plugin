#!/usr/bin/env python3
"""SessionStart / PreCompact hook for Memorable.

Outputs read instructions for seed files and context files so Claude
actively reads them with the Read tool, rather than passively receiving
content in a system reminder. Also surfaces session notes with a recency
ceiling: the most recent notes are always included regardless of salience.
"""

import json
import hashlib
import platform
import re
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

BASE_DIR = Path.home() / ".memorable"
DATA_DIR = BASE_DIR / "data"
SEEDS_DIR = DATA_DIR / "seeds"
FILES_DIR = DATA_DIR / "files"
CONFIG_PATH = DATA_DIR / "config.json"
NOTE_USAGE_PATH = DATA_DIR / "note_usage.json"
CURRENT_LOADED_NOTES_PATH = DATA_DIR / "current_loaded_notes.json"

ANCHOR = "\u2693"
_ANCHOR_RE = re.compile(ANCHOR + r"([0-3]\ufe0f\u20e3)?")
_WORD_RE = re.compile(r"[A-Za-z0-9_']+")
_BULLET_RE = re.compile(r"^\s*[-*]\s+", re.MULTILINE)
_ACTION_CUE_RE = re.compile(
    r"\b(todo|next step|next steps|action(?:s| items?)?|follow[- ]?up|"
    r"decide|decision|blocked|blocker|unblock|deadline|ship|fix|implement|resolve)\b",
    re.IGNORECASE,
)

# Note loading constants
DECAY_FACTOR = 0.97
MIN_SALIENCE = 0.05
MAX_SALIENT_NOTES = 8
RECENCY_CEILING = 3  # Always include this many most-recent notes
CURRENT_MACHINE = platform.node().split(".")[0].strip().lower()
AUTO_NOW_MARKER = "<!-- memorable:auto-now -->"
WEEKLY_SYNTHESIS_PATH = DATA_DIR / "notes" / "synthesis_weekly.jsonl"
MONTHLY_SYNTHESIS_PATH = DATA_DIR / "notes" / "synthesis_monthly.jsonl"
NOTE_MAINTENANCE_PATH = DATA_DIR / "note_maintenance.json"
ARCHIVE_DIRNAME = "archive"
ARCHIVE_MIN_SALIENCE = 0.1
ARCHIVE_AFTER_DAYS = 90
MAINTENANCE_INTERVAL_HOURS = 24
MAX_WEEKLY_TAGS = 6
MAX_WEEKLY_BULLETS_PER_TAG = 3
MAX_MONTHLY_WEEKS = 8
PINNED_SALIENCE_BOOST = 0.8


def load_config() -> dict:
    try:
        if CONFIG_PATH.exists():
            return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def sanitize_filename(filename: str) -> str:
    """Keep only safe filename characters."""
    return "".join(c for c in filename if c.isalnum() or c in "-_.").strip()


def extract_at_depth(anchored_text: str, max_depth: int) -> str:
    """Extract content from anchored text up to max_depth, stripping markers."""
    if max_depth < 0:
        return anchored_text

    result = []
    pos = 0
    depth_stack = []

    for match in _ANCHOR_RE.finditer(anchored_text):
        level_str = match.group(1)
        start = match.start()
        end = match.end()

        if level_str:
            level = int(level_str[0])
            if depth_stack and depth_stack[-1] <= max_depth:
                result.append(anchored_text[pos:start])
            elif not depth_stack and pos == 0:
                before = anchored_text[:start].strip()
                if before:
                    result.append(before + " ")
            depth_stack.append(level)
            pos = end
        else:
            if depth_stack:
                if depth_stack[-1] <= max_depth:
                    result.append(anchored_text[pos:start])
                depth_stack.pop()
            pos = end

    if depth_stack and depth_stack[-1] <= max_depth:
        result.append(anchored_text[pos:])
    elif not depth_stack:
        trailing = anchored_text[pos:].strip()
        if trailing:
            result.append(trailing)

    text = "".join(result).strip()
    text = re.sub(r" {2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text


def prepare_context_file(filename: str, depth: int) -> str | None:
    """Prepare a context file for loading, returning the path to read.

    For anchored files with a specific depth, extracts content and writes
    a cached version. Returns the path Claude should read.
    """
    safe_filename = sanitize_filename(filename)
    if not safe_filename:
        return None

    raw_path = FILES_DIR / safe_filename
    anchored_path = FILES_DIR / f"{safe_filename}.anchored"

    # If anchored version exists and depth is set (not full/-1)
    if anchored_path.is_file() and depth >= 0:
        anchored_text = anchored_path.read_text(encoding="utf-8")
        extracted = extract_at_depth(anchored_text, depth)

        # Write to a cached extraction file
        cache_path = FILES_DIR / f".cache-{safe_filename}-depth{depth}.md"
        cache_path.write_text(extracted, encoding="utf-8")
        return str(cache_path)

    # Full depth or no anchored version — serve raw file
    if raw_path.is_file():
        return str(raw_path)

    return None


def collect_files(config: dict) -> list[str]:
    """Collect all files that should be read, in order."""
    paths = []

    # Core seed files
    for name in ("user.md", "agent.md", "now.md"):
        path = SEEDS_DIR / name
        if path.is_file():
            paths.append(str(path))

    # Additional context files from config
    for entry in config.get("context_files", []):
        if not entry.get("enabled", True):
            continue
        filename = sanitize_filename(entry.get("filename", ""))
        if not filename:
            continue

        # Skip if already covered by seeds above
        seed_path = SEEDS_DIR / filename
        if seed_path.is_file() and str(seed_path) in paths:
            continue

        depth = entry.get("depth", -1)
        prepared = prepare_context_file(filename, depth)
        if prepared:
            paths.append(prepared)
            continue

        # Fallback: check seeds dir
        if seed_path.is_file():
            paths.append(str(seed_path))

    return paths


def _effective_salience(entry: dict, usage_notes: dict | None = None) -> float:
    """Calculate effective salience with decay + density + actionability."""
    if bool(entry.get("archived", False)):
        return MIN_SALIENCE

    try:
        salience = float(entry.get("salience", 1.0))
    except (TypeError, ValueError):
        salience = 1.0

    try:
        emotional_weight = float(entry.get("emotional_weight", 0.3))
    except (TypeError, ValueError):
        emotional_weight = 0.3
    emotional_weight = max(0.0, min(1.0, emotional_weight))

    last_ref = entry.get("last_referenced", entry.get("ts", ""))
    try:
        ts_clean = str(last_ref).replace("Z", "+00:00")
        dt = datetime.fromisoformat(ts_clean)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        days = (datetime.now(timezone.utc) - dt).total_seconds() / 86400
    except (ValueError, TypeError):
        days = 30

    adjusted_days = days * (1.0 - emotional_weight * 0.5)
    decayed = salience * (DECAY_FACTOR ** adjusted_days)
    if bool(entry.get("pinned", False)):
        decayed += PINNED_SALIENCE_BOOST
    base = max(MIN_SALIENCE, decayed)
    density_mult = _information_density_multiplier(entry)
    actionability_mult = _actionability_multiplier(entry)
    context_mult = _time_machine_context_multiplier(entry)
    reference_mult = _reference_effectiveness_multiplier(entry, usage_notes or {})
    return max(
        MIN_SALIENCE,
        base * density_mult * actionability_mult * context_mult * reference_mult,
    )


def _note_text(entry: dict) -> str:
    text = entry.get("note", "")
    return text if isinstance(text, str) else str(text)


def _information_density_multiplier(entry: dict) -> float:
    """Score notes by signal per token (short dense > long rambling)."""
    text = _note_text(entry).strip()
    if not text:
        return 1.0

    words = _WORD_RE.findall(text.lower())
    if not words:
        return 1.0

    word_count = len(words)
    unique_ratio = len(set(words)) / word_count
    est_tokens = max(1, len(text) // 4)
    words_per_token = word_count / est_tokens

    lexical_score = max(0.0, min(1.0, (unique_ratio - 0.25) / 0.55))
    density_score = max(0.0, min(1.0, words_per_token / 0.85))

    # Softly penalize extremely long notes unless they are exceptionally dense.
    token_penalty = 0.0
    if est_tokens > 450:
        token_penalty = min(0.25, (est_tokens - 450) / 2200)

    score = (0.55 * lexical_score) + (0.45 * density_score) - token_penalty
    score = max(0.0, min(1.0, score))

    # 0.80x .. 1.30x
    return 0.8 + (0.5 * score)


def _actionability_multiplier(entry: dict) -> float:
    """Boost notes with clear next actions, blockers, or explicit action items."""
    text = _note_text(entry)
    score = 0.0

    if _ACTION_CUE_RE.search(text):
        score += 0.4

    bullet_count = len(_BULLET_RE.findall(text))
    if bullet_count >= 2:
        score += 0.25
    elif bullet_count == 1:
        score += 0.15

    action_items = entry.get("action_items", [])
    if isinstance(action_items, list):
        valid_items = [str(x).strip() for x in action_items if str(x).strip()]
        if valid_items:
            score += min(0.45, 0.15 + (0.1 * len(valid_items)))

    score = max(0.0, min(1.0, score))
    # 1.00x .. 1.35x
    return 1.0 + (0.35 * score)


def _time_machine_context_multiplier(entry: dict) -> float:
    """Boost notes matching current machine and time-of-day usage patterns."""
    now = datetime.now(timezone.utc)

    ts = _note_timestamp(entry)
    try:
        dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        dt = None

    # Hour proximity boost: notes near current hour are more likely relevant.
    hour_boost = 0.0
    if dt:
        note_hour = dt.astimezone(timezone.utc).hour
        now_hour = now.hour
        delta = min((now_hour - note_hour) % 24, (note_hour - now_hour) % 24)
        # 0h -> 1.0, 6h -> 0.0, >=6h clamped
        closeness = max(0.0, (6.0 - float(delta)) / 6.0)
        hour_boost = 0.15 * closeness

    # Machine match boost: prioritize notes from same machine.
    machine_boost = 0.0
    raw_machine = str(entry.get("machine", "")).strip().lower()
    if raw_machine and CURRENT_MACHINE:
        note_machine = raw_machine.split(".")[0]
        if note_machine == CURRENT_MACHINE:
            machine_boost = 0.12

    # 0.95x floor for mismatched context, up to ~1.27x for strong match.
    return 0.95 + hour_boost + machine_boost


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _note_key(entry: dict) -> str:
    """Stable key used for tracking load/reference effectiveness."""
    session = str(entry.get("session", "")).strip()
    ts = _note_timestamp(entry)
    if session:
        return f"{session}|{ts}"
    digest = hashlib.sha1(_note_text(entry).encode("utf-8")).hexdigest()[:12]
    return f"{ts}|{digest}"


def _load_note_usage() -> dict:
    """Load note usage counters from disk."""
    try:
        if NOTE_USAGE_PATH.exists():
            data = json.loads(NOTE_USAGE_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict) and isinstance(data.get("notes"), dict):
                return data
    except Exception:
        pass
    return {"notes": {}}


def _save_note_usage(data: dict):
    """Persist note usage counters to disk (best effort)."""
    try:
        NOTE_USAGE_PATH.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception:
        pass


def _reference_effectiveness_multiplier(entry: dict, usage_notes: dict) -> float:
    """Boost notes that are consistently referenced after being loaded."""
    rec = usage_notes.get(_note_key(entry))
    if not isinstance(rec, dict):
        return 1.0

    try:
        loaded = int(rec.get("loaded_count", 0))
    except (TypeError, ValueError):
        loaded = 0
    try:
        referenced = int(rec.get("referenced_count", 0))
    except (TypeError, ValueError):
        referenced = 0

    if loaded < 3:
        return 1.0

    ratio = 0.0 if loaded <= 0 else max(0.0, min(1.0, referenced / float(loaded)))
    # 0.85x (rarely referenced) .. 1.25x (consistently referenced)
    return 0.85 + (0.4 * ratio)


def _record_loaded_notes(selected_entries: list[dict], usage_data: dict):
    """Record which notes were loaded this session and increment load counts."""
    usage_notes = usage_data.setdefault("notes", {})
    now_iso = _utc_now_iso()
    by_key = {}

    for entry in selected_entries:
        key = _note_key(entry)
        session = str(entry.get("session", "")).strip()
        tags = entry.get("topic_tags", [])
        if not isinstance(tags, list):
            tags = []
        tags = [str(t).strip() for t in tags if str(t).strip()]

        by_key[key] = {
            "key": key,
            "session": session,
            "session_short": session[:8],
            "tags": tags,
        }

        rec = usage_notes.setdefault(
            key,
            {
                "loaded_count": 0,
                "referenced_count": 0,
                "first_loaded": now_iso,
            },
        )
        rec["loaded_count"] = int(rec.get("loaded_count", 0)) + 1
        rec["last_loaded"] = now_iso
        rec["session"] = session
        rec["session_short"] = session[:8]
        rec["tags"] = tags
        rec["timestamp"] = _note_timestamp(entry)

    _save_note_usage(usage_data)

    # Write currently loaded notes for UserPromptSubmit matching.
    try:
        CURRENT_LOADED_NOTES_PATH.write_text(
            json.dumps(
                {
                    "updated_at": now_iso,
                    "notes": list(by_key.values()),
                },
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
    except Exception:
        pass


def _note_timestamp(entry: dict) -> str:
    """Get the best timestamp for recency sorting."""
    return entry.get("first_ts", entry.get("ts", ""))


def _parse_iso_datetime(value: str) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def _note_datetime(entry: dict) -> datetime | None:
    return _parse_iso_datetime(_note_timestamp(entry))


def _note_salience(entry: dict) -> float:
    try:
        return float(entry.get("salience", 0.0))
    except (TypeError, ValueError):
        return 0.0


def _note_tags(entry: dict) -> list[str]:
    raw = entry.get("topic_tags", [])
    if not isinstance(raw, list):
        return []
    return [str(tag).strip() for tag in raw if str(tag).strip()]


def _is_synthesis_entry(entry: dict) -> bool:
    level = str(entry.get("synthesis_level", "")).strip().lower()
    return level in {"weekly", "monthly"}


def _week_start(d: date) -> date:
    return d - timedelta(days=d.weekday())


def _month_start(d: date) -> date:
    return date(d.year, d.month, 1)


def _next_month_start(d: date) -> date:
    if d.month == 12:
        return date(d.year + 1, 1, 1)
    return date(d.year, d.month + 1, 1)


def _period_end_iso(d: date) -> str:
    return datetime.combine(d, datetime.min.time(), tzinfo=timezone.utc).isoformat()


def _load_note_maintenance_state() -> dict:
    try:
        if NOTE_MAINTENANCE_PATH.exists():
            data = json.loads(NOTE_MAINTENANCE_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return {}


def _save_note_maintenance_state(state: dict):
    try:
        NOTE_MAINTENANCE_PATH.write_text(
            json.dumps(state, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception:
        pass


def _should_archive_entry(entry: dict, cutoff: datetime) -> bool:
    if _is_synthesis_entry(entry):
        return False
    if _note_salience(entry) >= ARCHIVE_MIN_SALIENCE:
        return False
    dt = _note_datetime(entry)
    if not dt:
        return False
    return dt < cutoff


def _archive_low_salience_notes(notes_dir: Path, now: datetime) -> int:
    archive_dir = notes_dir / ARCHIVE_DIRNAME
    archive_dir.mkdir(parents=True, exist_ok=True)

    cutoff = now - timedelta(days=ARCHIVE_AFTER_DAYS)
    archived_count = 0

    for jsonl_file in notes_dir.glob("*.jsonl"):
        if jsonl_file.name in {
            WEEKLY_SYNTHESIS_PATH.name,
            MONTHLY_SYNTHESIS_PATH.name,
        }:
            continue

        keep_lines: list[str] = []
        archive_lines: list[str] = []
        original_lines: list[str] = []

        try:
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

                    if _should_archive_entry(obj, cutoff):
                        archive_lines.append(normalized)
                    else:
                        keep_lines.append(normalized)
        except OSError:
            continue

        if not archive_lines:
            continue

        tmp_path = jsonl_file.with_suffix(jsonl_file.suffix + ".tmp")
        rollback_path = jsonl_file.with_suffix(jsonl_file.suffix + ".rollback.tmp")
        try:
            with tmp_path.open("w", encoding="utf-8") as fh:
                fh.writelines(keep_lines)
            tmp_path.replace(jsonl_file)

            archive_path = archive_dir / jsonl_file.name
            with archive_path.open("a", encoding="utf-8") as fh:
                fh.writelines(archive_lines)
            archived_count += len(archive_lines)
        except OSError:
            # If archiving failed after source rewrite, restore original source
            # so we don't lose records on partial failures.
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

    return archived_count


def _load_existing_periods(path: Path, level: str) -> set[str]:
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


def _append_jsonl_entries(path: Path, entries: list[dict]):
    if not entries:
        return
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            for entry in entries:
                fh.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
    except OSError:
        pass


def _build_weekly_synthesis_entry(
    week_start_date: date,
    week_entries: list[dict],
    generated_at: str,
) -> dict | None:
    if not week_entries:
        return None

    week_end_date = week_start_date + timedelta(days=6)
    scored = sorted(week_entries, key=_note_salience, reverse=True)

    tag_buckets: dict[str, list[dict]] = {}
    tag_scores: dict[str, float] = {}
    for entry in scored:
        tags = _note_tags(entry) or ["untagged"]
        score = max(0.0, _note_salience(entry))
        for tag in tags:
            tag_buckets.setdefault(tag, []).append(entry)
            tag_scores[tag] = tag_scores.get(tag, 0.0) + score

    if not tag_buckets:
        return None

    ranked_tags = sorted(
        tag_scores.items(),
        key=lambda kv: (kv[1], len(tag_buckets.get(kv[0], []))),
        reverse=True,
    )[:MAX_WEEKLY_TAGS]
    top_tags = [tag for tag, _ in ranked_tags]

    lines = [
        "## Summary",
        (
            f"Weekly synthesis for {week_start_date.isoformat()} "
            f"to {week_end_date.isoformat()}."
        ),
    ]

    for tag in top_tags:
        lines.append("")
        lines.append(f"### {tag}")
        items = sorted(tag_buckets.get(tag, []), key=_note_salience, reverse=True)
        for entry in items[:MAX_WEEKLY_BULLETS_PER_TAG]:
            ts = _note_timestamp(entry)[:10]
            sid = str(entry.get("session", "")).strip()[:8]
            sid_suffix = f" [{sid}]" if sid else ""
            lines.append(f"- {ts}{sid_suffix}: {_note_summary(entry)}")

    if not top_tags:
        lines.extend(["", "- No theme clusters identified"])

    baseline = scored[: min(12, len(scored))]
    avg_salience = (
        sum(max(0.0, _note_salience(entry)) for entry in baseline) / float(len(baseline))
        if baseline
        else 0.2
    )

    return {
        "ts": _period_end_iso(week_end_date),
        "first_ts": _period_end_iso(week_start_date),
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


def _create_missing_weekly_syntheses(entries: list[dict], now: datetime) -> int:
    existing = _load_existing_periods(WEEKLY_SYNTHESIS_PATH, "weekly")
    current_week = _week_start(now.date())

    by_week: dict[date, list[dict]] = {}
    for entry in entries:
        if _is_synthesis_entry(entry):
            continue
        dt = _note_datetime(entry)
        if not dt:
            continue
        week_start_date = _week_start(dt.date())
        if week_start_date >= current_week:
            continue
        by_week.setdefault(week_start_date, []).append(entry)

    if not by_week:
        return 0

    generated_at = _utc_now_iso()
    new_entries = []
    for week_start_date in sorted(by_week):
        period_key = week_start_date.isoformat()
        if period_key in existing:
            continue
        built = _build_weekly_synthesis_entry(week_start_date, by_week[week_start_date], generated_at)
        if built:
            new_entries.append(built)

    _append_jsonl_entries(WEEKLY_SYNTHESIS_PATH, new_entries)
    return len(new_entries)


def _build_monthly_synthesis_entry(
    month_start_date: date,
    month_weeklies: list[dict],
    generated_at: str,
) -> dict | None:
    if not month_weeklies:
        return None

    month_end_date = _next_month_start(month_start_date) - timedelta(days=1)
    sorted_weeklies = sorted(month_weeklies, key=_note_timestamp, reverse=True)

    tag_counts: dict[str, int] = {}
    for entry in month_weeklies:
        for tag in _note_tags(entry):
            tag_counts[tag] = tag_counts.get(tag, 0) + 1
    top_tags = [
        tag
        for tag, _ in sorted(tag_counts.items(), key=lambda kv: (kv[1], kv[0]), reverse=True)[:MAX_WEEKLY_TAGS]
    ]

    lines = [
        "## Summary",
        (
            f"Monthly synthesis for {month_start_date.strftime('%Y-%m')} "
            f"from {len(month_weeklies)} weekly synthesis notes."
        ),
        "",
        "### Recurring themes",
    ]
    if top_tags:
        for tag in top_tags:
            lines.append(f"- {tag} ({tag_counts.get(tag, 0)} weeks)")
    else:
        lines.append("- No recurring themes detected")

    lines.extend(["", "### Weekly highlights"])
    for weekly in sorted_weeklies[:MAX_MONTHLY_WEEKS]:
        period = str(weekly.get("period_start", "")).strip()[:10]
        period_label = period if period else _note_timestamp(weekly)[:10]
        lines.append(f"- Week of {period_label}: {_note_summary(weekly)}")

    baseline = sorted_weeklies[: min(8, len(sorted_weeklies))]
    avg_salience = (
        sum(max(0.0, _note_salience(entry)) for entry in baseline) / float(len(baseline))
        if baseline
        else 0.25
    )

    return {
        "ts": _period_end_iso(month_end_date),
        "first_ts": _period_end_iso(month_start_date),
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


def _create_missing_monthly_syntheses(entries: list[dict], now: datetime) -> int:
    existing = _load_existing_periods(MONTHLY_SYNTHESIS_PATH, "monthly")
    current_month = _month_start(now.date())

    by_month: dict[date, list[dict]] = {}
    for entry in entries:
        if str(entry.get("synthesis_level", "")).strip().lower() != "weekly":
            continue
        period_start = str(entry.get("period_start", "")).strip()
        dt = _parse_iso_datetime(period_start)
        if not dt:
            dt = _note_datetime(entry)
        if not dt:
            continue
        month_start_date = _month_start(dt.date())
        if month_start_date >= current_month:
            continue
        by_month.setdefault(month_start_date, []).append(entry)

    if not by_month:
        return 0

    generated_at = _utc_now_iso()
    new_entries = []
    for month_start_date in sorted(by_month):
        period_key = month_start_date.isoformat()
        if period_key in existing:
            continue
        built = _build_monthly_synthesis_entry(month_start_date, by_month[month_start_date], generated_at)
        if built:
            new_entries.append(built)

    _append_jsonl_entries(MONTHLY_SYNTHESIS_PATH, new_entries)
    return len(new_entries)


def _run_hierarchical_consolidation(notes_dir: Path, entries: list[dict]) -> list[dict]:
    """Run periodic note consolidation: archive + weekly/monthly synthesis."""
    now = datetime.now(timezone.utc)
    state = _load_note_maintenance_state()
    last_run = _parse_iso_datetime(state.get("last_run", ""))
    if last_run and (now - last_run) < timedelta(hours=MAINTENANCE_INTERVAL_HOURS):
        return entries

    archived = 0
    weekly_created = 0
    monthly_created = 0
    try:
        archived = _archive_low_salience_notes(notes_dir, now)
        entries = _load_all_notes(notes_dir)
        weekly_created = _create_missing_weekly_syntheses(entries, now)
        if weekly_created:
            entries = _load_all_notes(notes_dir)
        monthly_created = _create_missing_monthly_syntheses(entries, now)
        if monthly_created:
            entries = _load_all_notes(notes_dir)
    finally:
        _save_note_maintenance_state(
            {
                "last_run": _utc_now_iso(),
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


def _load_all_notes(notes_dir: Path) -> list[dict]:
    """Load all note entries from JSONL files in the notes directory."""
    entries = []
    for jsonl_file in notes_dir.glob("*.jsonl"):
        try:
            with open(jsonl_file) as f:
                for line in f:
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


def _select_notes(entries: list[dict]) -> list[tuple[float, dict]]:
    """Select notes with recency ceiling: always include the N most recent,
    then fill remaining slots by salience score."""
    if not entries:
        return []

    usage_data = _load_note_usage()
    usage_notes = usage_data.get("notes", {})

    # Sort by timestamp descending to find most recent
    by_recency = sorted(entries, key=lambda e: _note_timestamp(e), reverse=True)

    # Always include the RECENCY_CEILING most recent notes
    recent = by_recency[:RECENCY_CEILING]
    recent_sessions = {e.get("session", "") for e in recent}

    # Score all remaining notes by salience
    remaining = [e for e in entries if e.get("session", "") not in recent_sessions]
    scored_remaining = [(_effective_salience(e, usage_notes), e) for e in remaining]
    scored_remaining.sort(key=lambda x: x[0], reverse=True)

    # Fill remaining budget with highest-salience notes
    budget = MAX_SALIENT_NOTES - len(recent)
    top_by_salience = scored_remaining[:budget]

    # Combine: recent notes (scored) + salience notes
    result = [(_effective_salience(e, usage_notes), e) for e in recent]
    result.extend(top_by_salience)

    # Sort final list by salience descending for display
    result.sort(key=lambda x: x[0], reverse=True)
    _record_loaded_notes([entry for _, entry in result], usage_data)
    return result


def _format_notes(scored: list[tuple[float, dict]]) -> str:
    """Format selected notes as compact references."""
    parts = []
    for score, entry in scored:
        tags = entry.get("topic_tags", [])
        tag_str = ", ".join(tags) if tags else "untagged"
        raw_anti = entry.get("should_not_try", [])
        anti = []
        if isinstance(raw_anti, list):
            anti = [str(x).strip() for x in raw_anti if str(x).strip()]
        anti_str = f" avoid:{'; '.join(anti[:3])}" if anti else ""
        ts = entry.get("first_ts", entry.get("ts", ""))[:10]
        sid = entry.get("session", "")[:8]
        parts.append(f"  {ts} [{tag_str}] salience:{score:.2f} session:{sid}{anti_str}")
    return "\n".join(parts)


def _note_summary(entry: dict) -> str:
    text = _note_text(entry)
    for line in text.splitlines():
        stripped = line.strip().lstrip("#").strip()
        if stripped and stripped.lower() != "summary":
            return stripped
    return "No summary"


def _extract_open_threads(entries: list[dict]) -> list[str]:
    threads = []
    seen = set()
    for entry in entries:
        text = _note_text(entry)
        for line in text.splitlines():
            cleaned = line.strip().lstrip("-*").strip()
            if not cleaned:
                continue
            if not _ACTION_CUE_RE.search(cleaned):
                continue
            key = cleaned.lower()
            if key in seen:
                continue
            seen.add(key)
            threads.append(cleaned)
            if len(threads) >= 6:
                return threads
    return threads


def _generate_now_markdown(entries: list[dict]) -> str:
    """Create a deterministic rolling now.md from recent+salient notes."""
    now_iso = _utc_now_iso()

    by_recency = sorted(entries, key=_note_timestamp, reverse=True)
    highlights = by_recency[:6]

    tag_counts: dict[str, int] = {}
    for entry in entries:
        tags = entry.get("topic_tags", [])
        if not isinstance(tags, list):
            continue
        for tag in tags:
            t = str(tag).strip()
            if t:
                tag_counts[t] = tag_counts.get(t, 0) + 1

    top_tags = sorted(tag_counts.items(), key=lambda kv: kv[1], reverse=True)[:6]
    open_threads = _extract_open_threads(entries)

    lines = [
        "# Working Memory",
        "",
        AUTO_NOW_MARKER,
        "",
        f"_Auto-updated from session notes on {now_iso}_",
        "",
        "## Active Themes",
        "",
    ]

    if top_tags:
        for tag, count in top_tags:
            lines.append(f"- {tag} ({count})")
    else:
        lines.append("- No clear themes yet")

    lines.extend(["", "## Recent Session Highlights", ""])
    if highlights:
        for entry in highlights:
            ts = _note_timestamp(entry)[:10]
            summary = _note_summary(entry)
            sid = str(entry.get("session", "")).strip()[:8]
            sid_suffix = f" [{sid}]" if sid else ""
            lines.append(f"- {ts}{sid_suffix}: {summary}")
    else:
        lines.append("- No recent highlights yet")

    lines.extend(["", "## Open Threads", ""])
    if open_threads:
        for item in open_threads:
            lines.append(f"- {item}")
    else:
        lines.append("- No explicit open threads detected")

    return "\n".join(lines).strip() + "\n"


def _maybe_update_now_md(selected_entries: list[dict]):
    """Auto-update now.md only if missing or previously auto-managed."""
    try:
        SEEDS_DIR.mkdir(parents=True, exist_ok=True)
        now_path = SEEDS_DIR / "now.md"
        if now_path.exists():
            existing = now_path.read_text(encoding="utf-8")
            if AUTO_NOW_MARKER not in existing:
                return

        content = _generate_now_markdown(selected_entries)
        now_path.write_text(content, encoding="utf-8")
    except Exception:
        pass


def main():
    try:
        # Read stdin (hook input)
        try:
            json.loads(sys.stdin.read())
        except (json.JSONDecodeError, EOFError):
            pass

        is_compact = "--compact" in sys.argv
        config = load_config()
        files = collect_files(config)

        if not files:
            return

        if is_compact:
            print("[Memorable] Context recovery after compaction. Read these files:\n")
        else:
            print("[Memorable] BEFORE RESPONDING, read these files in order:\n")

        for i, path in enumerate(files, 1):
            print(f"{i}. Read {path}")

        print("\nDo NOT skip this. Do NOT respond before reading these files.")

        # Add session notes with recency ceiling
        notes_dir = BASE_DIR / "data" / "notes"
        if notes_dir.exists():
            entries = _load_all_notes(notes_dir)
            if entries:
                entries = _run_hierarchical_consolidation(notes_dir, entries)
                selected = _select_notes(entries)
                if selected:
                    _maybe_update_now_md([entry for _, entry in selected])
                    formatted = _format_notes(selected)
                    print(f"\n[Memorable] Most salient session notes ({len(entries)} total in {notes_dir}/):")
                    print(formatted)
                    print(f"To read a note: grep {notes_dir}/ for its session ID. To search by topic: grep by keyword.")

        # Surface memorable_search tool
        print("\n[Memorable] To search past sessions and observations, use the `memorable_search` MCP tool or the /memorable-search skill.")
        print("Use this when the user references past conversations, asks \"do you remember...\", or when you need historical context.")

    except Exception as e:
        log_path = BASE_DIR / "hook-errors.log"
        try:
            import time
            with open(log_path, "a") as f:
                f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] session_start: {e}\n")
        except Exception:
            pass


if __name__ == "__main__":
    main()
