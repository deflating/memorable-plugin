#!/usr/bin/env python3
"""LLM-based memory consolidation — merges fading notes into stronger memories.

Inspired by sleep consolidation in human memory: periodically reviews notes
that are losing salience, finds clusters of related memories, and merges them
into consolidated summary notes. The originals are then archived.

This is the "forgetting as a feature" system — redundant, low-value memories
are compressed into denser, more useful consolidated memories.
"""

import json
import os
import sys
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Add daemon dir to path for note_generator imports
DAEMON_DIR = Path(__file__).resolve().parent.parent.parent.parent / "daemon"
sys.path.insert(0, str(DAEMON_DIR))

from note_constants import NOTES_DIR, WEEKLY_SYNTHESIS_PATH, MONTHLY_SYNTHESIS_PATH
from note_utils import (
    is_synthesis_entry,
    note_datetime,
    note_salience,
    note_tags,
    note_text,
    utc_now_iso,
)

# Consolidation thresholds
CONSOLIDATION_SALIENCE_CEILING = 0.4  # only consider notes below this
CONSOLIDATION_MIN_AGE_DAYS = 14  # don't consolidate anything newer than 2 weeks
CONSOLIDATION_MIN_CLUSTER_SIZE = 2  # need at least 2 notes to merge
CONSOLIDATION_MAX_CLUSTER_SIZE = 6  # don't merge more than 6 at once
MIN_TAG_OVERLAP = 1  # minimum shared tags to be in same cluster


def find_consolidation_candidates(notes_dir: Path, now: datetime) -> list[dict]:
    """Find notes that are fading but not yet archived — consolidation candidates."""
    cutoff = now - timedelta(days=CONSOLIDATION_MIN_AGE_DAYS)
    candidates = []
    excluded = {WEEKLY_SYNTHESIS_PATH.name, MONTHLY_SYNTHESIS_PATH.name}

    for jsonl_file in notes_dir.glob("*.jsonl"):
        if jsonl_file.name in excluded:
            continue
        try:
            with open(jsonl_file) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if is_synthesis_entry(entry):
                        continue
                    if entry.get("archived"):
                        continue
                    if entry.get("consolidated_from"):
                        continue  # already a consolidation product
                    if entry.get("pinned"):
                        continue
                    sal = note_salience(entry)
                    if sal >= CONSOLIDATION_SALIENCE_CEILING:
                        continue
                    dt = note_datetime(entry)
                    if not dt or dt > cutoff:
                        continue
                    candidates.append(entry)
        except OSError:
            continue

    return candidates


def cluster_by_tags(candidates: list[dict]) -> list[list[dict]]:
    """Group candidates into clusters based on shared tags."""
    if not candidates:
        return []

    # Simple greedy clustering: assign each note to the cluster with most tag overlap
    clusters: list[list[dict]] = []
    used: set[str] = set()

    # Sort by salience (lowest first — merge the weakest)
    candidates.sort(key=lambda e: note_salience(e))

    for entry in candidates:
        session_id = entry.get("session", "")
        if session_id in used:
            continue
        entry_tag_set = set(note_tags(entry))
        if not entry_tag_set:
            continue

        # Find best existing cluster
        best_cluster_idx = -1
        best_overlap = 0
        for idx, cluster in enumerate(clusters):
            if len(cluster) >= CONSOLIDATION_MAX_CLUSTER_SIZE:
                continue
            cluster_tags = set()
            for c_entry in cluster:
                cluster_tags.update(note_tags(c_entry))
            overlap = len(entry_tag_set & cluster_tags)
            if overlap >= MIN_TAG_OVERLAP and overlap > best_overlap:
                best_overlap = overlap
                best_cluster_idx = idx

        if best_cluster_idx >= 0:
            clusters[best_cluster_idx].append(entry)
        else:
            clusters.append([entry])
        used.add(session_id)

    # Filter to clusters with enough entries
    return [c for c in clusters if len(c) >= CONSOLIDATION_MIN_CLUSTER_SIZE]


def build_consolidation_prompt(cluster: list[dict]) -> str:
    """Build an LLM prompt to merge a cluster of related notes."""
    notes_text = []
    for i, entry in enumerate(cluster, 1):
        tags = ", ".join(note_tags(entry))
        sal = note_salience(entry)
        ew = entry.get("emotional_weight", 0.0)
        ts = entry.get("ts", "")[:10]
        notes_text.append(
            f"### Note {i} (date: {ts}, salience: {sal:.2f}, "
            f"emotional: {ew:.1f}, tags: [{tags}])\n{note_text(entry)}"
        )

    combined = "\n\n---\n\n".join(notes_text)

    return f"""You are consolidating fading memories for an AI assistant's persistent memory system. These related notes are losing salience and will be archived soon. Your job is to merge them into a single, dense consolidated memory that preserves the most important information.

{combined}

---

Write a single consolidated note that:
1. Preserves all key decisions, preferences, and facts from across the notes
2. Removes redundancy — if the same thing appears in multiple notes, keep it once
3. Keeps emotional context and relationship details (these matter most for continuity)
4. Prioritises information that would be useful if the AI encountered these topics again
5. Is concise — aim for about 1/3 the total length of the input notes
6. Uses the same format as the input notes (## sections, bullet points)

After the note, output metadata:
<!-- META: {{"topic_tags": ["tag1", "tag2", ...], "emotional_weight": 0.5}} -->

topic_tags: Union of the most important tags from the source notes (max 5).
emotional_weight: The highest emotional weight from any source note."""


def consolidate_cluster(cluster: list[dict], cfg: dict) -> dict | None:
    """Use LLM to merge a cluster of notes into a consolidated note."""
    try:
        from note_generator import call_llm, parse_meta
    except ImportError:
        # Try direct import from daemon
        sys.path.insert(0, str(DAEMON_DIR))
        from note_generator import call_llm, parse_meta

    prompt = build_consolidation_prompt(cluster)

    try:
        raw_response = call_llm(prompt, cfg, task="consolidation")
    except Exception:
        # Fall back to session_notes task routing if consolidation not configured
        try:
            raw_response = call_llm(prompt, cfg, task="session_notes")
        except Exception:
            return None

    note_content, topic_tags, emotional_weight = parse_meta(raw_response)

    now_iso = utc_now_iso()
    source_sessions = [e.get("session", "") for e in cluster if e.get("session")]

    # Consolidated note gets a salience boost — it's earned its place
    # by surviving long enough to be consolidated
    consolidated_entry = {
        "ts": cluster[0].get("ts", now_iso),  # oldest source timestamp
        "session": f"consolidated-{now_iso[:10]}",
        "machine": cluster[0].get("machine", ""),
        "message_count": sum(e.get("message_count", 0) for e in cluster),
        "first_ts": min(e.get("first_ts", e.get("ts", "")) for e in cluster),
        "last_ts": max(e.get("last_ts", e.get("ts", "")) for e in cluster),
        "note": note_content,
        "salience": 0.6,  # consolidated memories start with moderate salience
        "emotional_weight": emotional_weight,
        "novelty_score": 0.0,  # not novel — it's synthesised from existing
        "topic_tags": topic_tags,
        "last_referenced": now_iso,
        "reference_count": 0,
        "consolidated_from": source_sessions,
    }

    return consolidated_entry


def archive_consolidated_sources(notes_dir: Path, source_sessions: list[str]):
    """Mark source notes as archived after successful consolidation."""
    excluded = {WEEKLY_SYNTHESIS_PATH.name, MONTHLY_SYNTHESIS_PATH.name}
    session_set = set(source_sessions)

    for jsonl_file in notes_dir.glob("*.jsonl"):
        if jsonl_file.name in excluded:
            continue
        lines = []
        modified = False
        try:
            with open(jsonl_file) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        lines.append(line)
                        continue
                    if entry.get("session") in session_set:
                        entry["archived"] = True
                        entry["archived_reason"] = "consolidated"
                        entry["archived_at"] = utc_now_iso()
                        modified = True
                    lines.append(json.dumps(entry))
        except OSError:
            continue

        if modified:
            try:
                with open(jsonl_file, "w") as f:
                    f.write("\n".join(lines) + "\n")
            except OSError:
                pass


def run_consolidation(notes_dir: Path, cfg: dict) -> int:
    """Run a full consolidation cycle. Returns number of notes consolidated."""
    now = datetime.now(timezone.utc)
    candidates = find_consolidation_candidates(notes_dir, now)
    if not candidates:
        return 0

    clusters = cluster_by_tags(candidates)
    if not clusters:
        return 0

    total_consolidated = 0
    machine_id = candidates[0].get("machine", "consolidated")

    for cluster in clusters:
        consolidated = consolidate_cluster(cluster, cfg)
        if not consolidated:
            continue

        # Write consolidated note
        notes_file = notes_dir / f"{machine_id}.jsonl"
        try:
            with open(notes_file, "a") as f:
                f.write(json.dumps(consolidated) + "\n")
        except OSError:
            continue

        # Archive the source notes
        source_sessions = consolidated.get("consolidated_from", [])
        archive_consolidated_sources(notes_dir, source_sessions)
        total_consolidated += len(cluster)

    return total_consolidated
