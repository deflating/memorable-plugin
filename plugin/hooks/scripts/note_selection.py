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
DECAY_FACTOR = 0.97
MIN_SALIENCE = 0.05
MAX_SALIENT_NOTES = 8
RECENCY_CEILING = 3
PINNED_SALIENCE_BOOST = 0.8
CURRENT_MACHINE = platform.node().split(".")[0].strip().lower()
TAG_GRAPH_PATH = DATA_DIR / "tag_graph.json"
MAX_ACTIVATION_HOPS = 2
ACTIVATION_DECAY = 0.5
CONTEXT_MIN_MULTIPLIER = 0.8
CONTEXT_MAX_MULTIPLIER = 2.0

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
    cleaned: list[str] = []
    for raw in value:
        tag = normalize_tag(raw)
        if tag:
            cleaned.append(tag)
    return cleaned


def normalize_tag(tag) -> str:
    value = str(tag).strip().lower()
    value = value.replace(" ", "-").replace("_", "-")
    value = re.sub(r"[^a-z0-9-]+", "", value)
    value = re.sub(r"-{2,}", "-", value).strip("-")
    return value


def entry_tags(entry: dict) -> list[str]:
    return clean_note_tags(entry.get("topic_tags", []))


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


def build_tag_cooccurrence_graph(entries: list[dict]) -> dict[str, dict[str, int]]:
    graph: dict[str, dict[str, int]] = {}
    for entry in entries:
        tags = sorted(set(entry_tags(entry)))
        if not tags:
            continue
        for tag in tags:
            graph.setdefault(tag, {})
        for idx, left in enumerate(tags):
            for right in tags[idx + 1:]:
                graph[left][right] = graph[left].get(right, 0) + 1
                graph[right][left] = graph[right].get(left, 0) + 1
    return graph


def cache_tag_graph(graph: dict[str, dict[str, int]], entries_count: int):
    if not DATA_DIR.exists():
        return
    payload = {
        "generated_at": utc_now_iso(),
        "entry_count": entries_count,
        "graph": graph,
    }
    try:
        TAG_GRAPH_PATH.parent.mkdir(parents=True, exist_ok=True)
        TAG_GRAPH_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass


def parse_now_sections(path: Path) -> dict[str, str]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return {}
    sections: dict[str, list[str]] = {}
    heading = ""
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if line.startswith("## "):
            heading = line[3:].strip().lower()
            sections.setdefault(heading, [])
            continue
        if heading:
            sections[heading].append(line)
    return {k: "\n".join(v).strip() for k, v in sections.items() if v}


def infer_seed_tags_from_now(known_tags: set[str]) -> set[str]:
    now_sections = parse_now_sections(DATA_DIR / "seeds" / "now.md")
    focus_text = "\n".join(
        filter(
            None,
            [
                now_sections.get("active focus", ""),
                now_sections.get("open threads", ""),
            ],
        )
    ).lower()
    if not focus_text:
        return set()

    focus_tokens = set(_WORD_RE.findall(focus_text))
    seeded: set[str] = set()
    for tag in known_tags:
        tokens = [tok for tok in tag.split("-") if tok]
        if not tokens:
            continue
        phrase = " ".join(tokens)
        if tag in focus_text or phrase in focus_text:
            seeded.add(tag)
            continue
        if len(tokens) == 1 and tokens[0] in focus_tokens:
            seeded.add(tag)
            continue
        if len(tokens) > 1 and all(tok in focus_tokens for tok in tokens):
            seeded.add(tag)
    return seeded


def recent_session_seed_tags(entries: list[dict]) -> set[str]:
    by_recency = sorted(entries, key=lambda entry: note_timestamp(entry), reverse=True)
    for entry in by_recency:
        tags = entry_tags(entry)
        if tags:
            return set(tags)
    return set()


def spread_tag_activation(
    graph: dict[str, dict[str, int]],
    seed_tags: set[str],
    max_hops: int = MAX_ACTIVATION_HOPS,
    decay: float = ACTIVATION_DECAY,
) -> dict[str, float]:
    if not graph or not seed_tags:
        return {}

    activation: dict[str, float] = {}
    frontier: dict[str, float] = {}
    for tag in seed_tags:
        activation[tag] = 1.0
        frontier[tag] = 1.0

    for _ in range(max_hops):
        next_frontier: dict[str, float] = {}
        for src, weight in frontier.items():
            neighbors = graph.get(src, {})
            if not neighbors:
                continue
            max_weight = max(neighbors.values()) or 1
            for dst, edge_weight in neighbors.items():
                spread = weight * decay * (float(edge_weight) / float(max_weight))
                if spread <= 0.0:
                    continue
                if spread > next_frontier.get(dst, 0.0):
                    next_frontier[dst] = spread
                if spread > activation.get(dst, 0.0):
                    activation[dst] = spread
        frontier = next_frontier
        if not frontier:
            break

    return activation


def build_contextual_usage(entries: list[dict]) -> dict:
    graph = build_tag_cooccurrence_graph(entries)
    if graph:
        cache_tag_graph(graph, len(entries))
    known_tags = set(graph.keys())
    seed_tags = set()
    seed_tags.update(recent_session_seed_tags(entries))
    seed_tags.update(infer_seed_tags_from_now(known_tags))
    activation = spread_tag_activation(graph, seed_tags)
    return {"tag_activation": activation}


def contextual_relevance_multiplier(entry: dict, usage_notes: dict | None = None) -> float:
    if not isinstance(usage_notes, dict):
        return 1.0
    activation = usage_notes.get("tag_activation", {})
    if not isinstance(activation, dict) or not activation:
        return 1.0
    tags = entry_tags(entry)
    if not tags:
        return 1.0
    average_activation = sum(float(activation.get(tag, 0.0)) for tag in tags) / float(len(tags))
    normalized = max(0.0, min(1.0, average_activation))
    return CONTEXT_MIN_MULTIPLIER + ((CONTEXT_MAX_MULTIPLIER - CONTEXT_MIN_MULTIPLIER) * normalized)


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
    relevance_mult = contextual_relevance_multiplier(entry, usage_notes)
    return max(
        MIN_SALIENCE,
        base * density_mult * actionability_mult * context_mult * relevance_mult,
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
    usage_notes = build_contextual_usage(entries)
    recent, remaining = split_recent_and_remaining(entries)
    scored_remaining = score_entries(remaining, usage_notes)
    budget = MAX_SALIENT_NOTES - len(recent)
    top_by_salience = scored_remaining[:budget]
    result = score_entries(recent, usage_notes)
    result.extend(top_by_salience)
    result.sort(key=lambda item: item[0], reverse=True)
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
