#!/usr/bin/env python3
"""Memorable — HTTP server & API.

Serves the web UI and provides API endpoints for managing
seed files, session notes, settings, file uploads, and status.

Python 3 stdlib only. No external dependencies.
"""

import argparse
import hashlib
import io
import json
import os
import re
import shutil
import time
import uuid
import zipfile
from datetime import datetime, timedelta, timezone
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse, unquote

# -- Processor & daemon imports -----------------------------------------------

import sys as _sys
_sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
_sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "daemon"))
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
RELIABILITY_METRICS_PATH = DATA_DIR / "reliability_metrics.json"
NOTE_SALIENCE_STEP = 0.25
NOTE_SALIENCE_MIN = 0.0
NOTE_SALIENCE_MAX = 3.0
METRICS_RETENTION_LIMIT = 500


def default_reliability_metrics() -> dict:
    return {
        "import": {"success": 0, "failure": 0},
        "export": {"success": 0, "failure": 0},
        "lag_incidents": [],
    }


def clean_counter(value) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def clean_lag_incidents(value) -> list[dict]:
    if not isinstance(value, list):
        return []
    cleaned = []
    for item in value:
        if not isinstance(item, dict):
            continue
        ts = str(item.get("ts", "")).strip()
        source_ts = str(item.get("source_ts", "")).strip()
        lag_seconds = item.get("lag_seconds")
        lag_seconds = clean_counter(lag_seconds) if lag_seconds is not None else None
        if not ts:
            continue
        cleaned.append(
            {
                "ts": ts,
                "source_ts": source_ts,
                "lag_seconds": lag_seconds,
            }
        )
    return cleaned[-METRICS_RETENTION_LIMIT:]


def load_reliability_metrics() -> dict:
    metrics = default_reliability_metrics()
    try:
        if not RELIABILITY_METRICS_PATH.exists():
            return metrics
        raw = json.loads(RELIABILITY_METRICS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return metrics

    if not isinstance(raw, dict):
        return metrics

    import_raw = raw.get("import", {})
    export_raw = raw.get("export", {})
    metrics["import"]["success"] = clean_counter(
        import_raw.get("success", 0) if isinstance(import_raw, dict) else 0
    )
    metrics["import"]["failure"] = clean_counter(
        import_raw.get("failure", 0) if isinstance(import_raw, dict) else 0
    )
    metrics["export"]["success"] = clean_counter(
        export_raw.get("success", 0) if isinstance(export_raw, dict) else 0
    )
    metrics["export"]["failure"] = clean_counter(
        export_raw.get("failure", 0) if isinstance(export_raw, dict) else 0
    )
    metrics["lag_incidents"] = clean_lag_incidents(raw.get("lag_incidents", []))
    return metrics


def save_reliability_metrics(metrics: dict):
    try:
        RELIABILITY_METRICS_PATH.parent.mkdir(parents=True, exist_ok=True)
        atomic_write(
            RELIABILITY_METRICS_PATH,
            json.dumps(metrics, ensure_ascii=False, indent=2) + "\n",
        )
    except Exception:
        pass


def increment_reliability_metric(operation: str, outcome: str):
    if operation not in {"import", "export"}:
        return
    if outcome not in {"success", "failure"}:
        return
    metrics = load_reliability_metrics()
    metrics[operation][outcome] = clean_counter(metrics[operation].get(outcome, 0)) + 1
    save_reliability_metrics(metrics)


def record_lag_incident(last_activity_dt: datetime, lag_seconds: int | None):
    source_ts = last_activity_dt.astimezone(timezone.utc).isoformat()
    metrics = load_reliability_metrics()
    incidents = clean_lag_incidents(metrics.get("lag_incidents", []))
    if any(str(item.get("source_ts", "")) == source_ts for item in incidents):
        return
    incidents.append(
        {
            "ts": datetime.now(timezone.utc).isoformat(),
            "source_ts": source_ts,
            "lag_seconds": clean_counter(lag_seconds) if lag_seconds is not None else None,
        }
    )
    metrics["lag_incidents"] = incidents[-METRICS_RETENTION_LIMIT:]
    save_reliability_metrics(metrics)


# -- Notes -----------------------------------------------------------------


def is_internal_context_artifact(filename: str) -> bool:
    """Return True for internal helper files in the context directory."""
    return filename.endswith(".anchored") or filename.startswith(".cache-")


def note_row_id(source_path: Path, line_no: int, obj: dict) -> str:
    text = str(obj.get("note", ""))
    fingerprint = (
        f"{source_path.name}|{line_no}|{obj.get('ts', '')}|"
        f"{obj.get('session', '')}|{text}"
    )
    digest = hashlib.sha1(fingerprint.encode("utf-8")).hexdigest()[:16]
    return f"note_{digest}"


def note_salience_value(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def clamp_note_salience(value: float) -> float:
    return max(NOTE_SALIENCE_MIN, min(NOTE_SALIENCE_MAX, float(value)))


def clean_string_list(raw_value) -> list[str]:
    if not isinstance(raw_value, list):
        return []
    cleaned = []
    for item in raw_value:
        text = str(item).strip()
        if text:
            cleaned.append(text)
    return cleaned


def note_flag_value(value) -> bool:
    if value is True:
        return True
    if value is False:
        return False
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return False


def sanitize_note_tags(raw_tags) -> list[str] | None:
    if not isinstance(raw_tags, list):
        return None
    cleaned: list[str] = []
    seen: set[str] = set()
    for tag in raw_tags:
        text = str(tag).strip()
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(text[:64])
        if len(cleaned) >= 24:
            break
    return cleaned


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def clean_note_object(obj: dict) -> dict:
    return {
        "ts": str(obj.get("ts", "")),
        "session": str(obj.get("session", "")),
        "machine": str(obj.get("machine", "")),
        "note": str(obj.get("note", "")),
        "topic_tags": clean_string_list(obj.get("topic_tags", [])),
        "should_not_try": clean_string_list(obj.get("should_not_try", [])),
        "message_count": obj.get("message_count", 0),
        "salience": note_salience_value(obj.get("salience", 0.0)),
        "pinned": note_flag_value(obj.get("pinned", False)),
        "archived": note_flag_value(obj.get("archived", False)),
        "review_updated_at": str(obj.get("review_updated_at", "")),
    }


def iter_note_rows():
    if not NOTES_DIR.is_dir():
        return
    for jsonl_path in sorted(NOTES_DIR.glob("*.jsonl")):
        try:
            with jsonl_path.open("r", encoding="utf-8") as fh:
                for line_no, raw_line in enumerate(fh, start=1):
                    line = raw_line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if not isinstance(obj, dict):
                        continue
                    note_obj = clean_note_object(obj)
                    yield {
                        "source_path": jsonl_path,
                        "line_no": line_no,
                        "obj": note_obj,
                        "id": note_row_id(jsonl_path, line_no, note_obj),
                    }
        except Exception:
            continue


def normalize_note(obj: dict, note_id: str = "") -> dict:
    """Map raw JSONL note fields to the shape the UI expects.

    JSONL has: ts, session, note, topic_tags, salience, ...
    UI wants:  date, summary, content, tags, salience, session
    """
    note_text = obj.get("note", "")
    summary = ""
    for line in note_text.splitlines():
        stripped = line.strip().lstrip("#").strip()
        if stripped and stripped.lower() != "summary":
            summary = stripped
            break

    should_not_try = obj.get("should_not_try", [])
    tags = obj.get("topic_tags", [])

    return {
        "id": note_id,
        "date": obj.get("ts", ""),
        "summary": summary,
        "content": note_text,
        "tags": tags,
        "salience": note_salience_value(obj.get("salience", 0.0)),
        "session": obj.get("session", ""),
        "machine": obj.get("machine", ""),
        "message_count": obj.get("message_count", 0),
        "pinned": obj.get("pinned", False),
        "archived": obj.get("archived", False),
        "should_not_try": should_not_try,
    }


def load_all_notes(include_archived: bool = True) -> list[dict]:
    """Read all .jsonl files from the notes directory.

    Each line in each file is a JSON object.
    Returns a flat list of normalized note objects.
    """
    notes = []
    for row in iter_note_rows() or []:
        normalized = normalize_note(row["obj"], row["id"])
        if not include_archived and normalized.get("archived"):
            continue
        notes.append(normalized)
    return notes


def handle_get_notes(query_params: dict):
    """GET /api/notes — list session notes with optional search/sort/limit/tag/machine/session."""
    notes = load_all_notes(include_archived=True)

    archived_mode = str(query_params.get("archived", ["exclude"])[0] or "exclude").strip().lower()
    if archived_mode == "only":
        notes = [n for n in notes if n.get("archived")]
    elif archived_mode != "include":
        notes = [n for n in notes if not n.get("archived")]

    tag = query_params.get("tag", [None])[0]
    if tag:
        notes = [n for n in notes if tag in n.get("tags", [])]

    machine = query_params.get("machine", [None])[0]
    if machine:
        notes = [n for n in notes if n.get("machine", "") == machine]

    session = query_params.get("session", [None])[0]
    if session:
        session_lower = session.lower()
        notes = [
            n
            for n in notes
            if str(n.get("session", "")).lower().startswith(session_lower)
        ]

    search = query_params.get("search", [None])[0]
    if search:
        search_lower = search.lower()
        filtered = []
        for n in notes:
            text = n.get("content", "")
            tag_str = " ".join(n.get("tags", []))
            anti_str = " ".join(n.get("should_not_try", []))
            session_ref = str(n.get("session", ""))
            if (
                search_lower in text.lower()
                or search_lower in tag_str.lower()
                or search_lower in anti_str.lower()
                or search_lower in session_ref.lower()
            ):
                filtered.append(n)
        notes = filtered

    sort_by = query_params.get("sort", ["date"])[0]
    if sort_by == "salience":
        notes.sort(key=lambda n: n.get("salience", 0), reverse=True)
    elif sort_by == "date_asc":
        notes.sort(key=lambda n: n.get("date", ""))
    else:
        notes.sort(key=lambda n: n.get("date", ""), reverse=True)

    total = len(notes)

    offset_str = query_params.get("offset", [None])[0]
    if offset_str:
        try:
            offset = int(offset_str)
            if offset < 0:
                offset = 0
            notes = notes[offset:]
        except ValueError:
            pass

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


def handle_get_notes_tags(query_params: dict | None = None):
    """GET /api/notes/tags — return all tags with counts."""
    query_params = query_params or {}
    notes = load_all_notes(include_archived=True)
    archived_mode = str(query_params.get("archived", ["exclude"])[0] or "exclude").strip().lower()
    if archived_mode == "only":
        notes = [n for n in notes if n.get("archived")]
    elif archived_mode != "include":
        notes = [n for n in notes if not n.get("archived")]

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
    notes = load_all_notes(include_archived=False)
    seen: set[str] = set()
    machines: list[str] = []
    for n in notes:
        m = n.get("machine", "")
        if m and m not in seen:
            seen.add(m)
            machines.append(m)
    return 200, {"machines": machines}


def apply_note_review_action(obj: dict, action: str, tags: list[str]) -> bool:
    salience_delta = {"promote": NOTE_SALIENCE_STEP, "demote": -NOTE_SALIENCE_STEP}
    changed = False

    if action == "pin":
        changed = not obj.get("pinned", False)
        obj["pinned"] = True
    elif action == "unpin":
        changed = obj.get("pinned", False)
        obj["pinned"] = False
    elif action == "archive":
        changed = not obj.get("archived", False)
        obj["archived"] = True
    elif action == "restore":
        changed = obj.get("archived", False)
        obj["archived"] = False
    elif action in salience_delta:
        salience = note_salience_value(obj.get("salience", 0.0))
        next_salience = clamp_note_salience(salience + salience_delta[action])
        if next_salience != salience:
            obj["salience"] = round(next_salience, 3)
            changed = True
    elif action == "retag":
        current = obj.get("topic_tags", [])
        if tags != current:
            obj["topic_tags"] = tags
            changed = True

    if changed:
        obj["review_updated_at"] = utc_now_iso()
    return changed


def parse_note_review_request(body: dict):
    note_id = str(body.get("note_id", "")).strip()
    if not note_id:
        return None, error_response(
            "INVALID_NOTE_ID",
            "Missing note id",
            "Send a non-empty 'note_id' field.",
        )

    action = str(body.get("action", "")).strip().lower()
    valid_actions = {"pin", "unpin", "archive", "restore", "promote", "demote", "retag"}
    if action not in valid_actions:
        return None, error_response(
            "INVALID_NOTE_ACTION",
            "Invalid note action",
            "Use one of: pin, unpin, archive, restore, promote, demote, retag.",
        )

    tags = []
    if action == "retag":
        tags = sanitize_note_tags(body.get("tags"))
        if tags is None:
            return None, error_response(
                "INVALID_TAGS",
                "Invalid tags payload",
                "Send 'tags' as an array of strings for retag actions.",
            )
    return {"note_id": note_id, "action": action, "tags": tags}, None


def rewrite_note_review_file(jsonl_path: Path, request: dict):
    raw_lines = jsonl_path.read_text(encoding="utf-8").splitlines()
    updated_lines: list[str] = []
    matched_note = None
    for line_no, raw_line in enumerate(raw_lines, start=1):
        line = raw_line.strip()
        if not line:
            updated_lines.append(raw_line)
            continue
        obj = json.loads(line)
        if not isinstance(obj, dict):
            updated_lines.append(raw_line)
            continue
        note_obj = clean_note_object(obj)
        row_id = note_row_id(jsonl_path, line_no, note_obj)
        if row_id != request["note_id"]:
            updated_lines.append(json.dumps(note_obj, ensure_ascii=False))
            continue
        changed = apply_note_review_action(note_obj, request["action"], request["tags"])
        updated_lines.append(json.dumps(note_obj, ensure_ascii=False))
        matched_note = normalize_note(note_obj, row_id)
        if changed:
            append_audit("notes.review", {"id": row_id, "action": request["action"], "source": jsonl_path.name})
    if matched_note is None:
        return None
    payload = "\n".join(updated_lines)
    atomic_write(jsonl_path, payload + "\n" if payload else "")
    return matched_note


def handle_post_note_review(body: dict):
    """POST /api/notes/review — mutate note review metadata."""
    request, err = parse_note_review_request(body)
    if err:
        return 400, err

    for jsonl_path in sorted(NOTES_DIR.glob("*.jsonl")):
        try:
            updated_note = rewrite_note_review_file(jsonl_path, request)
        except json.JSONDecodeError:
            continue
        except OSError:
            return 500, error_response(
                "WRITE_FAILED",
                "Failed to update note",
                "Check file permissions and retry.",
            )
        if not updated_note:
            continue

        return 200, {"ok": True, "note": updated_note}

    return 404, error_response(
        "NOTE_NOT_FOUND",
        "Note not found",
        "Refresh notes and retry the action.",
    )


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


def settings_error_code(field_name: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9]+", "_", field_name).strip("_").upper()
    return f"INVALID_{normalized}" if normalized else "INVALID_SETTINGS"


def parse_int_setting(value, field_name: str, minimum: int, maximum: int):
    if isinstance(value, bool) or not isinstance(value, int):
        return None, error_response(
            settings_error_code(field_name),
            f"Invalid {field_name}",
            f"Send {field_name} as an integer between {minimum} and {maximum}.",
        )
    if value < minimum or value > maximum:
        return None, error_response(
            settings_error_code(field_name),
            f"Invalid {field_name}",
            f"Send {field_name} between {minimum} and {maximum}.",
        )
    return value, None


def parse_string_setting(value, field_name: str):
    if not isinstance(value, str):
        return None, error_response(
            settings_error_code(field_name),
            f"Invalid {field_name}",
            f"Send {field_name} as a string.",
        )
    return value, None


def parse_llm_provider_patch(raw):
    if not isinstance(raw, dict):
        return None, error_response(
            "INVALID_LLM_PROVIDER",
            "Invalid llm_provider",
            "Send llm_provider as an object.",
        )
    allowed = {"endpoint", "api_key", "model", "provider"}
    patch = {}
    for key, value in raw.items():
        if key not in allowed:
            return None, error_response(
                "INVALID_LLM_PROVIDER_KEY",
                f"Invalid llm_provider field: {key}",
                "Allowed llm_provider fields: endpoint, api_key, model, provider.",
            )
        parsed, err = parse_string_setting(value, f"llm_provider.{key}")
        if err:
            return None, err
        patch[key] = parsed
    return patch, None


_ALLOWED_LLM_ROUTE_KEYS = {"session_notes", "now_md", "anchors"}


def _normalize_llm_route(value: str) -> str:
    v = value.strip().lower().replace(" ", "_")
    if v in {"claude", "claude-cli", "claude_cli"}:
        return "claude_cli"
    if v in {"claude-api", "claude_api"}:
        return "claude_api"
    return v


def parse_llm_routing_patch(raw):
    if not isinstance(raw, dict):
        return None, error_response(
            "INVALID_LLM_ROUTING",
            "Invalid llm_routing",
            "Send llm_routing as an object.",
        )
    patch = {}
    for key, value in raw.items():
        if key not in _ALLOWED_LLM_ROUTE_KEYS:
            return None, error_response(
                "INVALID_LLM_ROUTING_KEY",
                f"Invalid llm_routing field: {key}",
                "Allowed llm_routing fields: session_notes, now_md, anchors.",
            )
        parsed, err = parse_string_setting(value, f"llm_routing.{key}")
        if err:
            return None, err
        normalized = _normalize_llm_route(parsed)
        if normalized not in {"deepseek", "gemini", "claude_api", "claude_cli"}:
            return None, error_response(
                "INVALID_LLM_ROUTING_VALUE",
                f"Invalid llm_routing.{key}",
                "Allowed values: deepseek, gemini, claude_cli (or claude), claude_api.",
            )
        patch[key] = normalized
    return patch, None


def parse_claude_cli_patch(raw):
    if not isinstance(raw, dict):
        return None, error_response(
            "INVALID_CLAUDE_CLI",
            "Invalid claude_cli",
            "Send claude_cli as an object.",
        )
    allowed = {"command", "prompt_flag"}
    patch = {}
    for key, value in raw.items():
        if key not in allowed:
            return None, error_response(
                "INVALID_CLAUDE_CLI_KEY",
                f"Invalid claude_cli field: {key}",
                "Allowed claude_cli fields: command, prompt_flag.",
            )
        parsed, err = parse_string_setting(value, f"claude_cli.{key}")
        if err:
            return None, err
        if not parsed.strip():
            return None, error_response(
                settings_error_code(f"claude_cli.{key}"),
                f"Invalid claude_cli.{key}",
                f"Send claude_cli.{key} as a non-empty string.",
            )
        patch[key] = parsed
    return patch, None


def parse_daemon_patch(raw):
    if not isinstance(raw, dict):
        return None, error_response(
            "INVALID_DAEMON",
            "Invalid daemon settings",
            "Send daemon as an object.",
        )
    patch = {}
    for key, value in raw.items():
        if key == "enabled":
            if not isinstance(value, bool):
                return None, error_response(
                    "INVALID_DAEMON_ENABLED",
                    "Invalid daemon.enabled",
                    "Send daemon.enabled as true or false.",
                )
            patch[key] = value
            continue
        if key == "idle_threshold":
            parsed, err = parse_int_setting(value, "daemon_idle_threshold", 1, 86400)
            if err:
                return None, err
            patch[key] = parsed
            continue
        return None, error_response(
            "INVALID_DAEMON_KEY",
            f"Invalid daemon field: {key}",
            "Allowed daemon fields: enabled, idle_threshold.",
        )
    return patch, None


def parse_settings_patch(body: dict):
    allowed_keys = {
        "llm_provider",
        "llm_routing",
        "claude_cli",
        "token_budget",
        "daemon",
        "server_port",
        "data_dir",
    }
    patch = {}
    for key in body.keys():
        if key not in allowed_keys:
            return None, error_response(
                "INVALID_SETTINGS_KEY",
                f"Invalid settings field: {key}",
                "Allowed fields: llm_provider, llm_routing, claude_cli, token_budget, daemon, server_port, data_dir.",
            )

    if "token_budget" in body:
        parsed, err = parse_int_setting(body["token_budget"], "token_budget", 1, 10_000_000)
        if err:
            return None, err
        patch["token_budget"] = parsed

    if "server_port" in body:
        parsed, err = parse_int_setting(body["server_port"], "server_port", 1, 65535)
        if err:
            return None, err
        patch["server_port"] = parsed

    if "data_dir" in body:
        parsed, err = parse_string_setting(body["data_dir"], "data_dir")
        if err:
            return None, err
        patch["data_dir"] = parsed

    if "llm_provider" in body:
        parsed, err = parse_llm_provider_patch(body["llm_provider"])
        if err:
            return None, err
        patch["llm_provider"] = parsed

    if "llm_routing" in body:
        parsed, err = parse_llm_routing_patch(body["llm_routing"])
        if err:
            return None, err
        patch["llm_routing"] = parsed

    if "claude_cli" in body:
        parsed, err = parse_claude_cli_patch(body["claude_cli"])
        if err:
            return None, err
        patch["claude_cli"] = parsed

    if "daemon" in body:
        parsed, err = parse_daemon_patch(body["daemon"])
        if err:
            return None, err
        patch["daemon"] = parsed

    return patch, None


def handle_post_settings(body: dict):
    """POST /api/settings — validate and merge config updates."""
    patch, err = parse_settings_patch(body)
    if err:
        return 400, err

    config = load_config()

    for key in ("token_budget", "server_port", "data_dir"):
        if key in patch:
            config[key] = patch[key]

    if "llm_provider" in patch:
        llm_cfg = config.get("llm_provider", {})
        if not isinstance(llm_cfg, dict):
            llm_cfg = {}
        llm_cfg.update(patch["llm_provider"])
        config["llm_provider"] = llm_cfg

    if "llm_routing" in patch:
        routing_cfg = config.get("llm_routing", {})
        if not isinstance(routing_cfg, dict):
            routing_cfg = {}
        routing_cfg.update(patch["llm_routing"])
        config["llm_routing"] = routing_cfg

    if "claude_cli" in patch:
        cli_cfg = config.get("claude_cli", {})
        if not isinstance(cli_cfg, dict):
            cli_cfg = {}
        cli_cfg.update(patch["claude_cli"])
        config["claude_cli"] = cli_cfg

    if "daemon" in patch:
        daemon_cfg = config.get("daemon", {})
        if not isinstance(daemon_cfg, dict):
            daemon_cfg = {}
        daemon_cfg.update(patch["daemon"])
        config["daemon"] = daemon_cfg

    save_config(config)
    append_audit("settings.update", {"changed_keys": sorted(list(patch.keys()))})
    return 200, {"ok": True, "settings": config}


# -- Status ----------------------------------------------------------------


def get_daemon_status() -> dict:
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


def check_config_validity() -> dict:
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


def parse_iso_timestamp(value) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def latest_session_activity() -> datetime | None:
    """Return the modification time of the most recently changed session file."""
    if not SESSIONS_DIR.is_dir():
        return None

    latest = None
    for path in SESSIONS_DIR.glob("*.json"):
        if not path.is_file():
            continue
        try:
            dt = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        except OSError:
            continue
        if latest is None or dt > latest:
            latest = dt
    return latest


def daemon_health_snapshot(
    *,
    daemon_enabled: bool,
    daemon_status: dict,
    idle_threshold: int,
    last_note_dt: datetime | None,
    last_session_dt: datetime | None,
    note_count: int,
) -> dict:
    running = bool(daemon_status.get("running"))
    issues: list[str] = []
    actions: list[str] = []

    lag_threshold_seconds = max(600, max(60, idle_threshold) * 3)
    lag_seconds = None
    if last_session_dt is not None:
        if last_note_dt is not None:
            lag_seconds = int((last_session_dt - last_note_dt).total_seconds())
        elif note_count == 0:
            lag_seconds = int((datetime.now(timezone.utc) - last_session_dt).total_seconds())
        if lag_seconds is not None and lag_seconds < 0:
            lag_seconds = 0

    if daemon_enabled and not running:
        issues.append("daemon_not_running")
        actions.append("start_daemon_process")

    if daemon_enabled and lag_seconds is not None and lag_seconds > lag_threshold_seconds:
        issues.append("notes_lagging")
        actions.append("check_daemon_backlog")

    if daemon_enabled and note_count == 0 and last_session_dt is not None:
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
        "last_session_at": last_session_dt.isoformat() if last_session_dt else None,
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
                        dt = parse_iso_timestamp(obj.get("ts") or obj.get("first_ts"))
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

    daemon_status = get_daemon_status()
    daemon_running = bool(daemon_status.get("running"))
    last_session_dt = latest_session_activity()
    daemon_health = daemon_health_snapshot(
        daemon_enabled=daemon_enabled,
        daemon_status=daemon_status,
        idle_threshold=idle_threshold,
        last_note_dt=last_note_dt,
        last_session_dt=last_session_dt,
        note_count=note_count,
    )
    if (
        "notes_lagging" in daemon_health.get("issues", [])
        and last_session_dt is not None
    ):
        record_lag_incident(last_session_dt, daemon_health.get("lag_seconds"))

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
            if f.is_file() and not is_internal_context_artifact(f.name)
        )

    return 200, {
        "total_notes": note_count,
        "note_count": note_count,
        "total_sessions": session_count,
        "session_count": session_count,
        "last_session_date": last_session_date,
        "last_note_date": daemon_health.get("last_note_at"),
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


def note_generation_counts_by_day() -> dict[str, int]:
    counts: dict[str, int] = {}
    if not NOTES_DIR.is_dir():
        return counts
    for jsonl_path in NOTES_DIR.glob("*.jsonl"):
        try:
            with jsonl_path.open("r", encoding="utf-8") as fh:
                for raw_line in fh:
                    line = raw_line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if not isinstance(obj, dict):
                        continue
                    if str(obj.get("synthesis_level", "")).strip().lower() in {
                        "weekly",
                        "monthly",
                    }:
                        continue
                    dt = parse_iso_timestamp(obj.get("ts") or obj.get("first_ts"))
                    if not dt:
                        continue
                    key = dt.date().isoformat()
                    counts[key] = counts.get(key, 0) + 1
        except Exception:
            continue
    return counts


def lag_incidents_last_days(incidents: list[dict], days: int) -> list[dict]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=max(1, days))
    filtered = []
    for incident in incidents:
        if not isinstance(incident, dict):
            continue
        ts = parse_iso_timestamp(incident.get("ts"))
        if not ts:
            continue
        if ts >= cutoff:
            filtered.append(incident)
    return filtered


def handle_get_metrics():
    """GET /api/metrics — local reliability counters and time-series summaries."""
    metrics = load_reliability_metrics()
    by_day = note_generation_counts_by_day()
    today = datetime.now(timezone.utc).date()
    last_7_days = []
    for offset in range(6, -1, -1):
        day = today - timedelta(days=offset)
        day_key = day.isoformat()
        last_7_days.append({"date": day_key, "count": by_day.get(day_key, 0)})

    incidents = clean_lag_incidents(metrics.get("lag_incidents", []))
    incidents_7d = lag_incidents_last_days(incidents, 7)
    last_lag_at = incidents[-1]["ts"] if incidents else None

    return 200, {
        "notes_generated_today": by_day.get(today.isoformat(), 0),
        "notes_generated_last_7_days": last_7_days,
        "lag_incidents_total": len(incidents),
        "lag_incidents_7d": len(incidents_7d),
        "last_lag_incident_at": last_lag_at,
        "import": {
            "success": clean_counter(metrics.get("import", {}).get("success", 0)),
            "failure": clean_counter(metrics.get("import", {}).get("failure", 0)),
        },
        "export": {
            "success": clean_counter(metrics.get("export", {}).get("success", 0)),
            "failure": clean_counter(metrics.get("export", {}).get("failure", 0)),
        },
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
    config_health = check_config_validity()
    daemon = get_daemon_status()

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
        if is_internal_context_artifact(f.name):
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

    raw_depth = body.get("depth", 1)
    try:
        depth = int(raw_depth)
    except (TypeError, ValueError):
        return 400, error_response(
            "INVALID_DEPTH",
            "Invalid depth value",
            "Send depth as one of: -1, 0, 1, 2, 3.",
        )
    if depth not in (-1, 0, 1, 2, 3):
        return 400, error_response(
            "INVALID_DEPTH",
            "Invalid depth value",
            "Send depth as one of: -1, 0, 1, 2, 3.",
        )

    enabled = body.get("enabled", True)
    if not isinstance(enabled, bool):
        return 400, error_response(
            "INVALID_ENABLED",
            "Invalid enabled value",
            "Send enabled as a boolean true/false.",
        )

    config = load_config()
    context_files = config.get("context_files", [])
    if not isinstance(context_files, list):
        context_files = []

    # Update or insert
    found = False
    for cf in context_files:
        if not isinstance(cf, dict):
            continue
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


def build_export_zip() -> bytes:
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
        payload = build_export_zip()
    except Exception:
        increment_reliability_metric("export", "failure")
        return 500, error_response(
            "EXPORT_BUILD_FAILED",
            "Failed to build export archive",
            "Retry and check file permissions in the data directory.",
        )

    increment_reliability_metric("export", "success")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%SZ")
    filename = f"memorable-export-{stamp}.zip"
    return 200, {"filename": filename, "payload": payload}


def safe_archive_member_path(name: str) -> Path | None:
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


def import_zip_payload(payload: bytes) -> int:
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
            rel = safe_archive_member_path(member.filename)
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
        increment_reliability_metric("import", "failure")
        return 400, error_response(
            "CONFIRMATION_TOKEN_MISMATCH",
            "Confirmation token mismatch",
            f"Send X-Confirmation-Token exactly as '{IMPORT_CONFIRM_TOKEN}'.",
        )

    raw_length = handler.headers.get("Content-Length", "0")
    try:
        length = int(raw_length)
    except (TypeError, ValueError):
        increment_reliability_metric("import", "failure")
        return 400, error_response(
            "INVALID_CONTENT_LENGTH",
            "Invalid Content-Length header",
            "Send a valid numeric Content-Length header.",
        )
    if length <= 0:
        increment_reliability_metric("import", "failure")
        return 400, error_response(
            "EMPTY_BODY",
            "Empty body",
            "Upload a ZIP archive body.",
        )
    if length > MAX_IMPORT_SIZE:
        increment_reliability_metric("import", "failure")
        return 413, error_response(
            "IMPORT_TOO_LARGE",
            "Import archive too large",
            f"Reduce payload to <= {MAX_IMPORT_SIZE} bytes.",
        )

    payload = handler.rfile.read(length)
    try:
        restored_files = import_zip_payload(payload)
    except ValueError as e:
        increment_reliability_metric("import", "failure")
        return 400, error_response(
            "INVALID_IMPORT_ARCHIVE",
            str(e),
            "Upload a valid Memorable export ZIP archive.",
        )
    except Exception:
        increment_reliability_metric("import", "failure")
        return 500, error_response(
            "IMPORT_FAILED",
            "Failed to import archive",
            "Check file permissions and archive integrity, then retry.",
        )

    increment_reliability_metric("import", "success")
    append_audit(
        "data.import",
        {
            "restored_files": restored_files,
            "filename": str(handler.headers.get("X-Filename", "")).strip(),
        },
    )
    return 200, {"ok": True, "restored_files": restored_files}


def handle_post_regenerate_summary():
    """POST /api/regenerate-summary — force regenerate the rolling now.md summary."""
    try:
        from note_generator import generate_rolling_summary, get_config
        cfg = get_config()
        generate_rolling_summary(cfg, NOTES_DIR)
        return 200, {"ok": True, "message": "Rolling summary regenerated."}
    except Exception as e:
        return 500, error_response(
            "REGENERATE_FAILED",
            "Failed to regenerate summary",
            str(e),
        )


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
