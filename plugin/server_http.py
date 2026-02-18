#!/usr/bin/env python3
"""HTTP routing and server startup for Memorable."""

import json
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.parse import parse_qs, unquote, urlparse

from server_api import (
    handle_get_budget,
    handle_get_deep_files,
    handle_get_deep_search,
    handle_get_export,
    handle_get_files,
    handle_get_file_levels,
    handle_get_health,
    handle_get_observations,
    handle_get_metrics,
    handle_get_machines,
    handle_get_notes,
    handle_get_notes_tags,
    handle_get_seeds,
    handle_get_session,
    handle_get_sessions,
    handle_get_settings,
    handle_get_status,
    handle_post_deploy,
    handle_post_deep_upload,
    handle_post_import,
    handle_post_file_upload,
    handle_post_regenerate_knowledge,
    handle_post_note_review,
    handle_post_process,
    handle_post_regenerate_summary,
    handle_post_reset,
    handle_post_seeds,
    handle_post_settings,
    handle_preview_file,
    handle_process_deep_file,
    handle_delete_deep_file,
    handle_process_file,
    handle_put_file_depth,
)
from server_storage import (
    DATA_DIR,
    DEFAULT_PORT,
    FILES_DIR,
    MAX_UPLOAD_SIZE,
    UI_DIR,
    append_audit,
    error_response,
    ensure_dirs,
    load_config,
    save_config,
)

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
LEVELS_FILE_SUFFIX = ".levels.json"
LEVEL_FILE_PREFIX = ".level"
LEVEL_FILE_SUFFIX = ".md"
FLOOR_FILE_SUFFIX = ".floor.md"
DELTA_FILE_PREFIX = ".delta"
DELTA_FILE_SUFFIX = ".md"


class MemorableHandler(SimpleHTTPRequestHandler):
    """Routes API requests and serves static files from the ui/ directory."""

    def log_message(self, format, *args):
        pass

    def send_json(self, status: int, data):
        body = json.dumps(data, ensure_ascii=False, default=str).encode("utf-8")
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

    def read_body(self):
        """Parse JSON body.

        Returns:
            (body: dict, err: tuple[int, dict] | None)
        """
        raw_length = self.headers.get("Content-Length", "0")
        try:
            length = int(raw_length)
        except (TypeError, ValueError):
            return None, (
                400,
                error_response(
                    "INVALID_CONTENT_LENGTH",
                    "Invalid Content-Length header",
                    "Send a valid numeric Content-Length header.",
                ),
            )
        if length < 0:
            return None, (
                400,
                error_response(
                    "INVALID_CONTENT_LENGTH",
                    "Invalid Content-Length header",
                    "Send a non-negative Content-Length header.",
                ),
            )
        if length == 0:
            return {}, None
        if length > MAX_UPLOAD_SIZE:
            return None, (
                413,
                error_response(
                    "UPLOAD_TOO_LARGE",
                    "Upload too large",
                    f"Reduce payload to <= {MAX_UPLOAD_SIZE} bytes.",
                ),
            )

        raw = self.rfile.read(length)
        try:
            body = json.loads(raw.decode("utf-8"))
        except Exception:
            return None, (
                400,
                error_response(
                    "INVALID_JSON",
                    "Invalid JSON",
                    "Send a valid JSON object.",
                ),
            )

        if not isinstance(body, dict):
            return None, (
                400,
                error_response(
                    "INVALID_JSON_OBJECT",
                    "JSON body must be an object",
                    "Send a JSON object payload.",
                ),
            )
        return body, None

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        query_params = parse_qs(parsed.query)

        if path == "/api/notes":
            status, data = handle_get_notes(query_params)
            return self.send_json(status, data)

        if path == "/api/notes/tags":
            status, data = handle_get_notes_tags(query_params)
            return self.send_json(status, data)

        if path == "/api/machines":
            status, data = handle_get_machines()
            return self.send_json(status, data)

        if path == "/api/metrics":
            status, data = handle_get_metrics()
            return self.send_json(status, data)

        if path == "/api/sessions":
            status, data = handle_get_sessions(query_params)
            return self.send_json(status, data)

        if path.startswith("/api/sessions/"):
            session_id = unquote(path[len("/api/sessions/"):])
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

        if path == "/api/observations":
            status, data = handle_get_observations()
            return self.send_json(status, data)

        if path == "/api/deep/files":
            status, data = handle_get_deep_files()
            return self.send_json(status, data)

        if path == "/api/deep/search":
            status, data = handle_get_deep_search(query_params)
            return self.send_json(status, data)

        if path == "/api/files":
            status, data = handle_get_files()
            return self.send_json(status, data)

        if path.startswith("/api/files/") and path.endswith("/preview"):
            filename = unquote(path[len("/api/files/"):-len("/preview")])
            status, data = handle_preview_file(filename, query_params)
            return self.send_json(status, data)

        if path.startswith("/api/files/") and path.endswith("/levels"):
            filename = unquote(path[len("/api/files/"):-len("/levels")])
            status, data = handle_get_file_levels(filename)
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

        self.serve_static(path)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        if path == "/api/regenerate-summary":
            status, data = handle_post_regenerate_summary()
            return self.send_json(status, data)

        if path == "/api/regenerate-knowledge":
            status, data = handle_post_regenerate_knowledge()
            return self.send_json(status, data)

        if path == "/api/files/upload":
            status, data = handle_post_file_upload(self)
            return self.send_json(status, data)

        if path == "/api/deep/files/upload":
            status, data = handle_post_deep_upload(self)
            return self.send_json(status, data)

        if path == "/api/import":
            status, data = handle_post_import(self)
            return self.send_json(status, data)

        if path.startswith("/api/files/") and path.endswith("/process"):
            filename = unquote(path[len("/api/files/"):-len("/process")])
            status, data = handle_process_file(filename)
            return self.send_json(status, data)

        if path.startswith("/api/deep/files/") and path.endswith("/process"):
            filename = unquote(path[len("/api/deep/files/"):-len("/process")])
            status, data = handle_process_deep_file(filename)
            return self.send_json(status, data)

        body_routes = {
            "/api/seeds",
            "/api/settings",
            "/api/deploy",
            "/api/process",
            "/api/reset",
            "/api/notes/review",
        }
        if path not in body_routes:
            return self.send_json(
                404,
                error_response("NOT_FOUND", "Not found", "Check the endpoint path and method."),
            )

        body, err = self.read_body()
        if err:
            status, payload = err
            return self.send_json(status, payload)

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

        if path == "/api/notes/review":
            status, data = handle_post_note_review(body)
            return self.send_json(status, data)

        self.send_json(
            404,
            error_response("NOT_FOUND", "Not found", "Check the endpoint path and method."),
        )

    def do_PUT(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        if path.startswith("/api/files/") and path.endswith("/depth"):
            body, err = self.read_body()
            if err:
                status, payload = err
                return self.send_json(status, payload)
            filename = unquote(path[len("/api/files/"):-len("/depth")])
            status, data = handle_put_file_depth(filename, body)
            return self.send_json(status, data)

        self.send_json(
            404,
            error_response("NOT_FOUND", "Not found", "Check the endpoint path and method."),
        )

    def do_DELETE(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        if path.startswith("/api/deep/files/"):
            filename = unquote(path[len("/api/deep/files/"):])
            status, data = handle_delete_deep_file(filename)
            return self.send_json(status, data)

        if path.startswith("/api/files/"):
            filename = unquote(path[len("/api/files/"):])
            if filename:
                safe = "".join(c for c in filename if c.isalnum() or c in "-_.").strip()
                if safe:
                    file_path = FILES_DIR / safe
                    if file_path.is_file():
                        file_path.unlink()
                        levels_file = FILES_DIR / (safe + LEVELS_FILE_SUFFIX)
                        levels_deleted = False
                        if levels_file.is_file():
                            levels_file.unlink()
                            levels_deleted = True
                        sidecar_deleted = 0
                        for sidecar in FILES_DIR.glob(f"{safe}{LEVEL_FILE_PREFIX}*{LEVEL_FILE_SUFFIX}"):
                            if not sidecar.is_file():
                                continue
                            try:
                                sidecar.unlink()
                                sidecar_deleted += 1
                            except OSError:
                                pass
                        floor_path = FILES_DIR / f"{safe}{FLOOR_FILE_SUFFIX}"
                        if floor_path.is_file():
                            try:
                                floor_path.unlink()
                                sidecar_deleted += 1
                            except OSError:
                                pass
                        for sidecar in FILES_DIR.glob(f"{safe}{DELTA_FILE_PREFIX}*{DELTA_FILE_SUFFIX}"):
                            if not sidecar.is_file():
                                continue
                            try:
                                sidecar.unlink()
                                sidecar_deleted += 1
                            except OSError:
                                pass
                        config = load_config()
                        cf = config.get("context_files", [])
                        config["context_files"] = [
                            f for f in cf if f.get("filename") != safe
                        ]
                        save_config(config)
                        append_audit(
                            "files.delete",
                            {
                                "filename": safe,
                                "levels_deleted": levels_deleted,
                                "level_sidecars_deleted": sidecar_deleted,
                            },
                        )
                        return self.send_json(
                            200,
                            {
                                "ok": True,
                                "deleted": safe,
                                "levels_deleted": levels_deleted,
                                "level_sidecars_deleted": sidecar_deleted,
                            },
                        )
            return self.send_json(
                404,
                error_response(
                    "FILE_NOT_FOUND",
                    "File not found",
                    "Check the filename and try again.",
                ),
            )

        self.send_json(
            404,
            error_response("NOT_FOUND", "Not found", "Check the endpoint path and method."),
        )

    def serve_static(self, url_path: str):
        """Serve a file from the UI directory."""
        if url_path in ("/", ""):
            url_path = "/index.html"

        rel = url_path.lstrip("/")
        file_path = (UI_DIR / rel).resolve()

        if not str(file_path).startswith(str(UI_DIR.resolve())):
            self.send_error(403, "Forbidden")
            return

        if not file_path.is_file():
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
