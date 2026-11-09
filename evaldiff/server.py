"""http.server handler: static files, /fixtures, /api/*."""
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import parse, stats

ROOT = os.path.dirname(os.path.abspath(__file__))
STATIC = os.path.join(ROOT, "static")
FIXTURES = os.path.join(os.path.dirname(ROOT), "fixtures")
EXAMPLES = [
    {"value": "f1", "label": "F1 binary n=20 (CSV)", "files": ["f1_a.csv", "f1_b.csv"]},
    {"value": "f2", "label": "F2 binary n=30 (JSONL)", "files": ["f2_a.jsonl", "f2_b.jsonl"]},
    {"value": "f3", "label": "F3 continuous n=8", "files": ["f3_a.jsonl", "f3_b.jsonl"]},
    {"value": "f4", "label": "F4 repeated trials", "files": ["f4_a.jsonl", "f4_b.jsonl"]},
    {"value": "big", "label": "BIG n=2000", "files": ["big_a.jsonl", "big_b.jsonl"]},
]
TYPES = {".html": "text/html", ".js": "text/javascript", ".css": "text/css",
         ".csv": "text/csv", ".tsv": "text/tab-separated-values", ".jsonl": "text/plain", ".json": "application/json"}


def compare(payload):
    """Run one comparison from {'a': {'name', 'text'}, 'b': {...}}. Returns a JSON-able dict."""
    try:
        sides = [parse.parse_side(payload[k].get("text") or "", payload[k].get("name"), k.upper()) for k in ("a", "b")]
    except parse.InputError as e:
        return {"error": str(e)}
    ids, a, b, warnings = parse.pair(*sides)
    if not ids:
        return {"error": "No example ids match between A and B.", "warnings": warnings}
    result = stats.analyze(ids, a, b)
    result["warnings"] = warnings + result["warnings"]
    return result


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json"):
        if not isinstance(body, bytes):
            body = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _file(self, folder, name):
        name = os.path.basename(name)  # no path traversal
        path = os.path.join(folder, name)
        if not name or not os.path.isfile(path):
            return self._send(404, b"Not found", "text/plain")
        with open(path, "rb") as f:
            self._send(200, f.read(), TYPES.get(os.path.splitext(name)[1], "application/octet-stream"))

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/":
            return self._file(STATIC, "index.html")
        if path.startswith("/static/"):
            return self._file(STATIC, path[len("/static/"):])
        if path.startswith("/fixtures/"):
            return self._file(FIXTURES, path[len("/fixtures/"):])
        if path == "/api/examples":
            return self._send(200, EXAMPLES)
        self._send(404, b"Not found", "text/plain")

    def do_POST(self):
        if self.path != "/api/compare":
            return self._send(404, b"Not found", "text/plain")
        length = int(self.headers.get("Content-Length") or 0)
        if length > 2 * parse.MAX_BYTES + 4096:
            return self._send(413, {"error": "A: file is larger than 50 MB."})
        try:
            payload = json.loads(self.rfile.read(length))
        except ValueError:
            return self._send(400, {"error": "Request is not valid JSON."})
        self._send(200, compare(payload))

    def log_message(self, *args):
        pass


def serve(host, port):
    try:
        httpd = ThreadingHTTPServer((host, port), Handler)
    except OSError:
        print("Port %d is in use; try --port %d" % (port, port + 1), flush=True)
        raise SystemExit(2)
    print("evaldiff running at http://%s:%d/" % (host, port), flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
