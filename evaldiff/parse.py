"""Parsing, validation and pairing of results files (spec section 2)."""
import csv
import io
import json
import math

ID_KEYS = ("id", "example_id", "sample_id")
SCORE_KEYS = ("score", "passed", "pass", "correct", "value", "result")
MAX_BYTES = 50 * 1024 * 1024
TRUE = {"true", "pass", "passed", "yes"}
FALSE = {"false", "fail", "failed", "no"}


class InputError(Exception):
    pass


def _list(items):
    items = list(items)
    return ", ".join(items[:10]) + (", …" if len(items) > 10 else "")


def parse_score(v):
    """Return a float score, or None if invalid (spec 2.1)."""
    if isinstance(v, bool):
        return float(v)
    if isinstance(v, (int, float)):
        return float(v) if math.isfinite(v) else None
    if isinstance(v, str):
        s = v.strip().lower()
        if s in TRUE:
            return 1.0
        if s in FALSE:
            return 0.0
        try:
            f = float(s)
        except ValueError:
            return None
        return f if math.isfinite(f) else None
    return None


def _pick(keys, wanted):
    lower = {}
    for k in keys:
        lower.setdefault(k.strip().lower(), k)
    return next((lower[w] for w in wanted if w in lower), None)


def _records(text, name):
    """Yield (line_no, dict) and return the list of all keys seen."""
    n = (name or "").lower()
    if n.endswith((".jsonl", ".json")) or (not n.endswith((".csv", ".tsv")) and text.lstrip().startswith("{")):
        out = []
        for i, line in enumerate(text.splitlines(), 1):
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
            except ValueError:
                raise InputError("line %d is not valid JSON" % i)
            if not isinstance(obj, dict):
                raise InputError("line %d is not a JSON object" % i)
            out.append((i, obj))
        keys = []
        for _, o in out:
            keys.extend(k for k in o if k not in keys)
        return out, keys
    delim = "\t" if (name or "").lower().endswith(".tsv") else ","
    reader = csv.reader(io.StringIO(text, newline=""), delimiter=delim)
    header, out = None, []
    for row in reader:
        if not any(c.strip() for c in row):
            continue
        if header is None:
            header = row
            continue
        out.append((reader.line_num, dict(zip(header, row))))
    return out, header or []


class ColumnError(InputError):
    """The id or score column could not be found; the UI offers column mapping (Sprint 2)."""


def _prepare(text, label):
    if len(text.encode("utf-8")) > MAX_BYTES:
        raise InputError("%s: file is larger than 50 MB." % label)
    return text[1:] if text.startswith("\ufeff") else text  # UTF-8 BOM would hide the first header


def columns(text, name, label):
    """Return {'columns': [...], 'id': auto id key or None, 'score': auto score key or None}."""
    text = _prepare(text, label)
    try:
        recs, keys = _records(text, name)
    except InputError as e:
        raise InputError("%s: %s" % (label, e))
    if not recs:
        raise InputError("%s: file contains no rows." % label)
    return {"columns": keys, "id": _pick(keys, ID_KEYS), "score": _pick(keys, SCORE_KEYS)}


def parse_side(text, name, label, id_key=None, score_key=None):
    """Parse one file. Returns {'ids', 'scores': {id: [floats]}, 'rows': {id: [raw dicts]}, 'invalid', 'id_key',
    'score_key', 'mapped'}. id_key/score_key override auto-detection when they name a column of this file."""
    text = _prepare(text, label)
    try:
        recs, keys = _records(text, name)
    except InputError as e:
        raise InputError("%s: %s" % (label, e))
    if not recs:
        raise InputError("%s: file contains no rows." % label)
    auto = _pick(keys, ID_KEYS), _pick(keys, SCORE_KEYS)
    id_key = id_key if id_key and id_key in keys else auto[0]
    score_key = score_key if score_key and score_key in keys else auto[1]
    missing = []  # report both missing columns at once; ColumnError args are the messages
    if id_key is None:
        missing.append("%s: no id column found (expected one of: %s)" % (label, ", ".join(ID_KEYS)))
    if score_key is None:
        missing.append("%s: no score column found (expected one of: %s)" % (label, ", ".join(SCORE_KEYS)))
    if missing:
        raise ColumnError(*missing)
    scores, rows, invalid = {}, {}, []
    for line, rec in recs:
        rid = rec.get(id_key)
        s = parse_score(rec.get(score_key))
        rid = "" if rid is None or isinstance(rid, (dict, list)) else str(rid).strip()
        if s is None or rid == "":  # shortcut: rows without an id are reported as invalid too
            invalid.append(line)
            continue
        scores.setdefault(rid, []).append(s)
        rows.setdefault(rid, []).append(rec)
    return {"ids": list(scores), "scores": scores, "rows": rows, "invalid": invalid,
            "id_key": id_key, "score_key": score_key, "mapped": (id_key, score_key) != auto}


def pair(a, b):
    """Pair two parsed sides. Returns (ids, a_means, b_means, warnings)."""
    warnings = []
    for lab, side in (("A", a), ("B", b)):
        multi = sum(1 for v in side["scores"].values() if len(v) > 1)
        if multi:
            warnings.append("%d ids have multiple rows in %s; scores averaged per id" % (multi, lab))
    bset, aset = set(b["ids"]), set(a["ids"])
    only_a = [i for i in a["ids"] if i not in bset]
    only_b = [i for i in b["ids"] if i not in aset]
    if only_a:
        warnings.append("%d ids only in A: %s" % (len(only_a), _list(only_a)))
    if only_b:
        warnings.append("%d ids only in B: %s" % (len(only_b), _list(only_b)))
    for lab, side in (("A", a), ("B", b)):
        if side["invalid"]:
            warnings.append("Excluded %d rows from %s with invalid scores (lines %s)"
                            % (len(side["invalid"]), lab, _list(str(n) for n in side["invalid"])))
    ids = [i for i in a["ids"] if i in bset]
    mean = lambda v: sum(v) / len(v)
    return ids, [mean(a["scores"][i]) for i in ids], [mean(b["scores"][i]) for i in ids], warnings
