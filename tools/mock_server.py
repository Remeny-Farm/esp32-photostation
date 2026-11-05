#!/usr/bin/env python3
"""Local mock of the esp32-photostation upload endpoint (docs/protocol.md).

Usage: python3 tools/mock_server.py --port 8787 --key <device-key> --store <dir>
"""
import argparse
import hmac
import json
import os
import re
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

MAX_PHOTO_BYTES = 1048576
VISIT_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
MAX_JSON_BYTES = 1048576


def _write_atomic(path, data):
    tmp = "%s.tmp.%d.%d" % (path, os.getpid(), threading.get_ident())
    with open(tmp, "wb") as f:
        f.write(data)
    os.replace(tmp, path)


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):  # replaced by _finish's one-line log
        pass

    # -- helpers ---------------------------------------------------------
    def _send(self, status, obj, close=False):
        payload = json.dumps(obj).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        if close:
            self.send_header("Connection", "close")
            self.close_connection = True
        self.end_headers()
        self.wfile.write(payload)
        if not self.server.quiet:
            print("%s %s %d %d" % (self.command, self.path, status, self._body_len),
                  file=sys.stderr, flush=True)

    def _err(self, status, code, close=False):
        self._send(status, {"ok": False, "error": code}, close=close)

    def _content_length(self):
        raw = self.headers.get("Content-Length")
        if raw is None:
            return 0  # no body
        raw = raw.strip()
        if not (raw.isascii() and raw.isdigit()):  # isdigit() alone accepts non-ASCII digits
            return None
        return int(raw)

    def _drain(self, length):
        while length > 0:
            chunk = self.rfile.read(min(length, 65536))
            if not chunk:
                break
            length -= len(chunk)

    def _too_large(self, length, limit):
        """Answer 413 and return True when the body exceeds limit."""
        if length <= limit:
            return False
        self._drain(length)  # discard in chunks so the client sees a clean 413
        self._err(413, "too_large")
        return True

    def _read_json(self, length):
        try:
            obj = json.loads(self.rfile.read(length) or b"null")
        except (ValueError, UnicodeDecodeError):
            return None
        return obj if isinstance(obj, dict) else None

    # -- routing ---------------------------------------------------------
    def do_POST(self):
        self._body_len = 0
        path = self.path.split("?", 1)[0]
        length = self._content_length()
        if length is None:
            return self._err(400, "bad_content_length", close=True)
        self._body_len = length

        if path == "/__mode":
            return self._mode(length)
        if path not in ("/api/photostation/photo", "/api/photostation/visit",
                        "/api/photostation/heartbeat"):
            self._drain(length)
            return self._err(404, "not_found")

        if self.server.take_failure():
            self._drain(length)
            return self._err(503, "unavailable")

        auth = self.headers.get("Authorization", "")
        scheme, _, token = auth.partition(" ")
        if scheme != "Bearer" or not hmac.compare_digest(
                token.encode(), self.server.key.encode()):
            self._drain(length)
            return self._err(401, "unauthorized")

        if path.endswith("/photo"):
            return self._photo(length)
        if path.endswith("/visit"):
            return self._visit(length)
        return self._heartbeat(length)

    def _mode(self, length):
        if self._too_large(length, MAX_JSON_BYTES):
            return
        obj = self._read_json(length)
        fail = obj.get("fail") if obj else None
        if not isinstance(fail, int) or isinstance(fail, bool) or fail < 0:
            return self._err(400, "bad_request")
        self.server.set_failures(fail)
        self._send(200, {"ok": True, "fail": fail})

    def _photo(self, length):
        ctype = self.headers.get("Content-Type", "").split(";")[0].strip().lower()
        if ctype != "image/jpeg":
            self._drain(length)
            return self._err(415, "unsupported_media_type")
        visit = self.headers.get("X-Visit-Id", "")
        n_raw = self.headers.get("X-Photo-N", "")
        if not (n_raw.isascii() and n_raw.isdigit() and 1 <= int(n_raw) <= 5) \
                or not VISIT_ID_RE.match(visit):
            self._drain(length)
            return self._err(400, "bad_request")
        if self._too_large(length, MAX_PHOTO_BYTES):
            return
        body = self.rfile.read(length)
        if body[:2] != b"\xff\xd8":
            return self._err(422, "not_jpeg")
        n = int(n_raw)
        vdir = os.path.join(self.server.store, visit)
        os.makedirs(vdir, exist_ok=True)
        target = os.path.join(vdir, "%d.jpg" % n)
        with self.server.lock:
            existed = os.path.exists(target)
            if not existed:
                _write_atomic(target, body)
        self._send(200 if existed else 201, {"ok": True, "visit_id": visit, "n": n})

    def _visit(self, length):
        if self._too_large(length, MAX_JSON_BYTES):
            return
        obj = self._read_json(length)
        visit = obj.get("visit_id") if obj else None
        photos = obj.get("photos", []) if obj else None
        if not isinstance(visit, str) or not VISIT_ID_RE.match(visit) \
                or not isinstance(photos, list):
            return self._err(400, "bad_request")
        listed = []
        for p in photos:
            n = p.get("n") if isinstance(p, dict) else None
            if not isinstance(n, int) or isinstance(n, bool) or not 1 <= n <= 5:
                return self._err(422, "bad_photos")
            listed.append(n)
        vdir = os.path.join(self.server.store, visit)
        os.makedirs(vdir, exist_ok=True)
        target = os.path.join(vdir, "visit.json")
        with self.server.lock:
            existed = os.path.exists(target)
            if not existed:
                _write_atomic(target, json.dumps(obj, indent=2).encode())
        # Recomputed on every call so a repeat shows photos that arrived later.
        incomplete = any(not os.path.exists(os.path.join(vdir, "%d.jpg" % n)) for n in listed)
        self._send(200 if existed else 201,
                   {"ok": True, "visit_id": visit, "incomplete": incomplete})

    def _heartbeat(self, length):
        if self._too_large(length, MAX_JSON_BYTES):
            return
        obj = self._read_json(length)
        if obj is None:
            return self._err(400, "bad_request")
        line = (json.dumps(obj) + "\n").encode()
        with self.server.lock:
            with open(os.path.join(self.server.store, "heartbeat.jsonl"), "ab") as f:
                f.write(line)
        self._send(200, {"ok": True})


class MockServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, addr, key, store, quiet):
        super().__init__(addr, Handler)
        self.key = key
        self.store = store
        self.quiet = quiet
        self.lock = threading.Lock()
        self._fail = 0

    def set_failures(self, n):
        with self.lock:
            self._fail = n

    def take_failure(self):
        with self.lock:
            if self._fail > 0:
                self._fail -= 1
                return True
            return False


def make_server(port, key, store, quiet=False, host="127.0.0.1"):
    os.makedirs(store, exist_ok=True)
    return MockServer((host, port), key, store, quiet)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--port", type=int, default=8787)
    ap.add_argument("--key", required=True)
    ap.add_argument("--store", required=True)
    ap.add_argument("--host", default="127.0.0.1",
                    help="bind address; use 0.0.0.0 so a board on the LAN can reach it")
    args = ap.parse_args()
    if not args.key:
        ap.error("--key must not be empty")
    server = make_server(args.port, args.key, args.store, host=args.host)
    print("mock server on %s:%d, store %s" % (args.host, server.server_address[1], args.store),
          file=sys.stderr, flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
