#!/usr/bin/env python3
"""Build a semantic knowledge seed from recurring episodic notes."""

import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from note_constants import DATA_DIR
from note_utils import is_synthesis_entry, note_datetime, note_salience, note_tags, week_start

KNOWLEDGE_PATH = DATA_DIR / "seeds" / "knowledge.md"
KNOWLEDGE_WINDOW_WEEKS = 4
KNOWLEDGE_MIN_STABILITY_WEEKS = 2
KNOWLEDGE_MAX_FACTS = 30
TARGET_SECTIONS = {"decisions", "user preferences", "technical context"}
NEGATION_TOKENS = {"not", "never", "no", "dont", "don't", "avoid", "avoids"}
_SECTION_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
_BULLET_RE = re.compile(r"^\s*[-*]\s+")
_WORD_RE = re.compile(r"[A-Za-z0-9']+")


def _coerce_note_text(entry: dict) -> str:
    text = entry.get("note", "")
    return text if isinstance(text, str) else str(text)


def _split_sections(text: str) -> dict[str, str]:
    sections: dict[str, list[str]] = {}
    current = ""
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        match = _SECTION_RE.match(line)
        if match:
            current = match.group(1).strip().lower()
            sections.setdefault(current, [])
            continue
        if current:
            sections[current].append(line)
    return {name: "\n".join(lines).strip() for name, lines in sections.items() if lines}


def _fact_lines(section_text: str) -> list[str]:
    candidates: list[str] = []
    for raw_line in section_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        line = _BULLET_RE.sub("", line).strip()
        if line.startswith("##"):
            continue
        if len(line) < 24 or len(line) > 220:
            continue
        lowered = line.lower()
        if lowered in {"summary", "technical context", "decisions", "user preferences"}:
            continue
        candidates.append(line)
    return candidates


def _normalize_fact_key(text: str) -> str:
    lowered = text.lower().strip()
    lowered = re.sub(r"[^a-z0-9\s]", " ", lowered)
    lowered = re.sub(r"\s+", " ", lowered).strip()
    return lowered


def _fact_signature(text: str) -> str:
    tokens = [tok for tok in _WORD_RE.findall(text.lower()) if tok not in NEGATION_TOKENS]
    return " ".join(tokens)


def _fact_sort_key(fact: dict):
    return (
        fact["stability_weeks"],
        fact["mentions"],
        fact["salience_total"],
        fact["last_seen_ts"],
    )


def extract_stable_facts(entries: list[dict], now: datetime) -> list[dict]:
    now = now.astimezone(timezone.utc)
    first_week = week_start((now - timedelta(weeks=KNOWLEDGE_WINDOW_WEEKS - 1)).date())
    facts: dict[str, dict] = {}

    for entry in entries:
        if is_synthesis_entry(entry) or bool(entry.get("archived", False)):
            continue
        dt = note_datetime(entry)
        if not dt:
            continue
        entry_week = week_start(dt.date())
        if entry_week < first_week:
            continue

        sections = _split_sections(_coerce_note_text(entry))
        source_lines: list[str] = []
        for section_name in TARGET_SECTIONS:
            source_lines.extend(_fact_lines(sections.get(section_name, "")))
        if not source_lines:
            source_lines.extend(_fact_lines(sections.get("summary", "")))

        tags = note_tags(entry)
        salience = max(0.0, note_salience(entry))
        for line in source_lines:
            key = _normalize_fact_key(line)
            if not key:
                continue
            fact = facts.setdefault(
                key,
                {
                    "text": line,
                    "weeks": set(),
                    "mentions": 0,
                    "salience_total": 0.0,
                    "tags": {},
                    "last_seen_ts": "",
                },
            )
            fact["weeks"].add(entry_week.isoformat())
            fact["mentions"] += 1
            fact["salience_total"] += salience
            fact["last_seen_ts"] = max(str(fact["last_seen_ts"]), dt.isoformat())
            if len(line) < len(fact["text"]):
                fact["text"] = line
            for tag in tags:
                fact["tags"][tag] = fact["tags"].get(tag, 0) + 1

    stable: list[dict] = []
    for fact in facts.values():
        weeks = len(fact["weeks"])
        if weeks < KNOWLEDGE_MIN_STABILITY_WEEKS:
            continue
        dominant_tag = "general"
        if fact["tags"]:
            dominant_tag = sorted(
                fact["tags"].items(),
                key=lambda item: (item[1], item[0]),
                reverse=True,
            )[0][0]
        stable.append(
            {
                "text": fact["text"],
                "stability_weeks": weeks,
                "mentions": fact["mentions"],
                "salience_total": round(fact["salience_total"], 3),
                "dominant_tag": dominant_tag,
                "last_seen_ts": fact["last_seen_ts"],
                "signature": _fact_signature(fact["text"]),
            }
        )

    # Keep only the strongest fact per semantic signature to avoid stale contradictions.
    by_signature: dict[str, dict] = {}
    for fact in stable:
        signature = fact["signature"] or _normalize_fact_key(fact["text"])
        current = by_signature.get(signature)
        if current is None or _fact_sort_key(fact) > _fact_sort_key(current):
            by_signature[signature] = fact

    deduped = list(by_signature.values())
    deduped.sort(key=_fact_sort_key, reverse=True)
    return deduped[:KNOWLEDGE_MAX_FACTS]


def render_knowledge_markdown(facts: list[dict], generated_at: datetime) -> str:
    date_label = generated_at.astimezone(timezone.utc).date().isoformat()
    lines = [
        "# Semantic Knowledge",
        "",
        f"_Auto-updated from recurring session patterns on {date_label}_",
    ]
    if not facts:
        lines.extend(
            [
                "",
                "No stable knowledge has graduated yet. Keep capturing sessions and this file will fill over time.",
            ]
        )
        return "\n".join(lines).strip() + "\n"

    grouped: dict[str, list[dict]] = {}
    for fact in facts:
        grouped.setdefault(fact.get("dominant_tag", "general"), []).append(fact)

    tag_order = sorted(grouped.keys(), key=lambda tag: (-len(grouped[tag]), tag))
    for tag in tag_order:
        lines.extend(["", f"## {tag}"])
        for fact in grouped[tag]:
            lines.append(
                f"- {fact['text']} _(seen {fact['stability_weeks']} weeks)_"
            )
    return "\n".join(lines).strip() + "\n"


def _atomic_write(path: Path, content: str):
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(content, encoding="utf-8")
    tmp_path.rename(path)


def update_knowledge_seed(
    entries: list[dict],
    now: datetime,
    knowledge_path: Path = KNOWLEDGE_PATH,
) -> int:
    facts = extract_stable_facts(entries, now)
    content = render_knowledge_markdown(facts, now)
    try:
        knowledge_path.parent.mkdir(parents=True, exist_ok=True)
        previous = ""
        if knowledge_path.exists():
            previous = knowledge_path.read_text(encoding="utf-8")
        if previous != content:
            _atomic_write(knowledge_path, content)
    except OSError:
        return 0
    return len(facts)

