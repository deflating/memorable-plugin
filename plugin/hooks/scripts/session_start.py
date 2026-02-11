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


def apply_anchor_marker(
    match: re.Match,
    anchored_text: str,
    max_depth: int,
    result: list[str],
    depth_stack: list[int],
    pos: int,
) -> int:
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
        return end
    if depth_stack and depth_stack[-1] <= max_depth:
        result.append(anchored_text[pos:start])
    if depth_stack:
        depth_stack.pop()
    return end


def append_trailing_extracted_text(
    anchored_text: str,
    max_depth: int,
    result: list[str],
    depth_stack: list[int],
    pos: int,
):
    if depth_stack and depth_stack[-1] <= max_depth:
        result.append(anchored_text[pos:])
        return
    if not depth_stack:
        trailing = anchored_text[pos:].strip()
        if trailing:
            result.append(trailing)


def compact_extracted_text(parts: list[str]) -> str:
    text = "".join(parts).strip()
    text = re.sub(r" {2,}", " ", text)
    return re.sub(r"\n{3,}", "\n\n", text)


def extract_at_depth(anchored_text: str, max_depth: int) -> str:
    """Extract content from anchored text up to max_depth, stripping markers."""
    if max_depth < 0:
        return anchored_text
    result = []
    pos = 0
    depth_stack = []
    for match in _ANCHOR_RE.finditer(anchored_text):
        pos = apply_anchor_marker(match, anchored_text, max_depth, result, depth_stack, pos)
    append_trailing_extracted_text(anchored_text, max_depth, result, depth_stack, pos)
    return compact_extracted_text(result)


def prepare_context_file(filename: str, depth: int) -> str | None:
    safe_filename = sanitize_filename(filename)
    if not safe_filename:
        return None
    raw_path = FILES_DIR / safe_filename
    anchored_path = FILES_DIR / f"{safe_filename}.anchored"
    if anchored_path.is_file() and depth >= 0:
        anchored_text = anchored_path.read_text(encoding="utf-8")
        extracted = extract_at_depth(anchored_text, depth)
        cache_path = FILES_DIR / f".cache-{safe_filename}-depth{depth}.md"
        cache_path.write_text(extracted, encoding="utf-8")
        return str(cache_path)
    if raw_path.is_file():
        return str(raw_path)
    return None


def core_seed_paths() -> list[str]:
    paths = []
    for name in ("user.md", "agent.md", "now.md"):
        path = SEEDS_DIR / name
        if path.is_file():
            paths.append(str(path))
    return paths


def resolve_context_entry_path(entry: dict, existing_paths: set[str]) -> str | None:
    if not entry.get("enabled", True):
        return None
    filename = sanitize_filename(entry.get("filename", ""))
    if not filename:
        return None
    seed_path = SEEDS_DIR / filename
    if seed_path.is_file() and str(seed_path) in existing_paths:
        return None
    prepared = prepare_context_file(filename, entry.get("depth", -1))
    if prepared:
        return prepared
    if seed_path.is_file():
        return str(seed_path)
    return None


def collect_files(config: dict) -> list[str]:
    paths = core_seed_paths()
    seen = set(paths)
    for entry in config.get("context_files", []):
        resolved = resolve_context_entry_path(entry, seen)
        if not resolved:
            continue
        paths.append(resolved)
        seen.add(resolved)
    return paths


def parse_float(value, fallback: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def entry_emotional_weight(entry: dict) -> float:
    weight = parse_float(entry.get("emotional_weight", 0.3), 0.3)
    return max(0.0, min(1.0, weight))


def entry_age_days(entry: dict) -> float:
    last_ref = entry.get("last_referenced", entry.get("ts", ""))
    dt = parse_iso_datetime(last_ref)
    if not dt:
        return 30.0
    return (datetime.now(timezone.utc) - dt).total_seconds() / 86400


def effective_salience(entry: dict, usage_notes: dict | None = None) -> float:
    """Calculate effective salience with decay + density + actionability."""
    if bool(entry.get("archived", False)):
        return MIN_SALIENCE
    salience = parse_float(entry.get("salience", 1.0), 1.0)
    emotional_weight = entry_emotional_weight(entry)
    days = entry_age_days(entry)
    adjusted_days = days * (1.0 - emotional_weight * 0.5)
    decayed = salience * (DECAY_FACTOR ** adjusted_days)
    if bool(entry.get("pinned", False)):
        decayed += PINNED_SALIENCE_BOOST
    base = max(MIN_SALIENCE, decayed)
    density_mult = information_density_multiplier(entry)
    actionability_mult = actionability_multiplier(entry)
    context_mult = time_machine_context_multiplier(entry)
    reference_mult = reference_effectiveness_multiplier(entry, usage_notes or {})
    return max(
        MIN_SALIENCE,
        base * density_mult * actionability_mult * context_mult * reference_mult,
    )


def note_text(entry: dict) -> str:
    text = entry.get("note", "")
    return text if isinstance(text, str) else str(text)


def information_density_multiplier(entry: dict) -> float:
    text = note_text(entry).strip()
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
    token_penalty = 0.0
    if est_tokens > 450:
        token_penalty = min(0.25, (est_tokens - 450) / 2200)
    score = (0.55 * lexical_score) + (0.45 * density_score) - token_penalty
    score = max(0.0, min(1.0, score))
    return 0.8 + (0.5 * score)


def actionability_multiplier(entry: dict) -> float:
    """Boost notes with clear next actions, blockers, or explicit action items."""
    text = note_text(entry)
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


def time_machine_context_multiplier(entry: dict) -> float:
    now = datetime.now(timezone.utc)
    dt = parse_iso_datetime(note_timestamp(entry))
    hour_boost = 0.0
    if dt:
        note_hour = dt.astimezone(timezone.utc).hour
        now_hour = now.hour
        delta = min((now_hour - note_hour) % 24, (note_hour - now_hour) % 24)
        closeness = max(0.0, (6.0 - float(delta)) / 6.0)
        hour_boost = 0.15 * closeness
    machine_boost = 0.0
    raw_machine = str(entry.get("machine", "")).strip().lower()
    if raw_machine and CURRENT_MACHINE:
        note_machine = raw_machine.split(".")[0]
        if note_machine == CURRENT_MACHINE:
            machine_boost = 0.12
    return 0.95 + hour_boost + machine_boost


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def note_key(entry: dict) -> str:
    """Stable key used for tracking load/reference effectiveness."""
    session = str(entry.get("session", "")).strip()
    ts = note_timestamp(entry)
    if session:
        return f"{session}|{ts}"
    digest = hashlib.sha1(note_text(entry).encode("utf-8")).hexdigest()[:12]
    return f"{ts}|{digest}"


def load_note_usage() -> dict:
    """Load note usage counters from disk."""
    try:
        if NOTE_USAGE_PATH.exists():
            data = json.loads(NOTE_USAGE_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict) and isinstance(data.get("notes"), dict):
                return data
    except Exception:
        pass
    return {"notes": {}}


def save_note_usage(data: dict):
    """Persist note usage counters to disk (best effort)."""
    try:
        NOTE_USAGE_PATH.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception:
        pass


def reference_effectiveness_multiplier(entry: dict, usage_notes: dict) -> float:
    """Boost notes that are consistently referenced after being loaded."""
    rec = usage_notes.get(note_key(entry))
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


def clean_note_tags(value) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(tag).strip() for tag in value if str(tag).strip()]


def track_loaded_note(usage_notes: dict, entry: dict, now_iso: str) -> dict:
    key = note_key(entry)
    session = str(entry.get("session", "")).strip()
    tags = clean_note_tags(entry.get("topic_tags", []))
    rec = usage_notes.setdefault(
        key,
        {"loaded_count": 0, "referenced_count": 0, "first_loaded": now_iso},
    )
    rec["loaded_count"] = int(rec.get("loaded_count", 0)) + 1
    rec["last_loaded"] = now_iso
    rec["session"] = session
    rec["session_short"] = session[:8]
    rec["tags"] = tags
    rec["timestamp"] = note_timestamp(entry)
    return {"key": key, "session": session, "session_short": session[:8], "tags": tags}


def write_current_loaded_notes(now_iso: str, by_key: dict):
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


def record_loaded_notes(selected_entries: list[dict], usage_data: dict):
    usage_notes = usage_data.setdefault("notes", {})
    now_iso = utc_now_iso()
    by_key = {}
    for entry in selected_entries:
        note_meta = track_loaded_note(usage_notes, entry, now_iso)
        by_key[note_meta["key"]] = note_meta
    save_note_usage(usage_data)
    write_current_loaded_notes(now_iso, by_key)


def note_timestamp(entry: dict) -> str:
    """Get the best timestamp for recency sorting."""
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


def should_archive_entry(entry: dict, cutoff: datetime) -> bool:
    if is_synthesis_entry(entry):
        return False
    if note_salience(entry) >= ARCHIVE_MIN_SALIENCE:
        return False
    dt = note_datetime(entry)
    if not dt:
        return False
    return dt < cutoff


def archive_source_files(notes_dir: Path):
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


def restore_archived_source(jsonl_file: Path, original_lines: list[str], tmp_path: Path, rollback_path: Path):
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


def persist_archived_lines(jsonl_file: Path, archive_dir: Path, keep_lines: list[str], archive_lines: list[str]):
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
            keep_lines, archive_lines, original_lines = partition_archive_lines(jsonl_file, cutoff)
        except OSError:
            continue
        if not archive_lines:
            continue
        try:
            persist_archived_lines(jsonl_file, archive_dir, keep_lines, archive_lines)
            archived_count += len(archive_lines)
        except OSError:
            tmp_path = jsonl_file.with_suffix(jsonl_file.suffix + ".tmp")
            rollback_path = jsonl_file.with_suffix(jsonl_file.suffix + ".rollback.tmp")
            restore_archived_source(jsonl_file, original_lines, tmp_path, rollback_path)
    return archived_count


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


def ranked_tags(tag_buckets: dict[str, list[dict]], tag_scores: dict[str, float], limit: int) -> list[str]:
    ranked = sorted(
        tag_scores.items(),
        key=lambda kv: (kv[1], len(tag_buckets.get(kv[0], []))),
        reverse=True,
    )[:limit]
    return [tag for tag, _ in ranked]


def weekly_theme_lines(top_tags: list[str], tag_buckets: dict[str, list[dict]]) -> list[str]:
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


def bounded_average_salience(entries: list[dict], window: int, fallback: float) -> float:
    baseline = entries[: min(window, len(entries))]
    if not baseline:
        return fallback
    total = sum(max(0.0, note_salience(entry)) for entry in baseline)
    return total / float(len(baseline))


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
    return weekly_synthesis_payload(week_start_date, week_end_date, week_entries, lines, top_tags, avg_salience, generated_at)


def weekly_entries_by_period(entries: list[dict], current_week: date) -> dict[date, list[dict]]:
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


def monthly_entries_by_period(entries: list[dict], current_month: date) -> dict[date, list[dict]]:
    grouped: dict[date, list[dict]] = {}
    for entry in entries:
        if str(entry.get("synthesis_level", "")).strip().lower() != "weekly":
            continue
        dt = parse_iso_datetime(str(entry.get("period_start", "")).strip()) or note_datetime(entry)
        if not dt:
            continue
        start = month_start(dt.date())
        if start < current_month:
            grouped.setdefault(start, []).append(entry)
    return grouped


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


def create_missing_weekly_syntheses(entries: list[dict], now: datetime) -> int:
    existing = load_existing_periods(WEEKLY_SYNTHESIS_PATH, "weekly")
    current_week = week_start(now.date())
    by_week = weekly_entries_by_period(entries, current_week)
    if not by_week:
        return 0
    generated_at = utc_now_iso()
    new_entries = build_missing_synthesis_entries(by_week, existing, build_weekly_synthesis_entry, generated_at)
    append_jsonl_entries(WEEKLY_SYNTHESIS_PATH, new_entries)
    return len(new_entries)


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
    return monthly_synthesis_payload(month_start_date, month_end_date, month_weeklies, lines, top_tags, avg_salience, generated_at)


def create_missing_monthly_syntheses(entries: list[dict], now: datetime) -> int:
    existing = load_existing_periods(MONTHLY_SYNTHESIS_PATH, "monthly")
    current_month = month_start(now.date())
    by_month = monthly_entries_by_period(entries, current_month)
    if not by_month:
        return 0
    generated_at = utc_now_iso()
    new_entries = build_missing_synthesis_entries(by_month, existing, build_monthly_synthesis_entry, generated_at)
    append_jsonl_entries(MONTHLY_SYNTHESIS_PATH, new_entries)
    return len(new_entries)


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
    """Run periodic note consolidation: archive + weekly/monthly synthesis."""
    now = datetime.now(timezone.utc)
    state = load_note_maintenance_state()
    last_run = parse_iso_datetime(state.get("last_run", ""))
    if last_run and (now - last_run) < timedelta(hours=MAINTENANCE_INTERVAL_HOURS):
        return entries

    archived = weekly_created = monthly_created = 0
    try:
        entries, archived, weekly_created, monthly_created = run_maintenance_cycle(notes_dir, entries, now)
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


def load_all_notes(notes_dir: Path) -> list[dict]:
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


def split_recent_and_remaining(entries: list[dict]):
    by_recency = sorted(entries, key=lambda entry: note_timestamp(entry), reverse=True)
    recent = by_recency[:RECENCY_CEILING]
    recent_sessions = {entry.get("session", "") for entry in recent}
    remaining = [entry for entry in entries if entry.get("session", "") not in recent_sessions]
    return recent, remaining


def score_entries(entries: list[dict], usage_notes: dict) -> list[tuple[float, dict]]:
    scored = [(effective_salience(entry, usage_notes), entry) for entry in entries]
    scored.sort(key=lambda item: item[0], reverse=True)
    return scored


def select_notes(entries: list[dict]) -> list[tuple[float, dict]]:
    """Select notes with recency ceiling: always include the N most recent,
    then fill remaining slots by salience score."""
    if not entries:
        return []
    usage_data = load_note_usage()
    usage_notes = usage_data.get("notes", {})
    recent, remaining = split_recent_and_remaining(entries)
    scored_remaining = score_entries(remaining, usage_notes)
    budget = MAX_SALIENT_NOTES - len(recent)
    top_by_salience = scored_remaining[:budget]
    result = score_entries(recent, usage_notes)
    result.extend(top_by_salience)
    result.sort(key=lambda item: item[0], reverse=True)
    record_loaded_notes([entry for _, entry in result], usage_data)
    return result


def format_notes(scored: list[tuple[float, dict]]) -> str:
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


def note_summary(entry: dict) -> str:
    text = note_text(entry)
    for line in text.splitlines():
        stripped = line.strip().lstrip("#").strip()
        if stripped and stripped.lower() != "summary":
            return stripped
    return "No summary"


def extract_open_threads(entries: list[dict]) -> list[str]:
    threads = []
    seen = set()
    for entry in entries:
        text = note_text(entry)
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


def theme_counts(entries: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for entry in entries:
        for tag in clean_note_tags(entry.get("topic_tags", [])):
            counts[tag] = counts.get(tag, 0) + 1
    return counts


def theme_section_lines(top_tags: list[tuple[str, int]]) -> list[str]:
    if not top_tags:
        return ["- No clear themes yet"]
    return [f"- {tag} ({count})" for tag, count in top_tags]


def recent_highlight_lines(highlights: list[dict]) -> list[str]:
    if not highlights:
        return ["- No recent highlights yet"]
    lines: list[str] = []
    for entry in highlights:
        ts = note_timestamp(entry)[:10]
        summary = note_summary(entry)
        sid = str(entry.get("session", "")).strip()[:8]
        sid_suffix = f" [{sid}]" if sid else ""
        lines.append(f"- {ts}{sid_suffix}: {summary}")
    return lines


def open_thread_lines(open_threads: list[str]) -> list[str]:
    if not open_threads:
        return ["- No explicit open threads detected"]
    return [f"- {item}" for item in open_threads]


def generate_now_markdown(entries: list[dict]) -> str:
    """Create a deterministic rolling now.md from recent+salient notes."""
    now_iso = utc_now_iso()
    by_recency = sorted(entries, key=note_timestamp, reverse=True)
    highlights = by_recency[:6]
    tag_counts = theme_counts(entries)
    top_tags = sorted(tag_counts.items(), key=lambda kv: kv[1], reverse=True)[:6]
    open_threads = extract_open_threads(entries)
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
    lines.extend(theme_section_lines(top_tags))
    lines.extend(["", "## Recent Session Highlights", ""])
    lines.extend(recent_highlight_lines(highlights))
    lines.extend(["", "## Open Threads", ""])
    lines.extend(open_thread_lines(open_threads))
    return "\n".join(lines).strip() + "\n"


def maybe_update_now_md(selected_entries: list[dict]):
    try:
        SEEDS_DIR.mkdir(parents=True, exist_ok=True)
        now_path = SEEDS_DIR / "now.md"
        if now_path.exists():
            existing = now_path.read_text(encoding="utf-8")
            if AUTO_NOW_MARKER not in existing:
                return

        content = generate_now_markdown(selected_entries)
        now_path.write_text(content, encoding="utf-8")
    except Exception:
        pass


def consume_hook_input():
    try:
        json.loads(sys.stdin.read())
    except (json.JSONDecodeError, EOFError):
        return


def print_context_instructions(files: list[str], is_compact: bool):
    header = "[Memorable] Context recovery after compaction. Read these files:\n"
    if not is_compact:
        header = "[Memorable] BEFORE RESPONDING, read these files in order:\n"
    print(header)
    for i, path in enumerate(files, 1):
        print(f"{i}. Read {path}")
    print("\nDo NOT skip this. Do NOT respond before reading these files.")


def print_selected_notes_section():
    notes_dir = BASE_DIR / "data" / "notes"
    if not notes_dir.exists():
        return
    entries = load_all_notes(notes_dir)
    if not entries:
        return
    entries = run_hierarchical_consolidation(notes_dir, entries)
    selected = select_notes(entries)
    if not selected:
        return
    maybe_update_now_md([entry for _, entry in selected])
    formatted = format_notes(selected)
    print(f"\n[Memorable] Most salient session notes ({len(entries)} total in {notes_dir}/):")
    print(formatted)
    print(f"To read a note: grep {notes_dir}/ for its session ID. To search by topic: grep by keyword.")


def print_memorable_search_hint():
    print("\n[Memorable] To search past sessions and observations, use the `memorable_search` MCP tool or the /memorable-search skill.")
    print("Use this when the user references past conversations, asks \"do you remember...\", or when you need historical context.")


def log_session_start_error(error: Exception):
    log_path = BASE_DIR / "hook-errors.log"
    try:
        import time
        with open(log_path, "a") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] session_start: {error}\n")
    except Exception:
        pass


def main():
    try:
        consume_hook_input()
        is_compact = "--compact" in sys.argv
        config = load_config()
        files = collect_files(config)
        if not files:
            return
        print_context_instructions(files, is_compact)
        print_selected_notes_section()
        print_memorable_search_hint()
    except Exception as error:
        log_session_start_error(error)


if __name__ == "__main__":
    main()
