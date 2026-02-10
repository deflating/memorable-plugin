#!/usr/bin/env python3
"""Memorable — HTTP server & API.

Serves the web UI and provides API endpoints for managing
seed files, session notes, settings, file uploads, and status.

Python 3 stdlib only. No external dependencies.
"""

import argparse
import json
import os
import shutil
import time
import uuid
from datetime import datetime, timezone
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse

# -- Paths -----------------------------------------------------------------

DATA_DIR = Path.home() / ".memorable" / "data"
SEEDS_DIR = DATA_DIR / "seeds"
NOTES_DIR = DATA_DIR / "notes"
SESSIONS_DIR = DATA_DIR / "sessions"
FILES_DIR = DATA_DIR / "files"
CONFIG_PATH = DATA_DIR / "config.json"

UI_DIR = Path(__file__).resolve().parent.parent / "ui"

CHARS_PER_TOKEN = 4
DEFAULT_PORT = 7777

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


# -- Notes -----------------------------------------------------------------


def load_all_notes() -> list[dict]:
    """Read all .jsonl files from the notes directory.

    Each line in each file is a JSON object.
    Returns a flat list of all note objects.
    """
    notes = []
    if not NOTES_DIR.is_dir():
        return notes

    for jsonl_path in sorted(NOTES_DIR.glob("*.jsonl")):
        try:
            text = jsonl_path.read_text(encoding="utf-8")
        except Exception:
            continue
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                notes.append(obj)
            except json.JSONDecodeError:
                continue
    return notes


def handle_get_notes(query_params: dict):
    """GET /api/notes — list session notes with optional search/sort/limit."""
    notes = load_all_notes()

    # Search filter
    search = query_params.get("search", [None])[0]
    if search:
        search_lower = search.lower()
        filtered = []
        for n in notes:
            note_text = n.get("note", "")
            tags = n.get("topic_tags", [])
            tag_str = " ".join(tags) if isinstance(tags, list) else ""
            if search_lower in note_text.lower() or search_lower in tag_str.lower():
                filtered.append(n)
        notes = filtered

    # Sort
    sort_by = query_params.get("sort", ["date"])[0]
    if sort_by == "salience":
        notes.sort(key=lambda n: n.get("salience", 0), reverse=True)
    else:
        # Default: sort by ts descending
        notes.sort(key=lambda n: n.get("ts", ""), reverse=True)

    # Limit
    limit_str = query_params.get("limit", [None])[0]
    if limit_str:
        try:
            limit = int(limit_str)
            notes = notes[:limit]
        except ValueError:
            pass

    return 200, {"notes": notes, "total": len(notes)}


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
                pass

        path.write_text(content, encoding="utf-8")
        written.append(safe)

    if not written:
        return 400, {"error": "No valid .md files to write"}

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
    return 200, {"ok": True, "settings": config}


# -- Status ----------------------------------------------------------------


def handle_get_status():
    """GET /api/status — dashboard data."""
    # Note count
    note_count = 0
    if NOTES_DIR.is_dir():
        for jsonl_path in NOTES_DIR.glob("*.jsonl"):
            try:
                text = jsonl_path.read_text(encoding="utf-8")
                note_count += sum(
                    1 for line in text.splitlines() if line.strip()
                )
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
    daemon_running = False
    pid_file = DATA_DIR / "daemon.pid"
    if pid_file.exists():
        try:
            pid = int(pid_file.read_text().strip())
            # Check if PID is alive
            os.kill(pid, 0)
            daemon_running = True
        except (ValueError, OSError, ProcessLookupError):
            daemon_running = False

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
        "note_count": note_count,
        "session_count": session_count,
        "last_session_date": last_session_date,
        "seeds_present": seeds_present,
        "daemon_running": daemon_running,
        "total_seed_tokens": total_tokens,
        "file_count": file_count,
        "data_dir": str(DATA_DIR),
    }


# -- Files -----------------------------------------------------------------


def handle_get_files():
    """GET /api/files — list uploaded context files with metadata."""
    files = []
    if not FILES_DIR.is_dir():
        return 200, {"files": files}

    for f in sorted(FILES_DIR.iterdir()):
        if not f.is_file():
            continue
        try:
            stat = f.stat()
            content = ""
            tokens = 0
            # Only estimate tokens for text files
            try:
                content = f.read_text(encoding="utf-8")
                tokens = estimate_tokens(content)
            except (UnicodeDecodeError, Exception):
                pass

            files.append({
                "name": f.name,
                "size": stat.st_size,
                "tokens": tokens,
                "modified": datetime.fromtimestamp(
                    stat.st_mtime, tz=timezone.utc
                ).isoformat(),
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


# -- Legacy endpoints ------------------------------------------------------


def handle_get_config():
    """GET /api/config — return full configuration (legacy + new)."""
    config = load_config()

    # Deployed seed files
    deployed = {}
    if SEEDS_DIR.is_dir():
        for f in sorted(SEEDS_DIR.glob("*.md")):
            try:
                content = f.read_text(encoding="utf-8")
                deployed[f.name] = {
                    "content": content,
                    "tokens": estimate_tokens(content),
                }
            except Exception:
                deployed[f.name] = {"content": "", "tokens": 0}

    # Profiles (legacy compat — check old location too)
    profiles = {}
    profiles_dir = DATA_DIR / "profiles"
    if profiles_dir.is_dir():
        for f in sorted(profiles_dir.glob("*.json")):
            try:
                profiles[f.stem] = json.loads(
                    f.read_text(encoding="utf-8")
                )
            except Exception:
                pass

    return 200, {
        "config": config,
        "deployed": deployed,
        "profiles": profiles,
    }


def handle_post_config(body: dict):
    """POST /api/config — save configuration."""
    config = body.get("config")
    if config is None:
        return 400, {"error": "Missing 'config' field"}

    save_config(config)

    # Also save profile data if provided
    profile_data = body.get("profile_data")
    if profile_data and isinstance(profile_data, dict):
        ensure_dirs()
        profiles_dir = DATA_DIR / "profiles"
        profiles_dir.mkdir(parents=True, exist_ok=True)
        for name, data in profile_data.items():
            safe_name = "".join(
                c for c in name if c.isalnum() or c in "-_"
            ).strip()
            if safe_name:
                path = profiles_dir / f"{safe_name}.json"
                path.write_text(
                    json.dumps(data, indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )

    return 200, {"ok": True}


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
                pass

        path.write_text(content, encoding="utf-8")
        deployed_files.append(safe)

    if not deployed_files:
        return 400, {"error": "No valid .md files to deploy"}

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

    return 200, {
        "ok": True,
        "stored": str(original_path),
        "tokens": estimate_tokens(content),
        "anchor_depth": depth,
        "status": "stored",
        "message": "Document stored. Use the processor to extract anchors.",
    }


def handle_get_budget():
    """GET /api/budget — return current token budget breakdown."""
    config = load_config()
    budget = config.get("token_budget", 200000)

    breakdown = []
    total_used = 0

    if SEEDS_DIR.is_dir():
        for f in sorted(SEEDS_DIR.glob("*.md")):
            try:
                content = f.read_text(encoding="utf-8")
                tokens = estimate_tokens(content)
                breakdown.append({
                    "file": f.name,
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
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Filename")
        self.end_headers()

    def read_body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
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

        if path == "/api/notes":
            status, data = handle_get_notes(query_params)
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

        if path == "/api/files":
            status, data = handle_get_files()
            return self.send_json(status, data)

        if path == "/api/config":
            status, data = handle_get_config()
            return self.send_json(status, data)

        if path == "/api/budget":
            status, data = handle_get_budget()
            return self.send_json(status, data)

        # --- Static files ---
        self.serve_static(path)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        if path == "/api/files/upload":
            status, data = handle_post_file_upload(self)
            return self.send_json(status, data)

        # For all other POST endpoints, read JSON body
        body = self.read_body()

        if path == "/api/seeds":
            status, data = handle_post_seeds(body)
            return self.send_json(status, data)

        if path == "/api/settings":
            status, data = handle_post_settings(body)
            return self.send_json(status, data)

        if path == "/api/config":
            status, data = handle_post_config(body)
            return self.send_json(status, data)

        if path == "/api/deploy":
            status, data = handle_post_deploy(body)
            return self.send_json(status, data)

        if path == "/api/process":
            status, data = handle_post_process(body)
            return self.send_json(status, data)

        self.send_json(404, {"error": "Not found"})

    def do_DELETE(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        if path.startswith("/api/files/"):
            filename = path[len("/api/files/"):]
            if filename:
                safe = "".join(
                    c for c in filename if c.isalnum() or c in "-_."
                ).strip()
                if safe:
                    file_path = FILES_DIR / safe
                    if file_path.is_file():
                        file_path.unlink()
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
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data)


# -- Entry point -----------------------------------------------------------


def run(port: int = DEFAULT_PORT):
    ensure_dirs()
    server = HTTPServer(("0.0.0.0", port), MemorableHandler)
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
