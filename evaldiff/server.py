"""http.server handler: static files, /fixtures, /api/*."""
import json
import math
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
    {"value": "f6", "label": "F6 zeros (Wilcoxon)", "files": ["f6_a.csv", "f6_b.csv"]},
    {"value": "big", "label": "BIG n=2000", "files": ["big_a.jsonl", "big_b.jsonl"]},
]
TYPES = {".html": "text/html", ".js": "text/javascript", ".css": "text/css",
         ".csv": "text/csv", ".tsv": "text/tab-separated-values", ".jsonl": "text/plain", ".json": "application/json"}


def _settings(raw):
    """Validate the settings panel values (trust boundary). Raises parse.InputError."""
    raw = raw or {}
    try:
        alpha = float(raw.get("alpha", stats.ALPHA))
        seed = raw.get("seed", 0)
        n_boot = raw.get("n_boot", stats.N_BOOT)
        threshold = float(raw.get("threshold", stats.THRESHOLD))
    except (TypeError, ValueError):
        raise parse.InputError("Settings must be numbers.")
    if alpha not in (0.01, 0.05, 0.1):
        raise parse.InputError("alpha must be 0.01, 0.05 or 0.10")
    if not isinstance(seed, int) or isinstance(seed, bool):
        raise parse.InputError("Seed must be an integer")
    if not isinstance(n_boot, int) or isinstance(n_boot, bool) or not 1000 <= n_boot <= 100000:
        raise parse.InputError("Bootstrap resamples must be between 1000 and 100000")
    if not math.isfinite(threshold):
        raise parse.InputError("Threshold must be a number")
    primary = raw.get("primary", "auto")
    if primary != "auto" and primary not in stats.TESTS:
        raise parse.InputError("Unknown primary test: %s" % primary)
    zero = raw.get("wilcoxon_zero", "wilcox")
    if zero not in ("wilcox", "pratt"):
        raise parse.InputError("Wilcoxon zero handling must be wilcox or pratt")
    return {"alpha": alpha, "seed": seed, "n_boot": n_boot, "threshold": threshold, "primary": primary, "zero": zero}


def _side(payload, k):
    return payload[k].get("text") or "", payload[k].get("name")


def columns(payload):
    """Headers of both files plus the auto-detected id/score columns, for the mapping selects."""
    out = {}
    for k in ("a", "b"):
        try:
            out[k] = parse.columns(*_side(payload, k), k.upper())
        except parse.InputError as e:
            out[k] = {"columns": [], "id": None, "score": None, "error": str(e)}
    return out


def compare(payload):
    """Run one comparison from {'a': {'name', 'text'}, 'b': {...}, 'settings': {...}, 'mapping': {...}}."""
    mapping = payload.get("mapping") or {}
    try:
        st = _settings(payload.get("settings"))
        sides = [parse.parse_side(*_side(payload, k), k.upper(), (mapping.get(k) or {}).get("id"),
                                  (mapping.get(k) or {}).get("score")) for k in ("a", "b")]
    except parse.ColumnError as e:
        return {"error": str(e), "columns": columns(payload)}
    except parse.InputError as e:
        return {"error": str(e)}
    ids, a, b, warnings = parse.pair(*sides)
    if not ids:
        return {"error": "No example ids match between A and B.", "warnings": warnings}
    result = stats.analyze(ids, a, b, st["alpha"], st["threshold"], st["seed"], st["n_boot"], st["primary"], st["zero"])
    result["warnings"] = warnings + result["warnings"]
    for row in result["rows"]:
        row["raw_a"], row["raw_b"] = sides[0]["rows"][row["id"]], sides[1]["rows"][row["id"]]
    result["mapping"] = {k: {"id": s["id_key"], "score": s["score_key"]} for k, s in zip("ab", sides)}
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
        if self.path not in ("/api/compare", "/api/columns"):
            return self._send(404, b"Not found", "text/plain")
        length = int(self.headers.get("Content-Length") or 0)
        if length > 2 * parse.MAX_BYTES + 4096:
            return self._send(413, {"error": "A: file is larger than 50 MB."})
        try:
            payload = json.loads(self.rfile.read(length))
        except ValueError:
            return self._send(400, {"error": "Request is not valid JSON."})
        if not isinstance(payload, dict) or not all(isinstance(payload.get(k), dict) for k in ("a", "b")):
            return self._send(400, {"error": "Request needs A and B."})
        self._send(200, (compare if self.path == "/api/compare" else columns)(payload))

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
