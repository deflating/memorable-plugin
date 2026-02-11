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

# -- Paths -----------------------------------------------------------------

DATA_DIR = Path.home() / ".memorable" / "data"
SEEDS_DIR = DATA_DIR / "seeds"
NOTES_DIR = DATA_DIR / "notes"
SESSIONS_DIR = DATA_DIR / "sessions"
FILES_DIR = DATA_DIR / "files"
CONFIG_PATH = DATA_DIR / "config.json"
AUDIT_LOG_PATH = DATA_DIR / "audit.log"

UI_DIR = Path(__file__).resolve().parent.parent / "ui"

CHARS_PER_TOKEN = 4
DEFAULT_PORT = 7777
MAX_UPLOAD_SIZE = 10 * 1024 * 1024

DEFAULT_CONFIG = {
    "llm_provider": {
        "endpoint": "https://api.deepseek.com/v1",
        "api_key": "",
        "model": "deepseek-chat",
    },
    "token_budget": 200000,
    "daemon": {
        "enabled": False,
        "idle_threshold": 300,
    },
    "server_port": DEFAULT_PORT,
}


# -- Data helpers ----------------------------------------------------------


def ensure_dirs():
    """Create all required directories if they don't exist."""
    for d in [DATA_DIR, SEEDS_DIR, NOTES_DIR, SESSIONS_DIR, FILES_DIR]:
        d.mkdir(parents=True, exist_ok=True)


def load_config() -> dict:
    """Load config.json, returning defaults on any error."""
    try:
        if CONFIG_PATH.exists():
            data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            # Merge with defaults so new keys are always present
            merged = dict(DEFAULT_CONFIG)
            merged.update(data)
            return merged
    except Exception:
        pass
    return dict(DEFAULT_CONFIG)


def save_config(config: dict):
    """Write config.json atomically."""
    ensure_dirs()
    tmp = CONFIG_PATH.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    tmp.rename(CONFIG_PATH)


def estimate_tokens(text: str) -> int:
    return len(text) // CHARS_PER_TOKEN


def append_audit(event: str, details: dict | None = None):
    """Append a JSONL audit event. Best-effort only."""
    try:
        ensure_dirs()
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "event": event,
            "details": details or {},
        }
        with AUDIT_LOG_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
    except Exception:
        pass


# -- Notes -----------------------------------------------------------------


def _normalize_note(obj: dict) -> dict:
    """Map raw JSONL note fields to the shape the UI expects.

    JSONL has: ts, session, note, topic_tags, salience, ...
    UI wants:  date, summary, content, tags, salience, session
    """
    note_text = obj.get("note", "")
    # Extract first meaningful line as summary
    summary = ""
    for line in note_text.splitlines():
        stripped = line.strip().lstrip("#").strip()
        if stripped and stripped.lower() != "summary":
            summary = stripped
            break

    return {
        "date": obj.get("ts", ""),
        "summary": summary,
        "content": note_text,
        "tags": obj.get("topic_tags", []),
        "salience": obj.get("salience", 0),
        "session": obj.get("session", ""),
        "machine": obj.get("machine", ""),
        "message_count": obj.get("message_count", 0),
    }


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
                        notes.append(_normalize_note(obj))
                    except json.JSONDecodeError:
                        continue
        except Exception:
            continue
    return notes


def handle_get_notes(query_params: dict):
    """GET /api/notes — list session notes with optional search/sort/limit/tag/machine."""
    notes = load_all_notes()

    # Tag filter
    tag = query_params.get("tag", [None])[0]
    if tag:
        notes = [n for n in notes if tag in n.get("tags", [])]

    # Machine filter
    machine = query_params.get("machine", [None])[0]
    if machine:
        notes = [n for n in notes if n.get("machine", "") == machine]

    # Search filter
    search = query_params.get("search", [None])[0]
    if search:
        search_lower = search.lower()
        filtered = []
        for n in notes:
            text = n.get("content", "")
            tags = n.get("tags", [])
            tag_str = " ".join(tags) if isinstance(tags, list) else ""
            if search_lower in text.lower() or search_lower in tag_str.lower():
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
            notes = notes[int(offset_str):]
        except ValueError:
            pass

    # Limit
    limit_str = query_params.get("limit", [None])[0]
    if limit_str:
        try:
            notes = notes[:int(limit_str)]
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
        return 404, {"error": "Session not found"}

    for json_path in SESSIONS_DIR.glob("*.json"):
        if json_path.parent != SESSIONS_DIR:
            continue
        try:
            obj = json.loads(json_path.read_text(encoding="utf-8"))
            if obj.get("id") == session_id:
                return 200, obj
        except Exception:
            continue

    return 404, {"error": "Session not found"}


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
        return 400, {"error": "Missing or invalid 'files' field"}

    ensure_dirs()
    written = []

    for filename, content in files.items():
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
                return 500, {"error": f"Backup failed for {safe}, aborting write"}

        path.write_text(content, encoding="utf-8")
        written.append(safe)

    if not written:
        return 400, {"error": "No valid .md files to write"}

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


def handle_get_status():
    """GET /api/status — dashboard data."""
    # Note count
    note_count = 0
    if NOTES_DIR.is_dir():
        for jsonl_path in NOTES_DIR.glob("*.jsonl"):
            try:
                with jsonl_path.open("r", encoding="utf-8") as fh:
                    note_count += sum(1 for line in fh if line.strip())
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

    # Daemon running — check for PID file
    daemon_running = _get_daemon_status()["running"]

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
        file_count = sum(1 for f in FILES_DIR.iterdir() if f.is_file())

    return 200, {
        "total_notes": note_count,
        "note_count": note_count,
        "total_sessions": session_count,
        "session_count": session_count,
        "last_session_date": last_session_date,
        "seeds_present": seeds_present,
        "daemon_running": daemon_running,
        "total_seed_tokens": total_tokens,
        "file_count": file_count,
        "data_dir": str(DATA_DIR),
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
        # Skip .anchored companion files
        if f.name.endswith(".anchored"):
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

    if "application/json" in content_type:
        length = int(handler.headers.get("Content-Length", 0))
        if length == 0:
            return 400, {"error": "Empty body"}
        if length > MAX_UPLOAD_SIZE:
            return 413, {"error": "Upload too large"}
        raw = handler.rfile.read(length)
        try:
            body = json.loads(raw)
        except json.JSONDecodeError:
            return 400, {"error": "Invalid JSON"}

        filename = body.get("filename", "")
        content = body.get("content", "")

        if not filename or not content:
            return 400, {"error": "Missing 'filename' or 'content'"}

        # Sanitize filename
        safe = "".join(
            c for c in filename if c.isalnum() or c in "-_."
        ).strip()
        if not safe:
            safe = f"upload-{uuid.uuid4().hex[:8]}.txt"

        path = FILES_DIR / safe
        path.write_text(content, encoding="utf-8")
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
        length = int(handler.headers.get("Content-Length", 0))
        if length == 0:
            return 400, {"error": "Empty body"}
        if length > MAX_UPLOAD_SIZE:
            return 413, {"error": "Upload too large"}

        raw = handler.rfile.read(length)

        safe = ""
        if filename:
            safe = "".join(
                c for c in filename if c.isalnum() or c in "-_."
            ).strip()
        if not safe:
            safe = f"upload-{uuid.uuid4().hex[:8]}.bin"

        path = FILES_DIR / safe
        path.write_bytes(raw)
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
        return 400, {"error": "Invalid filename"}

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
        return 400, {"error": "Invalid filename"}

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
        return 404, {"error": "File not found"}

    return 200, {
        "content": content,
        "tokens": estimate_tokens(content),
        "depth": depth,
    }


def handle_put_file_depth(filename: str, body: dict):
    """PUT /api/files/<filename>/depth — set loading depth + enabled."""
    safe = "".join(c for c in filename if c.isalnum() or c in "-_.").strip()
    if not safe:
        return 400, {"error": "Invalid filename"}

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
        return 400, {
            "error": "Missing or invalid 'files' field. Expected {filename: content}"
        }

    ensure_dirs()
    deployed_files = []

    for filename, content in files.items():
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
                return 500, {"error": f"Backup failed for {safe}, aborting write"}

        path.write_text(content, encoding="utf-8")
        deployed_files.append(safe)

    if not deployed_files:
        return 400, {"error": "No valid .md files to deploy"}

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

    if not content:
        return 400, {"error": "Missing 'content' field"}

    ensure_dirs()

    safe_name = (
        "".join(c for c in filename if c.isalnum() or c in "-_.").strip()
        or "document.md"
    )
    original_path = FILES_DIR / f"original_{safe_name}"
    original_path.write_text(content, encoding="utf-8")
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
        return 500, {"error": "Failed to build export archive"}

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%SZ")
    filename = f"memorable-export-{stamp}.zip"
    return 200, {"filename": filename, "payload": payload}


def handle_post_reset(body: dict):
    """POST /api/reset — wipe DATA_DIR contents after explicit confirmation."""
    token = str(body.get("confirmation_token", "")).strip()
    if token != "RESET":
        return 400, {
            "error": "Confirmation token mismatch",
            "expected": "RESET",
        }

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
        return 500, {
            "error": "Reset partially failed",
            "removed": removed,
            "failed": failed,
        }

    append_audit("data.reset", {"removed_count": len(removed)})
    return 200, {"ok": True, "removed_count": len(removed)}


# -- Request handler -------------------------------------------------------

CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
    ".woff": "font/woff",
    ".woff2": "font/woff2",
    ".ttf": "font/ttf",
    ".map": "application/json",
}


class MemorableHandler(SimpleHTTPRequestHandler):
    """Routes API requests and serves static files from the ui/ directory."""

    def log_message(self, format, *args):
        pass

    def send_json(self, status: int, data):
        body = json.dumps(data, ensure_ascii=False, default=str).encode(
            "utf-8"
        )
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_bytes(
        self,
        status: int,
        payload: bytes,
        content_type: str,
        filename=None,
    ):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        if filename:
            self.send_header(
                "Content-Disposition",
                f'attachment; filename="{filename}"',
            )
        self.end_headers()
        self.wfile.write(payload)

    def do_OPTIONS(self):
        self.send_response(204)
        self.end_headers()

    def read_body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        if length > MAX_UPLOAD_SIZE:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        query_params = parse_qs(parsed.query)

        # --- API routes ---

        if path == "/api/notes/tags":
            status, data = handle_get_notes_tags()
            return self.send_json(status, data)

        if path == "/api/notes":
            status, data = handle_get_notes(query_params)
            return self.send_json(status, data)

        if path == "/api/machines":
            status, data = handle_get_machines()
            return self.send_json(status, data)

        if path == "/api/sessions":
            status, data = handle_get_sessions(query_params)
            return self.send_json(status, data)

        if path.startswith("/api/sessions/"):
            session_id = path[len("/api/sessions/"):]
            if session_id:
                status, data = handle_get_session(session_id)
                return self.send_json(status, data)

        if path == "/api/seeds":
            status, data = handle_get_seeds()
            return self.send_json(status, data)

        if path == "/api/settings":
            status, data = handle_get_settings()
            return self.send_json(status, data)

        if path == "/api/status":
            status, data = handle_get_status()
            return self.send_json(status, data)

        if path == "/api/health":
            status, data = handle_get_health()
            return self.send_json(status, data)

        if path == "/api/files":
            status, data = handle_get_files()
            return self.send_json(status, data)

        # GET /api/files/<filename>/preview?depth=N
        if path.startswith("/api/files/") and path.endswith("/preview"):
            filename = unquote(path[len("/api/files/"):-len("/preview")])
            status, data = handle_preview_file(filename, query_params)
            return self.send_json(status, data)

        if path == "/api/budget":
            status, data = handle_get_budget()
            return self.send_json(status, data)

        if path == "/api/export":
            status, data = handle_get_export()
            if status != 200:
                return self.send_json(status, data)
            return self.send_bytes(
                status=200,
                payload=data["payload"],
                content_type="application/zip",
                filename=data["filename"],
            )

        # --- Static files ---
        self.serve_static(path)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        if path == "/api/files/upload":
            status, data = handle_post_file_upload(self)
            return self.send_json(status, data)

        # POST /api/files/<filename>/process
        if path.startswith("/api/files/") and path.endswith("/process"):
            filename = unquote(path[len("/api/files/"):-len("/process")])
            status, data = handle_process_file(filename)
            return self.send_json(status, data)

        # For all other POST endpoints, read JSON body
        body = self.read_body()

        if path == "/api/seeds":
            status, data = handle_post_seeds(body)
            return self.send_json(status, data)

        if path == "/api/settings":
            status, data = handle_post_settings(body)
            return self.send_json(status, data)

        if path == "/api/deploy":
            status, data = handle_post_deploy(body)
            return self.send_json(status, data)

        if path == "/api/process":
            status, data = handle_post_process(body)
            return self.send_json(status, data)

        if path == "/api/reset":
            status, data = handle_post_reset(body)
            return self.send_json(status, data)

        self.send_json(404, {"error": "Not found"})

    def do_PUT(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        body = self.read_body()

        # PUT /api/files/<filename>/depth
        if path.startswith("/api/files/") and path.endswith("/depth"):
            filename = unquote(path[len("/api/files/"):-len("/depth")])
            status, data = handle_put_file_depth(filename, body)
            return self.send_json(status, data)

        self.send_json(404, {"error": "Not found"})

    def do_DELETE(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        if path.startswith("/api/files/"):
            filename = unquote(path[len("/api/files/"):])
            if filename:
                safe = "".join(
                    c for c in filename if c.isalnum() or c in "-_."
                ).strip()
                if safe:
                    file_path = FILES_DIR / safe
                    if file_path.is_file():
                        file_path.unlink()
                        # Also delete .anchored companion
                        anchored = FILES_DIR / (safe + ".anchored")
                        anchored_deleted = False
                        if anchored.is_file():
                            anchored.unlink()
                            anchored_deleted = True
                        # Remove from context_files config
                        config = load_config()
                        cf = config.get("context_files", [])
                        config["context_files"] = [
                            f for f in cf if f.get("filename") != safe
                        ]
                        save_config(config)
                        append_audit(
                            "files.delete",
                            {"filename": safe, "anchored_deleted": anchored_deleted},
                        )
                        return self.send_json(200, {"ok": True, "deleted": safe})
            return self.send_json(404, {"error": "File not found"})

        self.send_json(404, {"error": "Not found"})

    def serve_static(self, url_path: str):
        """Serve a file from the UI directory."""
        if url_path in ("/", ""):
            url_path = "/index.html"

        rel = url_path.lstrip("/")
        file_path = (UI_DIR / rel).resolve()

        # Path traversal protection
        if not str(file_path).startswith(str(UI_DIR.resolve())):
            self.send_error(403, "Forbidden")
            return

        if not file_path.is_file():
            # SPA fallback
            index = UI_DIR / "index.html"
            if index.is_file():
                file_path = index
            else:
                self.send_error(404, "Not found")
                return

        ext = file_path.suffix.lower()
        content_type = CONTENT_TYPES.get(ext, "application/octet-stream")

        try:
            data = file_path.read_bytes()
        except Exception:
            self.send_error(500, "Internal server error")
            return

        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(data)


# -- Entry point -----------------------------------------------------------


def run(port: int = DEFAULT_PORT):
    ensure_dirs()
    server = ThreadingHTTPServer(("127.0.0.1", port), MemorableHandler)
    print(f"Memorable running at http://localhost:{port}")
    print(f"Data directory: {DATA_DIR}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.server_close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Memorable server")
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help=f"Port (default: {DEFAULT_PORT})",
    )
    args = parser.parse_args()
    run(port=args.port)
