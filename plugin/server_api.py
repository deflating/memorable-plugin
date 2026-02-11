#!/usr/bin/env python3
"""Memorable — HTTP server & API.

Serves the web UI and provides API endpoints for managing
seed files, session notes, settings, file uploads, and status.

Python 3 stdlib only. No external dependencies.
"""

import argparse
import io
import json
import os
import re
import shutil
import time
import uuid
import zipfile
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse, unquote

# -- Processor import (for anchor processing) ------------------------------

import sys as _sys
_sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from processor.anchor import (
    extract_at_depth as _extract_at_depth,
    process_file as _process_file,
    read_file_at_depth as _read_file_at_depth,
    estimate_tokens as _anchor_estimate_tokens,
)
from server_storage import (
    CHARS_PER_TOKEN,
    CONFIG_PATH,
    DATA_DIR,
    DEFAULT_PORT,
    FILES_DIR,
    MAX_UPLOAD_SIZE,
    NOTES_DIR,
    SESSIONS_DIR,
    SEEDS_DIR,
    UI_DIR,
    append_audit,
    atomic_write,
    atomic_write_bytes,
    ensure_dirs,
    error_response,
    estimate_tokens,
    load_config,
    save_config,
)

IMPORT_CONFIRM_TOKEN = "IMPORT"
MAX_IMPORT_SIZE = 100 * 1024 * 1024
MAX_IMPORT_FILES = 5000
MAX_IMPORT_UNCOMPRESSED = 300 * 1024 * 1024
NOTE_USAGE_PATH = DATA_DIR / "note_usage.json"


# -- Notes -----------------------------------------------------------------


def _is_internal_context_artifact(filename: str) -> bool:
    """Return True for internal helper files in the context directory."""
    return filename.endswith(".anchored") or filename.startswith(".cache-")


def _normalize_note(obj: dict) -> dict:
    """Map raw JSONL note fields to the shape the UI expects.

    JSONL has: ts, session, note, topic_tags, salience, ...
    UI wants:  date, summary, content, tags, salience, session
    """
    note_text = obj.get("note", "")
    if not isinstance(note_text, str):
        note_text = str(note_text)
    # Extract first meaningful line as summary
    summary = ""
    for line in note_text.splitlines():
        stripped = line.strip().lstrip("#").strip()
        if stripped and stripped.lower() != "summary":
            summary = stripped
            break

    raw_should_not_try = obj.get("should_not_try", [])
    if isinstance(raw_should_not_try, list):
        should_not_try = [
            str(item).strip()
            for item in raw_should_not_try
            if str(item).strip()
        ]
    else:
        should_not_try = []

    raw_tags = obj.get("topic_tags", [])
    if isinstance(raw_tags, list):
        tags = [str(t).strip() for t in raw_tags if str(t).strip()]
    else:
        tags = []

    raw_conflicts = obj.get("conflicts_with", [])
    if isinstance(raw_conflicts, list):
        conflicts_with = [str(item).strip() for item in raw_conflicts if str(item).strip()]
    else:
        conflicts_with = []

    return {
        "date": obj.get("ts", ""),
        "summary": summary,
        "content": note_text,
        "tags": tags,
        "salience": obj.get("salience", 0),
        "session": obj.get("session", ""),
        "machine": obj.get("machine", ""),
        "message_count": obj.get("message_count", 0),
        "should_not_try": should_not_try,
        "conflicts_with": conflicts_with,
    }


_TOOL_POSITIVE_RE = re.compile(
    r"\b(?:use|using|uses|used|adopted|switched to|migrated to|moved to|replaced with)\s+([a-z0-9][a-z0-9._+-]{1,30})\b",
    re.IGNORECASE,
)
_TOOL_NEGATIVE_RE = re.compile(
    r"\b(?:no longer use|stopped using|don't use|do not use|avoid)\s+([a-z0-9][a-z0-9._+-]{1,30})\b",
    re.IGNORECASE,
)
_TOOL_TRANSITION_RE = re.compile(
    r"\b(?:switched to|migrated to|moved to|replaced)\b",
    re.IGNORECASE,
)
_TOOL_STOPWORDS = {
    "the", "and", "with", "that", "this", "from", "into", "tool", "stack",
    "framework", "library", "system", "project", "code", "new", "old",
}


def _session_ref(note: dict) -> str:
    session = str(note.get("session", "")).strip()
    if session:
        return session[:8]
    date = str(note.get("date", "")).strip()
    return date[:10] if date else "unknown"


def _extract_tool_signals(text: str) -> dict:
    if not isinstance(text, str):
        text = str(text)

    positive = []
    for m in _TOOL_POSITIVE_RE.finditer(text):
        tok = m.group(1).lower().strip()
        if tok and tok not in _TOOL_STOPWORDS:
            positive.append(tok)

    negative = {
        m.group(1).lower().strip()
        for m in _TOOL_NEGATIVE_RE.finditer(text)
        if m.group(1).lower().strip() and m.group(1).lower().strip() not in _TOOL_STOPWORDS
    }

    return {
        "positive": set(positive),
        "negative": negative,
        "primary": positive[0] if positive else "",
        "transition": bool(_TOOL_TRANSITION_RE.search(text)),
    }


def _signals_conflict(a: dict, b: dict) -> bool:
    if (a["negative"] & b["positive"]) or (b["negative"] & a["positive"]):
        return True

    a_primary = a.get("primary", "")
    b_primary = b.get("primary", "")
    if (
        a_primary
        and b_primary
        and a_primary != b_primary
        and (a.get("transition") or b.get("transition"))
    ):
        return True

    return False


def _annotate_conflicts(notes: list[dict]) -> list[dict]:
    if not notes:
        return notes

    for n in notes:
        existing = n.get("conflicts_with", [])
        if not isinstance(existing, list):
            existing = []
        n["conflicts_with"] = {str(x).strip() for x in existing if str(x).strip()}

    tag_to_indices: dict[str, list[int]] = {}
    for idx, note in enumerate(notes):
        tags = note.get("tags", [])
        if not isinstance(tags, list):
            continue
        for tag in tags:
            t = str(tag).strip().lower()
            if not t:
                continue
            tag_to_indices.setdefault(t, []).append(idx)

    candidate_pairs: set[tuple[int, int]] = set()
    for indices in tag_to_indices.values():
        if len(indices) < 2:
            continue
        ordered = sorted(set(indices))
        for i in range(len(ordered)):
            for j in range(i + 1, len(ordered)):
                candidate_pairs.add((ordered[i], ordered[j]))

    signals_cache = {
        i: _extract_tool_signals(notes[i].get("content", ""))
        for i in range(len(notes))
    }

    for i, j in candidate_pairs:
        a = notes[i]
        b = notes[j]
        # Require at least one reasonably salient note in the pair.
        if max(a.get("salience", 0), b.get("salience", 0)) < 1.0:
            continue
        if not _signals_conflict(signals_cache[i], signals_cache[j]):
            continue

        a["conflicts_with"].add(_session_ref(b))
        b["conflicts_with"].add(_session_ref(a))

    for n in notes:
        n["conflicts_with"] = sorted(n["conflicts_with"])

    return notes


def load_all_notes() -> list[dict]:
    """Read all .jsonl files from the notes directory.

    Each line in each file is a JSON object.
    Returns a flat list of normalized note objects.
    """
    notes = []
    if not NOTES_DIR.is_dir():
        return notes

    for jsonl_path in sorted(NOTES_DIR.glob("*.jsonl")):
        try:
            with jsonl_path.open("r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                        if not isinstance(obj, dict):
                            continue
                        try:
                            notes.append(_normalize_note(obj))
                        except Exception:
                            continue
                    except json.JSONDecodeError:
                        continue
        except Exception:
            continue
    return _annotate_conflicts(notes)


def handle_get_notes(query_params: dict):
    """GET /api/notes — list session notes with optional search/sort/limit/tag/machine/session."""
    notes = load_all_notes()

    # Tag filter
    tag = query_params.get("tag", [None])[0]
    if tag:
        notes = [n for n in notes if tag in n.get("tags", [])]

    # Machine filter
    machine = query_params.get("machine", [None])[0]
    if machine:
        notes = [n for n in notes if n.get("machine", "") == machine]

    # Session filter (supports short prefixes shown in UI, like first 8 chars)
    session = query_params.get("session", [None])[0]
    if session:
        session_lower = session.lower()
        notes = [
            n
            for n in notes
            if str(n.get("session", "")).lower().startswith(session_lower)
        ]

    # Search filter
    search = query_params.get("search", [None])[0]
    if search:
        search_lower = search.lower()
        filtered = []
        for n in notes:
            text = n.get("content", "")
            tags = n.get("tags", [])
            tag_str = " ".join(tags) if isinstance(tags, list) else ""
            anti = n.get("should_not_try", [])
            anti_str = " ".join(anti) if isinstance(anti, list) else ""
            conflicts = n.get("conflicts_with", [])
            conflicts_str = " ".join(conflicts) if isinstance(conflicts, list) else ""
            session_ref = str(n.get("session", ""))
            if (
                search_lower in text.lower()
                or search_lower in tag_str.lower()
                or search_lower in anti_str.lower()
                or search_lower in conflicts_str.lower()
                or search_lower in session_ref.lower()
            ):
                filtered.append(n)
        notes = filtered

    # Sort
    sort_by = query_params.get("sort", ["date"])[0]
    if sort_by == "salience":
        notes.sort(key=lambda n: n.get("salience", 0), reverse=True)
    elif sort_by == "date_asc":
        notes.sort(key=lambda n: n.get("date", ""))
    else:
        notes.sort(key=lambda n: n.get("date", ""), reverse=True)

    # Total before pagination
    total = len(notes)

    # Offset
    offset_str = query_params.get("offset", [None])[0]
    if offset_str:
        try:
            offset = int(offset_str)
            if offset < 0:
                offset = 0
            notes = notes[offset:]
        except ValueError:
            pass

    # Limit
    limit_str = query_params.get("limit", [None])[0]
    if limit_str:
        try:
            limit = int(limit_str)
            if limit < 0:
                limit = 0
            notes = notes[:limit]
        except ValueError:
            pass

    return 200, {"notes": notes, "total": total}


def handle_get_notes_tags():
    """GET /api/notes/tags — return all tags with counts."""
    notes = load_all_notes()
    tag_counts: dict[str, int] = {}
    for n in notes:
        for t in n.get("tags", []):
            tag_counts[t] = tag_counts.get(t, 0) + 1
    tags = sorted(
        [{"name": k, "count": v} for k, v in tag_counts.items()],
        key=lambda x: x["count"],
        reverse=True,
    )
    return 200, {"tags": tags}


def handle_get_machines():
    """GET /api/machines — return distinct machine names from notes."""
    notes = load_all_notes()
    seen: set[str] = set()
    machines: list[str] = []
    for n in notes:
        m = n.get("machine", "")
        if m and m not in seen:
            seen.add(m)
            machines.append(m)
    return 200, {"machines": machines}


# -- Sessions --------------------------------------------------------------


def load_all_sessions() -> list[dict]:
    """Read all .json files from the sessions directory (top-level only)."""
    sessions = []
    if not SESSIONS_DIR.is_dir():
        return sessions

    for json_path in sorted(SESSIONS_DIR.glob("*.json")):
        # Skip backup directories — only read top-level files
        if json_path.parent != SESSIONS_DIR:
            continue
        try:
            obj = json.loads(json_path.read_text(encoding="utf-8"))
            sessions.append(obj)
        except Exception:
            continue
    return sessions


def handle_get_sessions(query_params: dict):
    """GET /api/sessions — list all sessions, sorted by date descending."""
    sessions = load_all_sessions()
    sessions.sort(key=lambda s: s.get("date", ""), reverse=True)

    limit_str = query_params.get("limit", [None])[0]
    if limit_str:
        try:
            limit = int(limit_str)
            sessions = sessions[:limit]
        except ValueError:
            pass

    return 200, {"sessions": sessions, "total": len(sessions)}


def handle_get_session(session_id: str):
    """GET /api/sessions/:id — get a single session by ID."""
    if not SESSIONS_DIR.is_dir():
        return 404, error_response(
            "SESSION_NOT_FOUND",
            "Session not found",
            "Check the session ID and try again.",
        )

    for json_path in SESSIONS_DIR.glob("*.json"):
        if json_path.parent != SESSIONS_DIR:
            continue
        try:
            obj = json.loads(json_path.read_text(encoding="utf-8"))
            if obj.get("id") == session_id:
                return 200, obj
        except Exception:
            continue

    return 404, error_response(
        "SESSION_NOT_FOUND",
        "Session not found",
        "Check the session ID and try again.",
    )


# -- Seeds -----------------------------------------------------------------


def handle_get_seeds():
    """GET /api/seeds — return all seed files as {filename: content}."""
    seeds = {}
    if not SEEDS_DIR.is_dir():
        return 200, {"files": seeds}

    for md_path in sorted(SEEDS_DIR.glob("*.md")):
        try:
            seeds[md_path.name] = md_path.read_text(encoding="utf-8")
        except Exception:
            seeds[md_path.name] = ""

    return 200, {"files": seeds}


def handle_post_seeds(body: dict):
    """POST /api/seeds — write seed files. Backup existing before overwriting.

    Expects body: {"files": {"filename.md": "content", ...}}
    """
    files = body.get("files")
    if not files or not isinstance(files, dict):
        return 400, error_response(
            "INVALID_FILES_PAYLOAD",
            "Missing or invalid 'files' field",
            "Send JSON with a 'files' object mapping filename.md to content.",
        )

    ensure_dirs()
    written = []

    for filename, content in files.items():
        if not isinstance(filename, str):
            continue
        if not isinstance(content, str):
            return 400, error_response(
                "INVALID_FILE_CONTENT",
                f"Content for {filename!r} must be text",
                "Send UTF-8 string content for each seed file.",
            )

        # Sanitize filename
        safe = "".join(c for c in filename if c.isalnum() or c in "-_.").strip()
        if not safe or not safe.endswith(".md"):
            continue

        path = SEEDS_DIR / safe

        # Backup existing
        if path.exists():
            bak = SEEDS_DIR / f".{safe}.bak"
            try:
                shutil.copy2(path, bak)
            except Exception:
                return 500, error_response(
                    "BACKUP_FAILED",
                    f"Backup failed for {safe}, aborting write",
                    "Free disk space or check permissions, then retry.",
                )

        atomic_write(path, content)
        written.append(safe)

    if not written:
        return 400, error_response(
            "NO_VALID_SEED_FILES",
            "No valid .md files to write",
            "Use filenames ending in .md with safe characters.",
        )

    append_audit("seeds.write", {"written": written, "count": len(written)})
    return 200, {"ok": True, "written": written}


# -- Settings --------------------------------------------------------------


def handle_get_settings():
    """GET /api/settings — return current config."""
    config = load_config()
    return 200, {"settings": config}


def handle_post_settings(body: dict):
    """POST /api/settings — update config. Merges with existing."""
    config = load_config()

    # Update top-level fields
    for key in ("token_budget", "server_port"):
        if key in body:
            config[key] = body[key]

    # Update nested objects
    if "llm_provider" in body and isinstance(body["llm_provider"], dict):
        if "llm_provider" not in config:
            config["llm_provider"] = {}
        config["llm_provider"].update(body["llm_provider"])

    if "daemon" in body and isinstance(body["daemon"], dict):
        if "daemon" not in config:
            config["daemon"] = {}
        config["daemon"].update(body["daemon"])

    if "data_dir" in body:
        config["data_dir"] = body["data_dir"]

    save_config(config)
    append_audit("settings.update", {"changed_keys": sorted(list(body.keys()))})
    return 200, {"ok": True, "settings": config}


# -- Status ----------------------------------------------------------------


def _get_daemon_status() -> dict:
    """Return daemon pid/running status based on daemon.pid and process liveness."""
    status = {"running": False, "pid": None}
    pid_file = DATA_DIR / "daemon.pid"
    if not pid_file.exists():
        return status

    try:
        pid = int(pid_file.read_text().strip())
    except ValueError:
        return status

    status["pid"] = pid
    try:
        os.kill(pid, 0)
        status["running"] = True
    except (OSError, ProcessLookupError):
        status["running"] = False
    return status


def _check_config_validity() -> dict:
    """Validate on-disk config schema for health checks."""
    if not CONFIG_PATH.exists():
        return {"exists": False, "valid": True, "error": None}

    try:
        raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"exists": True, "valid": False, "error": "Invalid JSON"}

    if not isinstance(raw, dict):
        return {"exists": True, "valid": False, "error": "Config root must be an object"}

    required = ("llm_provider", "token_budget", "daemon", "server_port")
    missing = [k for k in required if k not in raw]
    if missing:
        return {
            "exists": True,
            "valid": False,
            "error": f"Missing required keys: {', '.join(missing)}",
        }

    if not isinstance(raw.get("llm_provider"), dict):
        return {"exists": True, "valid": False, "error": "llm_provider must be an object"}
    if not isinstance(raw.get("daemon"), dict):
        return {"exists": True, "valid": False, "error": "daemon must be an object"}

    return {"exists": True, "valid": True, "error": None}


def _parse_iso_timestamp(value) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _latest_transcript_activity() -> datetime | None:
    transcripts_dir = DATA_DIR / "transcripts"
    if not transcripts_dir.is_dir():
        return None

    latest = None
    for path in transcripts_dir.rglob("*"):
        if not path.is_file():
            continue
        try:
            dt = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        except OSError:
            continue
        if latest is None or dt > latest:
            latest = dt
    return latest


def _daemon_health_snapshot(
    *,
    daemon_enabled: bool,
    daemon_status: dict,
    idle_threshold: int,
    last_note_dt: datetime | None,
    last_transcript_dt: datetime | None,
    note_count: int,
) -> dict:
    running = bool(daemon_status.get("running"))
    issues: list[str] = []
    actions: list[str] = []

    lag_threshold_seconds = max(600, max(60, idle_threshold) * 3)
    lag_seconds = None
    if last_transcript_dt is not None:
        if last_note_dt is not None:
            lag_seconds = int((last_transcript_dt - last_note_dt).total_seconds())
        elif note_count == 0:
            lag_seconds = int((datetime.now(timezone.utc) - last_transcript_dt).total_seconds())
        if lag_seconds is not None and lag_seconds < 0:
            lag_seconds = 0

    if daemon_enabled and not running:
        issues.append("daemon_not_running")
        actions.append("start_daemon_process")

    if daemon_enabled and lag_seconds is not None and lag_seconds > lag_threshold_seconds:
        issues.append("notes_lagging")
        actions.append("check_daemon_backlog")

    if daemon_enabled and note_count == 0 and last_transcript_dt is not None:
        issues.append("no_notes_generated")
        actions.append("verify_note_generation")

    if not daemon_enabled:
        state = "disabled"
    elif issues:
        state = "attention"
    elif running:
        state = "healthy"
    else:
        state = "idle"

    deduped_actions = list(dict.fromkeys(actions))

    return {
        "state": state,
        "enabled": daemon_enabled,
        "running": running,
        "pid": daemon_status.get("pid"),
        "issues": issues,
        "actions": deduped_actions,
        "lag_seconds": lag_seconds,
        "lag_threshold_seconds": lag_threshold_seconds if daemon_enabled else None,
        "last_note_at": last_note_dt.isoformat() if last_note_dt else None,
        "last_transcript_at": last_transcript_dt.isoformat() if last_transcript_dt else None,
    }


def handle_get_status():
    """GET /api/status — dashboard data."""
    config = load_config()
    daemon_cfg = config.get("daemon", {})
    if not isinstance(daemon_cfg, dict):
        daemon_cfg = {}
    daemon_enabled = bool(daemon_cfg.get("enabled", False))
    try:
        idle_threshold = int(daemon_cfg.get("idle_threshold", 300))
    except (TypeError, ValueError):
        idle_threshold = 300

    # Note count + newest note timestamp
    note_count = 0
    last_note_dt = None
    if NOTES_DIR.is_dir():
        for jsonl_path in NOTES_DIR.glob("*.jsonl"):
            try:
                with jsonl_path.open("r", encoding="utf-8") as fh:
                    for raw_line in fh:
                        line = raw_line.strip()
                        if not line:
                            continue
                        note_count += 1
                        try:
                            obj = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        if not isinstance(obj, dict):
                            continue
                        dt = _parse_iso_timestamp(obj.get("ts") or obj.get("first_ts"))
                        if dt and (last_note_dt is None or dt > last_note_dt):
                            last_note_dt = dt
            except Exception:
                continue

    # Session count & last session date
    session_count = 0
    last_session_date = None
    if SESSIONS_DIR.is_dir():
        for json_path in SESSIONS_DIR.glob("*.json"):
            if json_path.parent != SESSIONS_DIR:
                continue
            session_count += 1
            try:
                obj = json.loads(json_path.read_text(encoding="utf-8"))
                d = obj.get("date", "")
                if d and (last_session_date is None or d > last_session_date):
                    last_session_date = d
            except Exception:
                continue

    # Seed files present
    seeds_present = SEEDS_DIR.is_dir() and any(SEEDS_DIR.glob("*.md"))

    daemon_status = _get_daemon_status()
    daemon_running = bool(daemon_status.get("running"))
    last_transcript_dt = _latest_transcript_activity()
    daemon_health = _daemon_health_snapshot(
        daemon_enabled=daemon_enabled,
        daemon_status=daemon_status,
        idle_threshold=idle_threshold,
        last_note_dt=last_note_dt,
        last_transcript_dt=last_transcript_dt,
        note_count=note_count,
    )

    # Total token estimate from seed files
    total_tokens = 0
    if SEEDS_DIR.is_dir():
        for md_path in SEEDS_DIR.glob("*.md"):
            try:
                total_tokens += estimate_tokens(
                    md_path.read_text(encoding="utf-8")
                )
            except Exception:
                continue

    # File count
    file_count = 0
    if FILES_DIR.is_dir():
        file_count = sum(
            1
            for f in FILES_DIR.iterdir()
            if f.is_file() and not _is_internal_context_artifact(f.name)
        )

    return 200, {
        "total_notes": note_count,
        "note_count": note_count,
        "total_sessions": session_count,
        "session_count": session_count,
        "last_session_date": last_session_date,
        "last_note_date": daemon_health.get("last_note_at"),
        "last_transcript_date": daemon_health.get("last_transcript_at"),
        "seeds_present": seeds_present,
        "daemon_running": daemon_running,
        "daemon_enabled": daemon_enabled,
        "daemon_pid": daemon_status.get("pid"),
        "daemon_lag_seconds": daemon_health.get("lag_seconds"),
        "daemon_health": daemon_health,
        "total_seed_tokens": total_tokens,
        "file_count": file_count,
        "data_dir": str(DATA_DIR),
    }


def handle_get_memory_insights():
    """GET /api/memory/insights — summarize note load/reference effectiveness."""
    usage_notes = {}
    if NOTE_USAGE_PATH.exists():
        try:
            raw = json.loads(NOTE_USAGE_PATH.read_text(encoding="utf-8"))
            if isinstance(raw, dict) and isinstance(raw.get("notes"), dict):
                usage_notes = raw.get("notes", {})
        except Exception:
            usage_notes = {}

    rows = []
    total_loaded = 0
    total_referenced = 0

    for key, rec in usage_notes.items():
        if not isinstance(rec, dict):
            continue
        try:
            loaded = int(rec.get("loaded_count", 0))
        except (TypeError, ValueError):
            loaded = 0
        try:
            referenced = int(rec.get("referenced_count", 0))
        except (TypeError, ValueError):
            referenced = 0

        loaded = max(0, loaded)
        referenced = max(0, referenced)
        total_loaded += loaded
        total_referenced += referenced

        short = str(rec.get("session_short", "")).strip()
        if not short:
            short = str(rec.get("session", "")).strip()[:8]
        if not short:
            short = str(key).strip()[:8] or "unknown"

        ratio = 0.0 if loaded <= 0 else referenced / float(loaded)
        rows.append(
            {
                "key": str(key),
                "session": short,
                "loaded": loaded,
                "referenced": referenced,
                "reference_rate": round(ratio, 4),
            }
        )

    rows.sort(
        key=lambda r: (
            r["referenced"],
            r["reference_rate"],
            r["loaded"],
        ),
        reverse=True,
    )

    low_eff_rows = [
        r for r in rows
        if r["loaded"] >= 3 and r["reference_rate"] < 0.2
    ]
    low_eff_rows.sort(key=lambda r: (r["loaded"], -r["reference_rate"]), reverse=True)

    never_ref_count = sum(1 for r in rows if r["loaded"] >= 3 and r["referenced"] == 0)
    reference_rate = 0.0 if total_loaded <= 0 else total_referenced / float(total_loaded)

    suggestions = []
    if not rows:
        suggestions.append("No effectiveness data yet. Run a few sessions to collect baseline usage.")
    if never_ref_count > 0:
        suggestions.append(
            f"{never_ref_count} frequently loaded note(s) were never referenced. Consider lowering their salience or archiving."
        )
    if low_eff_rows:
        suggestions.append(
            "Some notes have low reference yield relative to load count. Consider refining tags or summaries."
        )
    if reference_rate >= 0.6 and total_loaded >= 10:
        suggestions.append("Memory reference yield is strong. Keep current note selection strategy.")

    return 200, {
        "tracked_notes": len(rows),
        "total_loaded": total_loaded,
        "total_referenced": total_referenced,
        "reference_rate": round(reference_rate, 4),
        "never_referenced_count": never_ref_count,
        "low_effectiveness_count": len(low_eff_rows),
        "top_referenced": rows[:5],
        "high_load_low_reference": low_eff_rows[:5],
        "suggestions": suggestions,
    }


def handle_get_health():
    """GET /api/health — basic runtime and storage health information."""
    ensure_dirs()

    seed_required = ("user.md", "agent.md", "now.md")
    seeds = {
        "required": {
            name: (SEEDS_DIR / name).is_file() for name in seed_required
        },
        "total_seed_files": 0,
    }
    if SEEDS_DIR.is_dir():
        seeds["total_seed_files"] = sum(1 for p in SEEDS_DIR.glob("*.md") if p.is_file())
    seeds["present"] = any(seeds["required"].values())

    usage = shutil.disk_usage(DATA_DIR)
    config_health = _check_config_validity()
    daemon = _get_daemon_status()

    return 200, {
        "ok": config_health["valid"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "seeds": seeds,
        "disk": {
            "path": str(DATA_DIR),
            "total_bytes": usage.total,
            "used_bytes": usage.used,
            "free_bytes": usage.free,
        },
        "config": config_health,
        "daemon": daemon,
    }


# -- Files -----------------------------------------------------------------


def handle_get_files():
    """GET /api/files — list uploaded context files with metadata + anchor info."""
    files = []
    if not FILES_DIR.is_dir():
        return 200, {"files": files}

    config = load_config()
    context_files = {
        cf.get("filename"): cf
        for cf in config.get("context_files", [])
    }

    for f in sorted(FILES_DIR.iterdir()):
        if not f.is_file():
            continue
        # Skip internal helper artifacts.
        if _is_internal_context_artifact(f.name):
            continue
        try:
            stat = f.stat()
            tokens = 0
            try:
                content = f.read_text(encoding="utf-8")
                tokens = estimate_tokens(content)
            except (UnicodeDecodeError, Exception):
                pass

            anchored_path = FILES_DIR / (f.name + ".anchored")
            is_anchored = anchored_path.is_file()

            # Token counts at each depth if anchored
            tokens_by_depth = None
            if is_anchored:
                try:
                    anch_text = anchored_path.read_text(encoding="utf-8")
                    tokens_by_depth = {}
                    for d in range(4):
                        extracted = _extract_at_depth(anch_text, d)
                        tokens_by_depth[str(d)] = _anchor_estimate_tokens(extracted)
                except Exception:
                    pass

            # Config for this file
            cf = context_files.get(f.name, {})

            files.append({
                "name": f.name,
                "size": stat.st_size,
                "tokens": tokens,
                "modified": datetime.fromtimestamp(
                    stat.st_mtime, tz=timezone.utc
                ).isoformat(),
                "anchored": is_anchored,
                "tokens_by_depth": tokens_by_depth,
                "depth": cf.get("depth", 1),
                "enabled": cf.get("enabled", False),
            })
        except Exception:
            continue

    return 200, {"files": files}


def handle_post_file_upload(handler):
    """POST /api/files/upload — handle file upload via multipart or raw body.

    Supports two modes:
    1. JSON body: {"filename": "name.md", "content": "text content"}
    2. Raw body with X-Filename header
    """
    ensure_dirs()
    content_type = handler.headers.get("Content-Type", "")

    raw_length = handler.headers.get("Content-Length", "0")
    try:
        length = int(raw_length)
    except (TypeError, ValueError):
        return 400, error_response(
            "INVALID_CONTENT_LENGTH",
            "Invalid Content-Length header",
            "Send a valid numeric Content-Length header.",
        )
    if length < 0:
        return 400, error_response(
            "INVALID_CONTENT_LENGTH",
            "Invalid Content-Length header",
            "Send a non-negative Content-Length header.",
        )

    if "application/json" in content_type:
        if length == 0:
            return 400, error_response(
                "EMPTY_BODY",
                "Empty body",
                "Provide a JSON body with filename and content.",
            )
        if length > MAX_UPLOAD_SIZE:
            return 413, error_response(
                "UPLOAD_TOO_LARGE",
                "Upload too large",
                f"Reduce payload to <= {MAX_UPLOAD_SIZE} bytes.",
            )
        raw = handler.rfile.read(length)
        try:
            body = json.loads(raw)
        except json.JSONDecodeError:
            return 400, error_response(
                "INVALID_JSON",
                "Invalid JSON",
                "Send a valid JSON object.",
            )
        if not isinstance(body, dict):
            return 400, error_response(
                "INVALID_JSON_OBJECT",
                "JSON body must be an object",
                "Send a JSON object payload.",
            )

        filename = body.get("filename", "")
        content = body.get("content", "")

        if not isinstance(filename, str) or not isinstance(content, str):
            return 400, error_response(
                "INVALID_UPLOAD_FIELDS_TYPE",
                "'filename' and 'content' must be strings",
                "Send JSON with string values for both filename and content.",
            )

        if not filename or not content:
            return 400, error_response(
                "MISSING_UPLOAD_FIELDS",
                "Missing 'filename' or 'content'",
                "Include both filename and content in the JSON body.",
            )

        # Sanitize filename
        safe = "".join(
            c for c in filename if c.isalnum() or c in "-_."
        ).strip()
        if not safe:
            safe = f"upload-{uuid.uuid4().hex[:8]}.txt"

        path = FILES_DIR / safe
        atomic_write(path, content)
        append_audit(
            "files.upload",
            {"filename": safe, "size_bytes": len(content), "mode": "json"},
        )

        return 200, {
            "ok": True,
            "filename": safe,
            "size": len(content),
            "tokens": estimate_tokens(content),
        }
    else:
        # Raw body upload
        filename = handler.headers.get("X-Filename", "")
        if length == 0:
            return 400, error_response(
                "EMPTY_BODY",
                "Empty body",
                "Provide request body bytes and optional X-Filename header.",
            )
        if length > MAX_UPLOAD_SIZE:
            return 413, error_response(
                "UPLOAD_TOO_LARGE",
                "Upload too large",
                f"Reduce payload to <= {MAX_UPLOAD_SIZE} bytes.",
            )

        raw = handler.rfile.read(length)

        safe = ""
        if filename:
            safe = "".join(
                c for c in filename if c.isalnum() or c in "-_."
            ).strip()
        if not safe:
            safe = f"upload-{uuid.uuid4().hex[:8]}.bin"

        path = FILES_DIR / safe
        atomic_write_bytes(path, raw)
        append_audit(
            "files.upload",
            {"filename": safe, "size_bytes": len(raw), "mode": "raw"},
        )

        tokens = 0
        try:
            tokens = estimate_tokens(raw.decode("utf-8"))
        except (UnicodeDecodeError, Exception):
            pass

        return 200, {
            "ok": True,
            "filename": safe,
            "size": len(raw),
            "tokens": tokens,
        }


# -- Anchor processing endpoints -------------------------------------------


def handle_process_file(filename: str):
    """POST /api/files/<filename>/process — trigger LLM anchor processing."""
    safe = "".join(c for c in filename if c.isalnum() or c in "-_.").strip()
    if not safe:
        return 400, error_response(
            "INVALID_FILENAME",
            "Invalid filename",
            "Use only alphanumeric characters, dash, underscore, and dot.",
        )

    result = _process_file(safe, force=True)
    append_audit(
        "files.process",
        {
            "filename": safe,
            "status": result.get("status"),
            "method": result.get("method"),
        },
    )
    return 200, result


def handle_preview_file(filename: str, query_params: dict):
    """GET /api/files/<filename>/preview — preview at a depth.

    Query params:
      depth=N  — extract at this depth (0-3, or -1/full for raw)
      raw=true — return the .anchored file as-is with ⚓ tags visible
    """
    safe = "".join(c for c in filename if c.isalnum() or c in "-_.").strip()
    if not safe:
        return 400, error_response(
            "INVALID_FILENAME",
            "Invalid filename",
            "Use only alphanumeric characters, dash, underscore, and dot.",
        )

    # raw=true returns the anchored file with tags intact
    if query_params.get("raw", [""])[0] == "true":
        anchored_path = FILES_DIR / (safe + ".anchored")
        if anchored_path.is_file():
            content = anchored_path.read_text(encoding="utf-8")
            return 200, {
                "content": content,
                "tokens": estimate_tokens(content),
                "depth": "raw",
            }
        # Fall through to raw file if no .anchored exists

    depth_str = query_params.get("depth", ["1"])[0]
    try:
        depth = int(depth_str)
    except ValueError:
        depth = -1 if depth_str == "full" else 1

    content = _read_file_at_depth(safe, depth)
    if content is None:
        return 404, error_response(
            "FILE_NOT_FOUND",
            "File not found",
            "Check the filename and upload the file if needed.",
        )

    return 200, {
        "content": content,
        "tokens": estimate_tokens(content),
        "depth": depth,
    }


def handle_put_file_depth(filename: str, body: dict):
    """PUT /api/files/<filename>/depth — set loading depth + enabled."""
    safe = "".join(c for c in filename if c.isalnum() or c in "-_.").strip()
    if not safe:
        return 400, error_response(
            "INVALID_FILENAME",
            "Invalid filename",
            "Use only alphanumeric characters, dash, underscore, and dot.",
        )

    depth = body.get("depth", 1)
    enabled = body.get("enabled", True)

    config = load_config()
    context_files = config.get("context_files", [])

    # Update or insert
    found = False
    for cf in context_files:
        if cf.get("filename") == safe:
            cf["depth"] = depth
            cf["enabled"] = enabled
            found = True
            break
    if not found:
        context_files.append({
            "filename": safe,
            "depth": depth,
            "enabled": enabled,
        })

    config["context_files"] = context_files
    save_config(config)
    append_audit(
        "files.depth.update",
        {"filename": safe, "depth": depth, "enabled": enabled},
    )

    return 200, {"ok": True, "filename": safe, "depth": depth, "enabled": enabled}


def handle_post_deploy(body: dict):
    """POST /api/deploy — write seed files to seeds directory.

    Expects body: {"files": {"user.md": "...", "agent.md": "..."}}
    """
    files = body.get("files")
    if not files or not isinstance(files, dict):
        return 400, error_response(
            "INVALID_FILES_PAYLOAD",
            "Missing or invalid 'files' field. Expected {filename: content}",
            "Send JSON with a 'files' object mapping filename.md to content.",
        )

    ensure_dirs()
    deployed_files = []

    for filename, content in files.items():
        if not isinstance(filename, str):
            continue
        if not isinstance(content, str):
            return 400, error_response(
                "INVALID_FILE_CONTENT",
                f"Content for {filename!r} must be text",
                "Send UTF-8 string content for each seed file.",
            )

        safe = "".join(
            c for c in filename if c.isalnum() or c in "-_."
        ).strip()
        if not safe or not safe.endswith(".md"):
            continue

        path = SEEDS_DIR / safe

        # Backup existing
        if path.exists():
            bak = SEEDS_DIR / f".{safe}.bak"
            try:
                shutil.copy2(path, bak)
            except Exception:
                return 500, error_response(
                    "BACKUP_FAILED",
                    f"Backup failed for {safe}, aborting write",
                    "Free disk space or check permissions, then retry.",
                )

        atomic_write(path, content)
        deployed_files.append(safe)

    if not deployed_files:
        return 400, error_response(
            "NO_VALID_SEED_FILES",
            "No valid .md files to deploy",
            "Use filenames ending in .md with safe characters.",
        )

    append_audit(
        "seeds.deploy",
        {"deployed": deployed_files, "count": len(deployed_files)},
    )
    return 200, {
        "ok": True,
        "deployed": deployed_files,
        "path": str(SEEDS_DIR),
    }


def handle_post_process(body: dict):
    """POST /api/process — store a document for processing.

    This is a stub. Actual processing is done by the processor/daemon.
    """
    content = body.get("content", "")
    filename = body.get("filename", "document.md")
    depth = body.get("anchor_depth", 3)

    if not isinstance(content, str):
        return 400, error_response(
            "INVALID_CONTENT_TYPE",
            "'content' must be a string",
            "Send content as UTF-8 text.",
        )
    if not isinstance(filename, str):
        return 400, error_response(
            "INVALID_FILENAME_TYPE",
            "'filename' must be a string",
            "Send filename as a string.",
        )

    if not content:
        return 400, error_response(
            "MISSING_CONTENT",
            "Missing 'content' field",
            "Provide a non-empty content field.",
        )

    ensure_dirs()

    safe_name = (
        "".join(c for c in filename if c.isalnum() or c in "-_.").strip()
        or "document.md"
    )
    original_path = FILES_DIR / f"original_{safe_name}"
    atomic_write(original_path, content)
    append_audit(
        "files.store_for_processing",
        {
            "filename": safe_name,
            "tokens": estimate_tokens(content),
            "anchor_depth": depth,
        },
    )

    return 200, {
        "ok": True,
        "stored": str(original_path),
        "tokens": estimate_tokens(content),
        "anchor_depth": depth,
        "status": "stored",
        "message": "Document stored. Use the processor to extract anchors.",
    }


def handle_get_budget():
    """GET /api/budget — return current token budget breakdown.

    Mirrors what session_start.py actually loads: seed files + semantic files
    at their configured depths.
    """
    config = load_config()
    budget = config.get("token_budget", 200000)

    breakdown = []
    total_used = 0

    # Core seed files — mirrors session_start.py which loads user.md, agent.md, now.md
    for seed_name in ("user.md", "agent.md", "now.md"):
        seed_path = SEEDS_DIR / seed_name
        if seed_path.is_file():
            try:
                content = seed_path.read_text(encoding="utf-8")
                tokens = estimate_tokens(content)
                breakdown.append({
                    "file": seed_name,
                    "type": "seed",
                    "tokens": tokens,
                    "chars": len(content),
                })
                total_used += tokens
            except Exception:
                pass

    # Context files from config — mirrors session_start.py collect_context_files()
    context_files = config.get("context_files", [])
    for entry in context_files:
        if not entry.get("enabled", True):
            continue
        filename = entry.get("filename", "")
        if not filename:
            continue
        depth = entry.get("depth", -1)

        # Check FILES_DIR first (semantic file), then fall back to seeds
        raw_path = FILES_DIR / filename
        anchored_path = FILES_DIR / (filename + ".anchored")
        seed_path = SEEDS_DIR / filename

        try:
            if raw_path.is_file():
                if depth is not None and depth >= 0 and anchored_path.is_file():
                    anchored_text = anchored_path.read_text(encoding="utf-8")
                    extracted = _extract_at_depth(anchored_text, depth)
                    tokens = estimate_tokens(extracted)
                else:
                    content = raw_path.read_text(encoding="utf-8")
                    tokens = estimate_tokens(content)
                breakdown.append({
                    "file": filename,
                    "type": "semantic",
                    "depth": depth,
                    "tokens": tokens,
                    "chars": tokens * CHARS_PER_TOKEN,
                })
                total_used += tokens
            elif seed_path.is_file():
                content = seed_path.read_text(encoding="utf-8")
                tokens = estimate_tokens(content)
                breakdown.append({
                    "file": filename,
                    "type": "seed",
                    "tokens": tokens,
                    "chars": len(content),
                })
                total_used += tokens
        except Exception:
            pass

    return 200, {
        "budget": budget,
        "used": total_used,
        "remaining": max(0, budget - total_used),
        "breakdown": breakdown,
        "chars_per_token": CHARS_PER_TOKEN,
    }


# -- Export / reset --------------------------------------------------------


def _build_export_zip() -> bytes:
    """Create an in-memory ZIP of all files under DATA_DIR."""
    ensure_dirs()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(DATA_DIR.rglob("*")):
            if not path.is_file():
                continue
            arcname = path.relative_to(DATA_DIR).as_posix()
            zf.write(path, arcname)
    return buf.getvalue()


def handle_get_export():
    """GET /api/export — download a ZIP archive of all local data."""
    try:
        payload = _build_export_zip()
    except Exception:
        return 500, error_response(
            "EXPORT_BUILD_FAILED",
            "Failed to build export archive",
            "Retry and check file permissions in the data directory.",
        )

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%SZ")
    filename = f"memorable-export-{stamp}.zip"
    return 200, {"filename": filename, "payload": payload}


def _safe_archive_member_path(name: str) -> Path | None:
    """Return a safe relative archive path or None if unsafe/invalid."""
    if not name:
        return None
    member = Path(name)
    if member.is_absolute():
        return None
    parts = [p for p in member.parts if p not in ("", ".")]
    if not parts or any(p == ".." for p in parts):
        return None
    return Path(*parts)


def _import_zip_payload(payload: bytes) -> int:
    """Replace DATA_DIR contents with files from ZIP payload.

    Returns number of restored files.
    """
    try:
        archive = zipfile.ZipFile(io.BytesIO(payload))
    except zipfile.BadZipFile as e:
        raise ValueError("Invalid ZIP archive") from e

    staged_files: list[tuple[Path, bytes]] = []
    total_uncompressed = 0
    with archive:
        members = [m for m in archive.infolist() if not m.is_dir()]
        if not members:
            raise ValueError("Archive has no files")
        if len(members) > MAX_IMPORT_FILES:
            raise ValueError(f"Archive has too many files (max {MAX_IMPORT_FILES})")

        for member in members:
            rel = _safe_archive_member_path(member.filename)
            if rel is None:
                raise ValueError(f"Unsafe path in archive: {member.filename}")

            total_uncompressed += int(member.file_size)
            if total_uncompressed > MAX_IMPORT_UNCOMPRESSED:
                raise ValueError(
                    f"Archive uncompressed size exceeds {MAX_IMPORT_UNCOMPRESSED} bytes"
                )

            staged_files.append((rel, archive.read(member)))

    root = DATA_DIR.parent
    stage_dir = root / f".import-stage-{uuid.uuid4().hex[:10]}"
    backup_dir = root / f".import-backup-{uuid.uuid4().hex[:10]}"

    stage_dir.mkdir(parents=True, exist_ok=True)
    try:
        for rel, data in staged_files:
            dest = stage_dir / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)

        if DATA_DIR.exists():
            shutil.move(str(DATA_DIR), str(backup_dir))
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copytree(stage_dir, DATA_DIR, dirs_exist_ok=True)
        ensure_dirs()

        if backup_dir.exists():
            shutil.rmtree(backup_dir)
    except Exception:
        try:
            if DATA_DIR.exists():
                shutil.rmtree(DATA_DIR)
        except Exception:
            pass
        try:
            if backup_dir.exists():
                shutil.move(str(backup_dir), str(DATA_DIR))
        except Exception:
            pass
        raise
    finally:
        try:
            if stage_dir.exists():
                shutil.rmtree(stage_dir)
        except Exception:
            pass

    return len(staged_files)


def handle_post_import(handler):
    """POST /api/import — restore data from an exported ZIP archive."""
    token = str(handler.headers.get("X-Confirmation-Token", "")).strip()
    if token != IMPORT_CONFIRM_TOKEN:
        return 400, error_response(
            "CONFIRMATION_TOKEN_MISMATCH",
            "Confirmation token mismatch",
            f"Send X-Confirmation-Token exactly as '{IMPORT_CONFIRM_TOKEN}'.",
        )

    raw_length = handler.headers.get("Content-Length", "0")
    try:
        length = int(raw_length)
    except (TypeError, ValueError):
        return 400, error_response(
            "INVALID_CONTENT_LENGTH",
            "Invalid Content-Length header",
            "Send a valid numeric Content-Length header.",
        )
    if length <= 0:
        return 400, error_response(
            "EMPTY_BODY",
            "Empty body",
            "Upload a ZIP archive body.",
        )
    if length > MAX_IMPORT_SIZE:
        return 413, error_response(
            "IMPORT_TOO_LARGE",
            "Import archive too large",
            f"Reduce payload to <= {MAX_IMPORT_SIZE} bytes.",
        )

    payload = handler.rfile.read(length)
    try:
        restored_files = _import_zip_payload(payload)
    except ValueError as e:
        return 400, error_response(
            "INVALID_IMPORT_ARCHIVE",
            str(e),
            "Upload a valid Memorable export ZIP archive.",
        )
    except Exception:
        return 500, error_response(
            "IMPORT_FAILED",
            "Failed to import archive",
            "Check file permissions and archive integrity, then retry.",
        )

    append_audit(
        "data.import",
        {
            "restored_files": restored_files,
            "filename": str(handler.headers.get("X-Filename", "")).strip(),
        },
    )
    return 200, {"ok": True, "restored_files": restored_files}


def handle_post_reset(body: dict):
    """POST /api/reset — wipe DATA_DIR contents after explicit confirmation."""
    token = str(body.get("confirmation_token", "")).strip()
    if token != "RESET":
        return 400, error_response(
            "CONFIRMATION_TOKEN_MISMATCH",
            "Confirmation token mismatch",
            "Send confirmation_token exactly as 'RESET'.",
        )

    ensure_dirs()
    removed = []
    failed = []

    for entry in DATA_DIR.iterdir():
        try:
            if entry.is_symlink() or entry.is_file():
                entry.unlink()
            elif entry.is_dir():
                shutil.rmtree(entry)
            else:
                entry.unlink(missing_ok=True)
            removed.append(entry.name)
        except Exception:
            failed.append(entry.name)

    ensure_dirs()

    if failed:
        append_audit(
            "data.reset.failed",
            {"removed": removed, "failed": failed},
        )
        return 500, error_response(
            "RESET_PARTIAL_FAILURE",
            "Reset partially failed",
            "Check file permissions in the data directory and retry.",
        )

    append_audit("data.reset", {"removed_count": len(removed)})
    return 200, {"ok": True, "removed_count": len(removed)}
