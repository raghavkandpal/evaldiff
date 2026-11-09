"""All statistics (spec section 2.3). Pure functions."""
import math
import random

ALPHA = 0.05
THRESHOLD = 0.5
N_BOOT = 10000
R_PERM = 10000


def mcnemar(b, c):
    """Exact McNemar. Returns (exact_p, mid_p). Integer arithmetic so large m does not underflow."""
    m, k = b + c, min(b, c)
    if m == 0:
        return 1.0, 1.0
    below = sum(math.comb(m, i) for i in range(k))
    at = math.comb(m, k)
    total = 2 ** m
    return min(1.0, 2 * (below + at) / total), min(1.0, (2 * below + at) / total)


def signflip(d, seed=0):
    """Sign-flip permutation p on |sum d|. Returns (p, exact)."""
    nz = [x for x in d if x != 0]
    obs = abs(sum(d)) - 1e-9
    if len(nz) <= 16:
        sums = [0.0]
        for x in nz:
            sums = [s + x for s in sums] + [s - x for s in sums]
        return sum(1 for s in sums if abs(s) >= obs) / len(sums), True
    rng = random.Random(seed)
    hits = sum(1 for _ in range(R_PERM)
               if abs(sum(x if rng.random() < 0.5 else -x for x in nz)) >= obs)
    return (1 + hits) / (1 + R_PERM), False


def _draws_match_randrange():
    """The inlined draw below mirrors Random._randbelow; verify it on this Python, else fall back."""
    for n in (1, 3, 8, 2000):
        r1, r2, k = random.Random(5).randrange, random.Random(5).getrandbits, n.bit_length()
        for _ in range(50):
            x = r2(k)
            while x >= n:
                x = r2(k)
            if x != r1(n):
                return False
    return True


_FAST = _draws_match_randrange()


def bootstrap_ci(d, alpha=ALPHA, n_boot=N_BOOT, seed=0):
    """Paired percentile bootstrap; draws rng.randrange(n) in order, resample by resample."""
    n = len(d)
    rng = random.Random(seed)
    means = []
    if _FAST:  # same draws as rng.randrange(n), ~4x faster (BIG n=2000 must finish in < 10 s)
        gb, k = rng.getrandbits, n.bit_length()
        for _ in range(n_boot):
            s = 0
            for _ in range(n):
                r = gb(k)
                while r >= n:
                    r = gb(k)
                s += d[r]
            means.append(s / n)
    else:
        rr = rng.randrange
        means = [sum([d[rr(n)] for _ in range(n)]) / n for _ in range(n_boot)]
    means.sort()
    return means[math.floor(n_boot * alpha / 2)], means[math.ceil(n_boot * (1 - alpha / 2)) - 1]


def verdict(n, p, diff, alpha=ALPHA):
    if n < 2:
        return "Insufficient data (n < 2)"
    if p < alpha and diff > 0:
        return "B is better (significant)"
    if p < alpha and diff < 0:
        return "B is worse (significant)"
    return "No significant difference"


def analyze(ids, a, b, alpha=ALPHA, threshold=THRESHOLD, seed=0):
    """Sprint 1 analysis of paired per-id means a, b."""
    n = len(ids)
    d = [y - x for x, y in zip(a, b)]
    binary = all(v in (0.0, 1.0) for v in a + b)
    passed = (lambda v: v == 1.0) if binary else (lambda v: v >= threshold)
    flips = {"improved": [], "regressed": [], "both_pass": 0, "both_fail": 0}
    for i, x, y in zip(ids, a, b):
        pa, pb = passed(x), passed(y)
        if pa and pb:
            flips["both_pass"] += 1
        elif not pa and not pb:
            flips["both_fail"] += 1
        else:
            flips["improved" if pb else "regressed"].append({"id": i, "a": x, "b": y})
    if binary:
        test = "Exact McNemar (mid-p)"
        p = mcnemar(len(flips["regressed"]), len(flips["improved"]))[1]
    else:
        p, exact = signflip(d, seed)
        test = "Paired sign-flip permutation (%s)" % ("exact" if exact else "Monte Carlo, R=%d" % R_PERM)
    diff = sum(d) / n
    ci = bootstrap_ci(d, alpha, N_BOOT, seed) if n >= 2 else None
    warnings, note = [], ""
    if n < 10:
        warnings.append("Small sample (n < 10): the bootstrap CI is unreliable; trust the exact test p-value.")
    if all(x == 0 for x in d):
        note = "All paired differences are zero."
    changes = []
    if not binary:
        order = sorted(range(n), key=lambda j: -abs(d[j]))[:20]
        changes = [{"id": ids[j], "a": a[j], "b": b[j], "d": d[j]} for j in order]
    return {
        "n": n,
        "score_type": "binary" if binary else "continuous",
        "mean_a": sum(a) / n,
        "mean_b": sum(b) / n,
        "diff": diff,
        "ci": ci,
        "ci_label": "%d%% paired bootstrap CI" % round((1 - alpha) * 100),
        "test": test,
        "p_value": p if n >= 2 else None,
        "verdict": verdict(n, p, diff, alpha),
        "seed": seed,
        "flips": flips,
        "changes": changes,
        "warnings": warnings,
        "note": note,
    }
