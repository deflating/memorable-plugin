#!/usr/bin/env python3
"""HTTP routing and server startup for Memorable."""

import json
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.parse import parse_qs, unquote, urlparse

from server_api import (
    handle_get_budget,
    handle_get_export,
    handle_get_files,
    handle_get_health,
    handle_get_machines,
    handle_get_notes,
    handle_get_notes_tags,
    handle_get_seeds,
    handle_get_session,
    handle_get_sessions,
    handle_get_settings,
    handle_get_status,
    handle_post_deploy,
    handle_post_file_upload,
    handle_post_process,
    handle_post_reset,
    handle_post_seeds,
    handle_post_settings,
    handle_preview_file,
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

    def read_body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        if length > MAX_UPLOAD_SIZE:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw.decode("utf-8"))
        except Exception:
            return {}

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        query_params = parse_qs(parsed.query)

        if path == "/api/notes":
            status, data = handle_get_notes(query_params)
            return self.send_json(status, data)

        if path == "/api/notes/tags":
            status, data = handle_get_notes_tags()
            return self.send_json(status, data)

        if path == "/api/machines":
            status, data = handle_get_machines()
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

        if path == "/api/files":
            status, data = handle_get_files()
            return self.send_json(status, data)

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

        self.serve_static(path)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        if path == "/api/files/upload":
            status, data = handle_post_file_upload(self)
            return self.send_json(status, data)

        if path.startswith("/api/files/") and path.endswith("/process"):
            filename = unquote(path[len("/api/files/"):-len("/process")])
            status, data = handle_process_file(filename)
            return self.send_json(status, data)

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

        self.send_json(
            404,
            error_response("NOT_FOUND", "Not found", "Check the endpoint path and method."),
        )

    def do_PUT(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        body = self.read_body()

        if path.startswith("/api/files/") and path.endswith("/depth"):
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

        if path.startswith("/api/files/"):
            filename = unquote(path[len("/api/files/"):])
            if filename:
                safe = "".join(c for c in filename if c.isalnum() or c in "-_.").strip()
                if safe:
                    file_path = FILES_DIR / safe
                    if file_path.is_file():
                        file_path.unlink()
                        anchored = FILES_DIR / (safe + ".anchored")
                        anchored_deleted = False
                        if anchored.is_file():
                            anchored.unlink()
                            anchored_deleted = True
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
