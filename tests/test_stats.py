"""Asserts the spec section 3 numbers that Sprints 1 to 3 introduce."""
import itertools
import os
import unittest

from evaldiff import parse, stats
from evaldiff.server import compare

FIX = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "fixtures")


def read(f):
    with open(os.path.join(FIX, f)) as fh:
        return fh.read()


def load(fa, fb):
    sides = [parse.parse_side(read(f), f, lab) for f, lab in ((fa, "A"), (fb, "B"))]
    ids, a, b, w = parse.pair(*sides)
    return ids, a, b, w, stats.analyze(ids, a, b)


def paste(a, b, **extra):
    return compare(dict({"a": {"name": None, "text": a}, "b": {"name": None, "text": b}}, **extra))


def fixture(fa, fb, **extra):
    return compare(dict({k: {"name": f, "text": read(f)} for k, f in (("a", fa), ("b", fb))},
                        **extra))


def brute_wilcoxon(d, zero):
    """Independent check: rank by brute-force average ranks, then enumerate all 2^z sign assignments."""
    r = [round(x, 12) for x in d]
    if zero == "wilcox":
        r = [x for x in r if x != 0]
    absr = [abs(x) for x in r]
    rank = [sum(1 for y in absr if y < x) + (sum(1 for y in absr if y == x) + 1) / 2 for x in absr]
    nz = [(rk, x) for rk, x in zip(rank, r) if x != 0]
    wp, wm = sum(rk for rk, x in nz if x > 0), sum(rk for rk, x in nz if x < 0)
    obs = abs(wp - wm) - 1e-9
    hits = sum(1 for signs in itertools.product((1, -1), repeat=len(nz))
               if abs(sum(s * rk for s, (rk, _) in zip(signs, nz))) >= obs)
    return min(wp, wm), hits / 2 ** len(nz)


def tests_by_key(r):
    return {t["key"]: t for t in r["tests"]}


class Fixtures(unittest.TestCase):
    def test_f1(self):
        ids, a, b, w, r = load("f1_a.csv", "f1_b.csv")
        self.assertEqual((r["n"], r["score_type"]), (20, "binary"))
        self.assertAlmostEqual(r["mean_a"], 0.6)
        self.assertAlmostEqual(r["mean_b"], 0.8)
        self.assertAlmostEqual(r["diff"], 0.2)
        fl = r["flips"]
        self.assertEqual([x["id"] for x in fl["improved"]], ["q16", "q17", "q18", "q19", "q20"])
        self.assertEqual([x["id"] for x in fl["regressed"]], ["q15"])
        self.assertEqual((fl["both_pass"], fl["both_fail"]), (11, 3))
        self.assertAlmostEqual(stats.mcnemar(1, 5)[0], 0.21875)
        self.assertAlmostEqual(stats.mcnemar(1, 5)[1], 0.125)
        self.assertEqual(r["test"], "Exact McNemar (mid-p)")
        self.assertAlmostEqual(r["p_value"], 0.125)
        p, exact = stats.signflip([y - x for x, y in zip(a, b)])
        self.assertTrue(exact)
        self.assertAlmostEqual(p, 0.21875)
        lo, hi = r["ci"]
        self.assertTrue(-0.10 <= lo <= 0.00 and 0.35 <= hi <= 0.50, r["ci"])
        self.assertEqual(r["ci_label"], "95% paired bootstrap CI")
        self.assertEqual(r["verdict"], "No significant difference")
        self.assertEqual(load("f1_a.csv", "f1_b.csv")[4]["ci"], r["ci"])  # deterministic

    def test_f2(self):
        ids, a, b, w, r = load("f2_a.jsonl", "f2_b.jsonl")
        self.assertEqual(r["n"], 30)
        self.assertAlmostEqual(r["mean_a"], 0.5333, places=4)
        self.assertAlmostEqual(r["mean_b"], 0.8)
        self.assertAlmostEqual(r["diff"], 0.2667, places=4)
        self.assertEqual((len(r["flips"]["regressed"]), len(r["flips"]["improved"])), (1, 9))
        self.assertEqual((r["flips"]["both_pass"], r["flips"]["both_fail"]), (15, 5))
        ex, mid = stats.mcnemar(1, 9)
        self.assertAlmostEqual(ex, 0.021484, places=6)
        self.assertAlmostEqual(mid, 0.011719, places=6)
        self.assertAlmostEqual(stats.signflip([y - x for x, y in zip(a, b)])[0], 0.021484, places=6)
        lo, hi = r["ci"]
        self.assertTrue(0.0333 <= lo <= 0.1334 and lo > 0 and 0.40 <= hi <= 0.50, r["ci"])
        self.assertEqual(r["verdict"], "B is better (significant)")
        s = stats.analyze(ids, b, a)  # swap
        self.assertAlmostEqual(s["diff"], -0.2667, places=4)
        self.assertAlmostEqual(s["p_value"], 0.011719, places=6)
        self.assertEqual(s["verdict"], "B is worse (significant)")
        self.assertEqual((len(s["flips"]["improved"]), len(s["flips"]["regressed"])), (1, 9))

    def test_f3(self):
        ids, a, b, w, r = load("f3_a.jsonl", "f3_b.jsonl")
        self.assertEqual((r["n"], r["score_type"]), (8, "continuous"))
        self.assertAlmostEqual(r["mean_a"], 0.475)
        self.assertAlmostEqual(r["mean_b"], 0.6875)
        self.assertAlmostEqual(r["diff"], 0.2125)
        self.assertEqual(r["test"], "Paired sign-flip permutation (exact)")
        self.assertAlmostEqual(r["p_value"], 0.015625)
        self.assertEqual(r["verdict"], "B is better (significant)")
        lo, hi = r["ci"]
        self.assertTrue(0.08 <= lo <= 0.16 and 0.26 <= hi <= 0.34, r["ci"])
        self.assertEqual([x["id"] for x in r["flips"]["improved"]], ["c01", "c03"])
        self.assertEqual(r["flips"]["regressed"], [])
        self.assertEqual(stats.mcnemar(0, 2), (0.5, 0.25))
        self.assertEqual(r["changes"][0]["id"], "c01")
        self.assertAlmostEqual(r["changes"][0]["d"], 0.4)

    def test_f4(self):
        ids, a, b, w, r = load("f4_a.jsonl", "f4_b.jsonl")
        self.assertIn("4 ids have multiple rows in A; scores averaged per id", w)
        self.assertIn("4 ids have multiple rows in B; scores averaged per id", w)
        for x, y in zip(a, [0.3, 0.5, 0.7, 0.1]):
            self.assertAlmostEqual(x, y)
        for x, y in zip(b, [0.6, 0.7, 0.8, 0.5]):
            self.assertAlmostEqual(x, y)
        self.assertEqual(r["n"], 4)
        self.assertAlmostEqual(r["mean_a"], 0.4)
        self.assertAlmostEqual(r["mean_b"], 0.65)
        self.assertAlmostEqual(r["diff"], 0.25)
        self.assertAlmostEqual(r["p_value"], 0.125)
        self.assertEqual(r["verdict"], "No significant difference")
        lo, hi = r["ci"]
        self.assertTrue(0.10 <= lo <= 0.20 and 0.30 <= hi <= 0.40, r["ci"])
        self.assertTrue(any(x.startswith("Small sample (n < 10)") for x in r["warnings"]))

    def test_big(self):
        ids, a, b, w, r = load("big_a.jsonl", "big_b.jsonl")
        self.assertEqual(r["n"], 2000)
        self.assertAlmostEqual(r["mean_a"], 0.6)
        self.assertAlmostEqual(r["mean_b"], 0.7)
        self.assertAlmostEqual(r["diff"], 0.1)
        self.assertEqual((len(r["flips"]["regressed"]), len(r["flips"]["improved"])), (400, 600))
        self.assertLess(r["p_value"], 0.0001)
        self.assertEqual(r["verdict"], "B is better (significant)")


class EdgeCases(unittest.TestCase):
    def test_mismatched_ids(self):
        r = paste("id,score\nx1,1\nx2,0\nx3,1\nx4,1\nx5,0\n", "id,score\nx1,1\nx2,1\nx3,1\nx6,0\n")
        self.assertEqual(r["n"], 3)
        self.assertAlmostEqual(r["diff"], 1 / 3)
        self.assertAlmostEqual(r["p_value"], 0.5)
        self.assertIn("2 ids only in A: x4, x5", r["warnings"])
        self.assertIn("1 ids only in B: x6", r["warnings"])

    def test_invalid_scores(self):
        r = paste("id,score\nv1,1\nv2,abc\nv3,NaN\nv4,\nv5,0\n", "id,score\nv1,1\nv2,1\nv3,1\nv4,1\nv5,1\n")
        self.assertIn("Excluded 3 rows from A with invalid scores (lines 3, 4, 5)", r["warnings"])
        self.assertIn("3 ids only in B: v2, v3, v4", r["warnings"])
        self.assertEqual(r["n"], 2)
        self.assertAlmostEqual(r["diff"], 0.5)
        self.assertAlmostEqual(r["p_value"], 0.5)

    def test_no_overlap(self):
        r = paste("id,score\na1,1\na2,0", "id,score\nb1,1\nb2,0")
        self.assertEqual(r["error"], "No example ids match between A and B.")

    def test_n1(self):
        r = paste("id,score\ns1,1", "id,score\ns1,0")
        self.assertEqual(r["n"], 1)
        self.assertAlmostEqual(r["diff"], -1)
        self.assertIsNone(r["p_value"])
        self.assertIsNone(r["ci"])
        self.assertEqual(r["verdict"], "Insufficient data (n < 2)")

    def test_all_ties(self):
        t = read("f1_a.csv")
        r = paste(t, t)
        self.assertEqual(r["diff"], 0)
        self.assertEqual(r["ci"], (0.0, 0.0))
        self.assertEqual(r["p_value"], 1.0)
        self.assertEqual(r["verdict"], "No significant difference")
        self.assertEqual(r["note"], "All paired differences are zero.")

    def test_bad_files(self):
        ok = "id,score\nz1,1"
        # Sprint 2: a missing id or score column offers mapping instead of an error (amended criterion 16)
        r = paste("name,score\nz1,1", ok)
        self.assertNotIn("error", r)
        self.assertEqual(r["missing_columns"], ["A: no id column found (expected one of: id, example_id, sample_id)"])
        self.assertEqual(paste('{"id":"z1","score":1}\n{bad json', ok)["error"], "A: line 2 is not valid JSON")
        self.assertEqual(paste('{"id":"z1","score":1}\n[1]', ok)["error"], "A: line 2 is not a JSON object")
        self.assertEqual(paste("", ok)["error"], "A: file contains no rows.")
        self.assertEqual(paste(ok, "id,name\nz1,x")["missing_columns"],
                         ["B: no score column found (expected one of: score, passed, pass, correct, value, result)"])

    def test_utf8_bom(self):
        csv_side = parse.parse_side("\ufeffid,score\nq1,1\nq2,0\n", "pasted.csv", "A")
        self.assertEqual(csv_side["scores"], {"q1": [1.0], "q2": [0.0]})
        self.assertEqual(paste("\ufeffid,score\nq1,1\nq2,0\n", "id,score\nq1,1\nq2,1\n")["n"], 2)
        jl = parse.parse_side('\ufeff{"id":"q1","score":1}\n{"id":"q2","score":0}\n', None, "A")
        self.assertEqual(jl["scores"], {"q1": [1.0], "q2": [0.0]})

    def test_scores(self):
        for v, want in ((True, 1.0), (False, 0.0), (0.7, 0.7), (" Passed ", 1.0), ("no", 0.0), ("2.5", 2.5),
                        (None, None), ("", None), ("NaN", None), ("inf", None), ("-inf", None), ("abc", None),
                        (float("nan"), None)):
            self.assertEqual(parse.parse_score(v), want, v)

    def test_case_insensitive_header_and_numeric_ids(self):
        r = paste('{"Example_ID":7,"Correct":"yes"}\n{"Example_ID":8,"Correct":"no"}',
                  '{"example_id":"7","correct":1}\n{"example_id":"8","correct":1}')
        self.assertEqual(r["n"], 2)

    def test_bootstrap_uses_randrange_sequence(self):
        import random
        d = [0.1, -0.3, 0.2, 0.5, 0.0, 1.0, -1.0]
        rr = random.Random(0).randrange
        means = sorted(sum(d[rr(7)] for _ in range(7)) / 7 for _ in range(1000))
        lo, hi = stats.bootstrap_ci(d, 0.05, 1000, 0)
        self.assertAlmostEqual(lo, means[25], places=12)
        self.assertAlmostEqual(hi, means[974], places=12)



class Sprint2Tests(unittest.TestCase):
    """Every paired test side by side (spec section 3, Sprint 2 criteria 1-8)."""

    def check_wilcoxon(self, r, zero, stat, p):
        t = tests_by_key(r)["wilcoxon"]
        d = [x["d"] for x in r["rows"]]
        bs, bp = brute_wilcoxon(d, zero)
        self.assertAlmostEqual(t["statistic"], stat)
        self.assertAlmostEqual(t["p"], p, places=6)
        self.assertAlmostEqual(t["statistic"], bs)
        self.assertAlmostEqual(t["p"], bp, places=12)

    def test_f1_battery(self):
        r = fixture("f1_a.csv", "f1_b.csv")
        t = tests_by_key(r)
        self.assertEqual(list(t), ["mcnemar_exact", "mcnemar_midp", "signflip", "wilcoxon", "ztest"])
        self.assertAlmostEqual(t["mcnemar_exact"]["p"], 0.21875)
        self.assertAlmostEqual(t["mcnemar_midp"]["p"], 0.125)
        self.assertEqual((t["mcnemar_exact"]["b"], t["mcnemar_exact"]["c"]), (1, 5))
        self.assertAlmostEqual(t["signflip"]["p"], 0.21875)
        self.check_wilcoxon(r, "wilcox", 3.5, 0.21875)
        self.assertEqual(t["wilcoxon"]["label"], "Wilcoxon signed-rank (exact)")
        import statistics
        d = [x["d"] for x in r["rows"]]
        self.assertAlmostEqual(statistics.stdev(d), 0.523148, places=6)
        self.assertAlmostEqual(statistics.stdev(d) / 20 ** 0.5, 0.116980, places=6)
        self.assertAlmostEqual(t["ztest"]["p"], 0.0873, places=4)
        self.assertAlmostEqual(t["ztest"]["ci"][0], -0.0293, places=4)
        self.assertAlmostEqual(t["ztest"]["ci"][1], 0.4293, places=4)

    def test_f2_battery(self):
        r = fixture("f2_a.jsonl", "f2_b.jsonl")
        t = tests_by_key(r)
        self.assertAlmostEqual(t["mcnemar_exact"]["p"], 0.021484, places=6)
        self.assertAlmostEqual(t["mcnemar_midp"]["p"], 0.011719, places=6)
        self.assertAlmostEqual(t["signflip"]["p"], 0.021484, places=6)
        self.check_wilcoxon(r, "wilcox", 5.5, 0.021484375)
        import statistics
        d = [x["d"] for x in r["rows"]]
        self.assertAlmostEqual(statistics.stdev(d), 0.520830, places=6)
        self.assertAlmostEqual(statistics.stdev(d) / 30 ** 0.5, 0.095090, places=6)
        self.assertAlmostEqual(statistics.variance(d), 0.271264, places=6)
        self.assertAlmostEqual(t["ztest"]["statistic"], 2.8044, places=4)
        self.assertTrue(abs(t["ztest"]["p"] - 0.0050) <= 0.0003)
        self.assertAlmostEqual(t["ztest"]["ci"][0], 0.0803, places=4)
        self.assertAlmostEqual(t["ztest"]["ci"][1], 0.4530, places=4)

    def test_f3_battery(self):
        r = fixture("f3_a.jsonl", "f3_b.jsonl")
        t = tests_by_key(r)
        self.check_wilcoxon(r, "wilcox", 1, 0.015625)
        self.assertAlmostEqual(t["signflip"]["p"], 0.015625)
        import statistics
        d = [x["d"] for x in r["rows"]]
        self.assertAlmostEqual(statistics.stdev(d), 0.145774, places=6)
        self.assertAlmostEqual(statistics.stdev(d) / 8 ** 0.5, 0.051539, places=6)
        self.assertLess(t["ztest"]["p"], 0.0001)
        self.assertAlmostEqual(t["ztest"]["ci"][0], 0.1115, places=4)
        self.assertAlmostEqual(t["ztest"]["ci"][1], 0.3135, places=4)
        self.assertEqual(t["mcnemar_exact"]["label"], "Exact McNemar (at threshold 0.5)")
        self.assertEqual(t["mcnemar_midp"]["label"], "Exact McNemar (mid-p) (at threshold 0.5)")
        self.assertEqual((t["mcnemar_exact"]["p"], t["mcnemar_midp"]["p"]), (0.5, 0.25))

    def test_f6_wilcox_vs_pratt(self):
        r = fixture("f6_a.csv", "f6_b.csv")
        self.assertEqual(r["score_type"], "continuous")
        self.assertAlmostEqual(r["diff"], 0.04)
        self.assertAlmostEqual(tests_by_key(r)["signflip"]["p"], 0.875)
        self.assertEqual(r["verdict"], "No significant difference")
        self.check_wilcoxon(r, "wilcox", 4, 0.875)
        r = fixture("f6_a.csv", "f6_b.csv", settings={"wilcoxon_zero": "pratt"})
        self.check_wilcoxon(r, "pratt", 5, 0.75)

    def test_wilcoxon_matches_brute_force(self):
        import random
        rng = random.Random(1)
        for _ in range(200):
            d = [rng.choice([0, 0.1, -0.1, 0.2, -0.2, 0.3, 0.35, -0.5, 1, -1]) for _ in range(rng.randint(1, 12))]
            for zero in ("wilcox", "pratt"):
                stat, p, exact = stats.wilcoxon(d, zero)
                if not any(d):
                    self.assertIsNone(p)
                    continue
                bs, bp = brute_wilcoxon(d, zero)
                self.assertAlmostEqual(stat, bs)
                self.assertAlmostEqual(p, bp, places=12)

    def test_wilcoxon_normal_approximation(self):
        d = [(-1) ** i * (i % 7 + 1) * 0.1 for i in range(60)]
        stat, p, exact = stats.wilcoxon(d)
        self.assertFalse(exact)
        self.assertTrue(0 < p <= 1)

    def test_primary_test(self):
        r = fixture("f3_a.jsonl", "f3_b.jsonl", settings={"primary": "wilcoxon"})
        self.assertEqual(r["test"], "Wilcoxon signed-rank (exact)")
        self.assertAlmostEqual(r["p_value"], 0.015625)
        r = fixture("f1_a.csv", "f1_b.csv", settings={"primary": "mcnemar_exact"})
        self.assertEqual(r["test"], "Exact McNemar")
        self.assertAlmostEqual(r["p_value"], 0.21875)

    def test_alpha(self):
        r = fixture("f2_a.jsonl", "f2_b.jsonl", settings={"alpha": 0.01})
        self.assertEqual(r["verdict"], "No significant difference")
        self.assertEqual(r["ci_label"], "99% paired bootstrap CI")
        self.assertEqual(fixture("f2_a.jsonl", "f2_b.jsonl", settings={"alpha": 0.05})["verdict"],
                         "B is better (significant)")
        self.assertEqual(fixture("f2_a.jsonl", "f2_b.jsonl", settings={"alpha": 0.1})["ci_label"],
                         "90% paired bootstrap CI")

    def test_seed(self):
        base = fixture("f1_a.csv", "f1_b.csv")
        s7 = fixture("f1_a.csv", "f1_b.csv", settings={"seed": 7})
        self.assertEqual(s7["seed"], 7)
        # F1 bootstrap means sit on a 0.05 grid, so seed 7 happens to give the same percentiles; F3 shows a change
        self.assertNotEqual(fixture("f3_a.jsonl", "f3_b.jsonl", settings={"seed": 7})["ci"],
                            fixture("f3_a.jsonl", "f3_b.jsonl")["ci"])
        for k in ("p_value", "verdict", "diff", "tests", "flips"):
            self.assertEqual(s7[k], base[k], k)
        self.assertEqual(fixture("f1_a.csv", "f1_b.csv", settings={"seed": 0})["ci"], base["ci"])

    def test_threshold(self):
        r = fixture("f3_a.jsonl", "f3_b.jsonl", settings={"threshold": 0.6})
        self.assertEqual([x["id"] for x in r["flips"]["improved"]], ["c01", "c02", "c03", "c07"])
        self.assertEqual([x["id"] for x in r["flips"]["regressed"]], ["c08"])
        t = tests_by_key(r)
        self.assertAlmostEqual(t["mcnemar_exact"]["p"], 0.375)
        self.assertAlmostEqual(t["mcnemar_midp"]["p"], 0.21875)
        self.assertEqual(t["mcnemar_exact"]["label"], "Exact McNemar (at threshold 0.6)")

    def test_settings_validation(self):
        for bad, msg in (({"n_boot": 500}, "Bootstrap resamples must be between 1000 and 100000"),
                         ({"n_boot": 100001}, "Bootstrap resamples must be between 1000 and 100000"),
                         ({"seed": 1.5}, "Seed must be an integer"), ({"alpha": 0.2}, "alpha must be 0.01, 0.05 or 0.10"),
                         ({"primary": "nope"}, "Unknown primary test: nope"),
                         ({"wilcoxon_zero": "zsplit"}, "Wilcoxon zero handling must be wilcox or pratt")):
            self.assertEqual(fixture("f1_a.csv", "f1_b.csv", settings=bad)["error"], msg)
        r = fixture("f1_a.csv", "f1_b.csv", settings={"n_boot": 1000})
        self.assertEqual(r["verdict"], "No significant difference")

    def test_column_mapping(self):
        a, b = "qid,judge_score\na,1\nb,0\nc,1", "qid,judge_score\na,1\nb,1\nc,1"
        r = paste(a, b)
        self.assertNotIn("error", r)  # evaluator bug 1: mapping for both sides, no error
        for k in "ab":
            self.assertEqual(r["columns"][k], {"columns": ["qid", "judge_score"], "id": None, "score": None})
        # low-severity bug 2: each side lists both its missing id and its missing score column
        self.assertEqual(r["missing_columns"], [m % k for k in "AB" for m in (
            "%s: no id column found (expected one of: id, example_id, sample_id)",
            "%s: no score column found (expected one of: score, passed, pass, correct, value, result)")])
        m = {k: {"id": "qid", "score": "judge_score"} for k in "ab"}
        r = paste(a, b, mapping=m)
        self.assertTrue(r["mapped"])
        self.assertEqual(r["n"], 3)
        self.assertAlmostEqual(r["diff"], 1 / 3)
        # low-severity bug 1: a stale mapping on files that auto-detect fine is not "mapped", so the panel hides
        r = paste("id,score\na,1\nb,0", "id,score\na,1\nb,1", mapping=m)
        self.assertFalse(r["mapped"])
        self.assertEqual(r["n"], 2)
        r = paste("name,score\nz1,1", "id,score\nz1,1")
        self.assertEqual(r["columns"]["b"]["id"], "id")
        # other input errors are still errors, even when the other side also lacks a column
        self.assertEqual(paste("name,score\nz1,1", "")["error"], "B: file contains no rows.")

    def test_mapping_alt_score(self):
        m = {k: {"id": "id", "score": "alt_score"} for k in "ab"}
        r = fixture("f3_a.jsonl", "f3_b.jsonl", mapping=m)
        self.assertTrue(r["mapped"])
        self.assertEqual(r["diff"], 0)
        self.assertEqual(r["p_value"], 1.0)
        self.assertEqual(r["verdict"], "No significant difference")
        self.assertEqual(r["note"], "All paired differences are zero.")
        self.assertIsNone(tests_by_key(r)["wilcoxon"]["p"])

    def test_explorer_rows(self):
        r = fixture("f2_a.jsonl", "f2_b.jsonl")
        rows = r["rows"]
        self.assertEqual([x["id"] for x in rows if x["status"] == "regressed"], ["k16"])
        self.assertEqual(sum(1 for x in rows if x["status"] == "improved"), 9)
        self.assertEqual(sum(1 for x in rows if x["status"] == "unchanged"), 20)
        self.assertEqual([x["id"] for x in rows if "m0" in x["id"]], ["m0%d" % i for i in range(1, 10)])
        k16 = next(x for x in rows if x["id"] == "k16")
        self.assertEqual(k16["raw_a"], [{"id": "k16", "passed": True, "slice": "code"}])
        self.assertEqual(k16["raw_b"], [{"id": "k16", "passed": False, "slice": "code"}])
        r3 = fixture("f3_a.jsonl", "f3_b.jsonl")
        asc = sorted(r3["rows"], key=lambda x: x["d"])
        self.assertEqual((asc[0]["id"], round(asc[0]["d"], 4), asc[-1]["id"]), ("c08", -0.05, "c01"))

    def test_columns_endpoint(self):
        from evaldiff.server import columns
        c = columns({"a": {"name": "f3_a.jsonl", "text": read("f3_a.jsonl")},
                     "b": {"name": None, "text": "{bad"}})
        self.assertEqual(c["a"], {"columns": ["id", "score", "alt_score", "cluster"], "id": "id", "score": "score"})
        self.assertEqual(c["b"]["error"], "B: line 1 is not valid JSON")
        # evaluator bug 2: per-side errors that the Map columns button must show
        c = columns({"a": {"name": None, "text": ""}, "b": {"name": None, "text": '{"id":1,"score":1}\n{bad'}})
        self.assertEqual((c["a"]["columns"], c["a"]["error"]), ([], "A: file contains no rows."))
        self.assertEqual(c["b"]["error"], "B: line 2 is not valid JSON")



class Sprint3Power(unittest.TestCase):
    """Power and sample size (spec section 3 power numbers, Sprint 3 criteria)."""

    def plan(self, r, **kw):
        from evaldiff.server import power
        binary = r["score_type"] == "binary"
        args = dict(design=r["score_type"], value=r["pd"] if binary else r["var_d"], alpha=0.05, power=0.8,
                    effect=0.05, n=r["n"])
        args.update(kw)
        return power(args)

    def test_f1(self):
        r = fixture("f1_a.csv", "f1_b.csv")
        self.assertAlmostEqual(r["pd"], 0.3)
        p = self.plan(r)
        self.assertEqual(p["method"], "Connor (paired binary)")
        self.assertTrue(abs(p["mde"] - 0.3233) <= 0.003, p["mde"])
        self.assertLess(abs(r["diff"]), p["mde"])  # criterion 2: power note applies (not significant)
        self.assertGreaterEqual(r["p_value"], r["alpha"])

    def test_f2(self):
        r = fixture("f2_a.jsonl", "f2_b.jsonl")
        self.assertAlmostEqual(r["pd"], 1 / 3)
        p = self.plan(r)
        self.assertTrue(abs(p["mde"] - 0.2839) <= 0.003, p["mde"])
        self.assertTrue(abs(p["n_required"] - 1045) <= 3, p["n_required"])
        self.assertEqual(p["n_required"], 1045)
        self.assertLess(r["p_value"], r["alpha"])  # criterion 3: significant, so no power note

    def test_f3(self):
        r = fixture("f3_a.jsonl", "f3_b.jsonl")
        self.assertAlmostEqual(r["var_d"], 0.02125)
        p = self.plan(r)
        self.assertEqual(p["method"], "Paired normal approximation (Miller 2024)")
        self.assertTrue(abs(p["mde"] - 0.1444) <= 0.001, p["mde"])
        self.assertEqual(p["n_required"], 67)
        self.assertEqual(self.plan(r, effect=0.10)["n_required"], 17)
        self.assertEqual(self.plan(r, power=0.90)["n_required"], 90)  # criterion 9
        t = p["table"]
        self.assertEqual([x["n"] for x in t], [8, 50, 100, 200, 500, 1000, 2000])
        self.assertEqual([x["n"] for x in t if x["current"]], [8])
        self.assertAlmostEqual(t[0]["mde"], p["mde"])
        self.assertTrue(all(a["mde"] > b["mde"] for a, b in zip(t, t[1:])))

    def test_no_variation_and_assumed(self):
        t = read("f1_a.csv")
        r = paste(t, t)
        self.assertEqual(r["pd"], 0)
        p = self.plan(r)
        self.assertIsNone(p["mde"])
        self.assertIsNone(p["n_required"])
        self.assertTrue(abs(self.plan(r, value=0.2)["n_required"] - 626) <= 3)  # criterion 7, assumed p_d 0.2

    def test_planner(self):
        from evaldiff.server import power
        self.assertEqual(power(dict(design="binary", value=0.2, alpha=0.05, power=0.8, effect=0.05))["n_required"], 626)
        self.assertEqual(power(dict(design="continuous", value=0.3 ** 2, alpha=0.05, power=0.8, effect=0.05))["n_required"],
                         283)

    def test_connor_formula_and_bisection(self):
        """Independent re-derivation: Connor's n at the bisected MDE equals the current n."""
        from statistics import NormalDist
        za, zb = NormalDist().inv_cdf(0.975), NormalDist().inv_cdf(0.8)
        for pd, n in ((0.3, 20), (1 / 3, 30), (0.05, 2000)):
            delta = stats.connor_mde(pd, n)
            self.assertAlmostEqual((za * pd ** 0.5 + zb * (pd - delta ** 2) ** 0.5) ** 2 / delta ** 2, n, places=6)
        self.assertIsNone(stats.connor_mde(0.3, 3))  # even delta = sqrt(p_d) needs more than 3
        self.assertIsNone(stats.connor_n(0.01, 0.5))
        self.assertIn("n_required_note", stats.power_plan("binary", 0.01, effect=0.5, n=20))
        self.assertAlmostEqual(stats.normal_mde(0.02125, 67) / 0.05, (66.71547774 / 67) ** 0.5, places=6)

    def test_current_n_already_in_table(self):
        t = stats.power_plan("binary", 0.2, n=2000)["table"]
        self.assertEqual([x["n"] for x in t], [50, 100, 200, 500, 1000, 2000])
        self.assertEqual([x["current"] for x in t], [False] * 5 + [True])

    def test_power_validation(self):
        from evaldiff.server import power
        base = dict(design="binary", value=0.2, alpha=0.05, power=0.8, effect=0.05)
        for bad, msg in (({"power": 1.0}, "Target power must be between 0 and 1"),
                         ({"power": None}, "Target power must be between 0 and 1"),
                         ({"effect": 0}, "Target effect must be between 0 and 1"),
                         ({"value": 1.5}, "The discordance rate must be between 0 and 1"),
                         ({"value": -1}, "The discordance rate or SD must be 0 or more"),
                         ({"design": "x"}, "Design must be binary or continuous"),
                         ({"n": 0}, "n must be a whole number of at least 1")):
            self.assertEqual(power(dict(base, **bad))["error"], msg)

    def test_no_observed_power(self):
        root = os.path.dirname(FIX)
        for f in ("index.html", "app.js"):
            with open(os.path.join(root, "evaldiff", "static", f)) as fh:
                self.assertNotIn("observed power", fh.read().lower())


class TestNoise(unittest.TestCase):
    def run_fix(self, a, b):
        from evaldiff.server import compare
        rd = lambda f: {"name": f, "text": open(os.path.join(FIX, f)).read()}
        return compare({"a": rd(a), "b": rd(b)})

    def test_f4(self):
        r = self.run_fix("f4_a.jsonl", "f4_b.jsonl")
        nz = r["noise"]
        self.assertAlmostEqual(nz["a"]["sg"], 0.01)
        self.assertAlmostEqual(nz["b"]["sg"], 0.01)
        self.assertEqual((nz["a"]["k"], nz["b"]["k"]), (2, 2))
        self.assertAlmostEqual(nz["var_d"], 0.016667, places=6)
        self.assertAlmostEqual(nz["noise_share"], 0.6)
        self.assertAlmostEqual(nz["signal_share"], 0.4)
        self.assertAlmostEqual(nz["omega2"], 0.006667, places=6)
        self.assertAlmostEqual(nz["se_paired"], 0.0645, places=4)
        omega = nz["omega2"]
        se = lambda k: ((omega + (nz["a"]["sg"] + nz["b"]["sg"]) / k) / 4) ** 0.5
        self.assertAlmostEqual(se(4), 0.0540, places=4)
        self.assertAlmostEqual((omega / 4) ** 0.5, 0.0408, places=4)
        self.assertEqual(nz["warning"], "")

    def test_f7(self):
        r = self.run_fix("f7_a.jsonl", "f7_b.jsonl")
        nz = r["noise"]
        self.assertEqual((round(r["mean_a"], 4), round(r["mean_b"], 4), round(r["diff"], 4)), (0.5, 0.9167, 0.4167))
        self.assertAlmostEqual(next(t for t in r["tests"] if t["key"] == "signflip")["p"], 0.25)
        self.assertEqual((nz["a"]["j"], nz["a"]["k"]), (2, 2))
        self.assertAlmostEqual(nz["a"]["sj"], 0.166667, places=6)
        self.assertAlmostEqual(nz["b"]["sj"], 0.083333, places=6)
        self.assertAlmostEqual(nz["a"]["sg"], 0.166667, places=6)
        self.assertAlmostEqual(nz["b"]["sg"], 0.0)
        self.assertEqual((nz["a"]["disagree_n"], nz["b"]["disagree_n"], nz["a"]["disagree_cells"]), (2, 1, 6))
        self.assertAlmostEqual(nz["var_d"], 0.020833, places=6)
        self.assertAlmostEqual(nz["gen_share"], 4.0)
        self.assertAlmostEqual(nz["judge_share"], 3.0)
        self.assertEqual(nz["signal_share"], 0.0)
        self.assertIn("Estimated noise exceeds the observed variance of differences", nz["warning"])
        self.assertIn("n = 3", nz["warning"])
        self.assertEqual({x["id"]: (x["a"], x["b"]) for x in nz["unstable"]},
                         {"j1": (0.75, 1.0), "j2": (0.25, 0.75), "j3": (0.5, 1.0)})
        self.assertEqual(len(r["rows"][1]["raw_a"]), 4)

    def test_no_repeats(self):
        self.assertEqual(self.run_fix("f1_a.csv", "f1_b.csv")["noise"], {"repeated": False})
        # trial-1 rows of F4 only
        from evaldiff.server import compare
        keep = lambda f: "".join(l for l in open(os.path.join(FIX, f)) if '"trial":1' in l)
        r = compare({"a": {"text": keep("f4_a.jsonl")}, "b": {"text": keep("f4_b.jsonl")}})
        self.assertEqual(r["noise"], {"repeated": False})

    def test_unbalanced(self):
        from evaldiff.server import compare
        a = '{"id":"x","score":0}\n{"id":"x","score":1}\n{"id":"y","score":1}\n{"id":"z","score":0}\n'
        b = '{"id":"x","score":1}\n{"id":"y","score":1}\n{"id":"z","score":1}\n'
        nz = compare({"a": {"text": a}, "b": {"text": b}})["noise"]
        self.assertAlmostEqual(nz["a"]["sg"], 0.5)  # only x has K_i >= 2
        self.assertAlmostEqual(nz["a"]["gen"], 0.5 * (1 / 2 + 1 + 1) / 3)
        self.assertIsNone(nz["b"]["sg"])


if __name__ == "__main__":
    unittest.main()
