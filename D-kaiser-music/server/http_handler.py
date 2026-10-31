#!/usr/bin/env python3
"""HTTP 请求处理器"""
import os, json
from http.server import BaseHTTPRequestHandler
from config import log_queue
from server import routes
from server.log_stream import stream_logs

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC_DIR = os.path.join(BASE_DIR, "static")


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _json(self, d, c=200):
        self.send_response(c)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(d, ensure_ascii=False).encode())

    def _body(self):
        l = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(l)) if l else {}

    def _serve_file(self, path, ctype):
        try:
            with open(path, "rb") as f:
                data = f.read()
            self.send_response(200)
            self.send_header("Content-Type", f"{ctype}; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except FileNotFoundError:
            self.send_error(404)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self._serve_file(os.path.join(STATIC_DIR, "index.html"), "text/html")
        elif self.path.startswith("/css/") or self.path.startswith("/js/"):
            fp = os.path.join(STATIC_DIR, self.path.lstrip("/"))
            fp = os.path.normpath(fp)
            if not fp.startswith(STATIC_DIR):
                self.send_error(403)
                return
            ct = "text/css" if fp.endswith(".css") else "application/javascript"
            self._serve_file(fp, ct)
        elif self.path == "/api/logs-stream":
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            stream_logs(self.wfile, log_queue)
        elif self.path == "/api/dl-status":
            self._json(routes.handle_dl_status())
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path == "/api/search":
            self._json(routes.handle_search(self._body()))
        elif self.path == "/api/download":
            self._json(routes.handle_download(self._body()))
        elif self.path == "/api/preview":
            self._json(routes.handle_preview(self._body()))
        elif self.path == "/api/lyric":
            self._json(routes.handle_lyric(self._body()))
        elif self.path == "/api/cookie":
            self._json(routes.handle_cookie(self._body()))
        elif self.path == "/api/dl-remove":
            self._json(routes.handle_dl_remove(self._body()))
        elif self.path == "/api/dl-clear":
            self._json(routes.handle_dl_clear(self._body()))
        else:
            self.send_error(404)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()