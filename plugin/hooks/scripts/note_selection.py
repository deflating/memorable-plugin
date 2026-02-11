#!/usr/bin/env python3
"""Note selection and salience scoring helpers for Memorable hooks."""

import hashlib
import json
import platform
import re
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path.home() / ".memorable"
DATA_DIR = BASE_DIR / "data"
NOTE_USAGE_PATH = DATA_DIR / "note_usage.json"
CURRENT_LOADED_NOTES_PATH = DATA_DIR / "current_loaded_notes.json"

DECAY_FACTOR = 0.97
MIN_SALIENCE = 0.05
MAX_SALIENT_NOTES = 8
RECENCY_CEILING = 3
PINNED_SALIENCE_BOOST = 0.8
CURRENT_MACHINE = platform.node().split(".")[0].strip().lower()

_WORD_RE = re.compile(r"[A-Za-z0-9_']+")
_BULLET_RE = re.compile(r"^\s*[-*]\s+", re.MULTILINE)
_ACTION_CUE_RE = re.compile(
    r"\b(todo|next step|next steps|action(?:s| items?)?|follow[- ]?up|"
    r"decide|decision|blocked|blocker|unblock|deadline|ship|fix|implement|resolve)\b",
    re.IGNORECASE,
)


def parse_float(value, fallback: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


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


def note_timestamp(entry: dict) -> str:
    return entry.get("first_ts", entry.get("ts", ""))


def note_datetime(entry: dict) -> datetime | None:
    return parse_iso_datetime(note_timestamp(entry))


def note_text(entry: dict) -> str:
    text = entry.get("note", "")
    return text if isinstance(text, str) else str(text)


def clean_note_tags(value) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(tag).strip() for tag in value if str(tag).strip()]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def entry_emotional_weight(entry: dict) -> float:
    weight = parse_float(entry.get("emotional_weight", 0.3), 0.3)
    return max(0.0, min(1.0, weight))


def entry_age_days(entry: dict) -> float:
    last_ref = entry.get("last_referenced", entry.get("ts", ""))
    dt = parse_iso_datetime(last_ref)
    if not dt:
        return 30.0
    return (datetime.now(timezone.utc) - dt).total_seconds() / 86400


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


def note_key(entry: dict) -> str:
    session = str(entry.get("session", "")).strip()
    ts = note_timestamp(entry)
    if session:
        return f"{session}|{ts}"
    digest = hashlib.sha1(note_text(entry).encode("utf-8")).hexdigest()[:12]
    return f"{ts}|{digest}"


def load_note_usage() -> dict:
    try:
        if NOTE_USAGE_PATH.exists():
            data = json.loads(NOTE_USAGE_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict) and isinstance(data.get("notes"), dict):
                return data
    except Exception:
        pass
    return {"notes": {}}


def save_note_usage(data: dict):
    try:
        NOTE_USAGE_PATH.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception:
        pass


def reference_effectiveness_multiplier(entry: dict, usage_notes: dict) -> float:
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
    return 0.85 + (0.4 * ratio)


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


def effective_salience(entry: dict, usage_notes: dict | None = None) -> float:
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
