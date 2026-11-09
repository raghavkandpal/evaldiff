"""Asserts the spec section 3 numbers that Sprint 1 introduces."""
import os
import unittest

from evaldiff import parse, stats
from evaldiff.server import compare

FIX = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "fixtures")


def load(fa, fb):
    sides = [parse.parse_side(open(os.path.join(FIX, f)).read(), f, lab) for f, lab in ((fa, "A"), (fb, "B"))]
    ids, a, b, w = parse.pair(*sides)
    return ids, a, b, w, stats.analyze(ids, a, b)


def paste(a, b):
    return compare({"a": {"name": None, "text": a}, "b": {"name": None, "text": b}})


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
        t = open(os.path.join(FIX, "f1_a.csv")).read()
        r = paste(t, t)
        self.assertEqual(r["diff"], 0)
        self.assertEqual(r["ci"], (0.0, 0.0))
        self.assertEqual(r["p_value"], 1.0)
        self.assertEqual(r["verdict"], "No significant difference")
        self.assertEqual(r["note"], "All paired differences are zero.")

    def test_bad_files(self):
        ok = "id,score\nz1,1"
        self.assertEqual(paste("name,score\nz1,1", ok)["error"],
                         "A: no id column found (expected one of: id, example_id, sample_id)")
        self.assertEqual(paste('{"id":"z1","score":1}\n{bad json', ok)["error"], "A: line 2 is not valid JSON")
        self.assertEqual(paste('{"id":"z1","score":1}\n[1]', ok)["error"], "A: line 2 is not a JSON object")
        self.assertEqual(paste("", ok)["error"], "A: file contains no rows.")
        self.assertEqual(paste(ok, "id,name\nz1,x")["error"],
                         "B: no score column found (expected one of: score, passed, pass, correct, value, result)")

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


if __name__ == "__main__":
    unittest.main()
