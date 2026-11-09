"""All statistics (spec section 2.3). Pure functions."""
import math
import random
import statistics

ALPHA = 0.05
THRESHOLD = 0.5
N_BOOT = 10000
R_PERM = 10000
MDE_NS = (50, 100, 200, 500, 1000, 2000)
CONNOR = "Connor (paired binary)"
MILLER = "Paired normal approximation (Miller 2024)"
TESTS = ("mcnemar_exact", "mcnemar_midp", "signflip", "wilcoxon", "ztest")


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
    # round(): keeps float noise (e.g. 0.995 * 10000) from shifting the percentile index
    return means[math.floor(round(n_boot * alpha / 2, 9))], means[math.ceil(round(n_boot * (1 - alpha / 2), 9)) - 1]


def wilcoxon(d, zero="wilcox"):
    """Wilcoxon signed-rank. Returns (statistic, p, exact); statistic and p are None if every d is zero."""
    r = [round(x, 12) for x in d]
    if zero == "wilcox":
        r = [x for x in r if x != 0]
    if not any(r):
        return None, None, True
    order = sorted(range(len(r)), key=lambda i: abs(r[i]))
    ranks = [0.0] * len(r)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and abs(r[order[j + 1]]) == abs(r[order[i]]):
            j += 1
        for k in range(i, j + 1):
            ranks[order[k]] = (i + j) / 2 + 1
        i = j + 1
    # pratt: zeros were ranked above, now their ranks are dropped
    pos = [rk for rk, x in zip(ranks, r) if x > 0]
    neg = [rk for rk, x in zip(ranks, r) if x < 0]
    wp, wm, nz = sum(pos), sum(neg), pos + neg
    if len(nz) <= 50:
        dbl = [int(round(2 * x)) for x in nz]  # average ranks are multiples of 0.5
        total = sum(dbl)
        counts = [1] + [0] * total  # counts[s] = sign assignments whose doubled W+ is s
        for x in dbl:
            for t in range(total, x - 1, -1):
                counts[t] += counts[t - x]
        obs = int(round(2 * abs(wp - wm)))
        hits = sum(c for t, c in enumerate(counts) if abs(2 * t - total) >= obs)
        return min(wp, wm), hits / 2 ** len(nz), True
    mu, sd = sum(nz) / 2, math.sqrt(sum(x * x for x in nz) / 4)  # exact null variance, includes tie correction
    return min(wp, wm), 2 * statistics.NormalDist().cdf(-abs(wp - mu) / sd), False


def ztest(d, alpha=ALPHA):
    """Paired z-test. Returns (z, p, (lo, hi)); z and p are None when SE = 0."""
    n = len(d)
    m = sum(d) / n
    se = statistics.stdev(d) / math.sqrt(n)
    if se == 0:
        return None, None, (m, m)
    q = statistics.NormalDist().inv_cdf(1 - alpha / 2)
    return m / se, 2 * statistics.NormalDist().cdf(-abs(m / se)), (m - q * se, m + q * se)


def _z(alpha, power):
    nd = statistics.NormalDist()
    return nd.inv_cdf(1 - alpha / 2), nd.inv_cdf(power)


def connor_n(pd, delta, alpha=ALPHA, power=0.8):
    """Connor (1987) paired-binary sample size (unrounded); None when delta^2 > pd has no solution."""
    if delta * delta > pd * (1 + 1e-12):  # tolerance: sqrt(pd) ** 2 can land just above pd
        return None
    za, zb = _z(alpha, power)
    return (za * math.sqrt(pd) + zb * math.sqrt(max(0.0, pd - delta * delta))) ** 2 / (delta * delta)


def connor_mde(pd, n, alpha=ALPHA, power=0.8):
    """Smallest delta Connor's equation detects at n, by bisection on (0, sqrt(pd)]; connor_n falls as delta grows.
    None when even delta = sqrt(pd) needs more than n examples."""
    lo, hi = 0.0, math.sqrt(pd)
    if connor_n(pd, hi, alpha, power) > n:
        return None
    for _ in range(100):
        mid = (lo + hi) / 2
        if connor_n(pd, mid, alpha, power) > n:
            lo = mid
        else:
            hi = mid
    return hi


def normal_n(var, delta, alpha=ALPHA, power=0.8):
    """Miller (2024) Eq. 9 with omega^2 = Var(d): unrounded n."""
    za, zb = _z(alpha, power)
    return (za + zb) ** 2 * var / (delta * delta)


def normal_mde(var, n, alpha=ALPHA, power=0.8):
    """Miller (2024) Eq. 10: minimum detectable effect at n."""
    za, zb = _z(alpha, power)
    return (za + zb) * math.sqrt(var / n)


def power_plan(design, value, alpha=ALPHA, power=0.8, effect=0.05, n=None):
    """Power panel numbers. value is p_d (binary) or Var(d) (continuous). With n, adds the MDE and the MDE table."""
    binary = design == "binary"
    out = {"method": CONNOR if binary else MILLER, "mde": None, "n_required": None, "table": []}
    if not value > 0:
        return out
    req = connor_n(value, effect, alpha, power) if binary else normal_n(value, effect, alpha, power)
    out["n_required"] = None if req is None else math.ceil(round(req, 9))  # round: 626.0000000001 is 626
    if req is None:
        out["n_required_note"] = "The target effect is too large for this discordance rate (Connor needs effect² ≤ p_d)."
    if n:
        mde = (lambda m: connor_mde(value, m, alpha, power)) if binary else (lambda m: normal_mde(value, m, alpha, power))
        out["mde"] = mde(n)
        out["table"] = [{"n": m, "mde": mde(m), "current": m == n} for m in sorted(set(MDE_NS) | {n})]
    return out


def verdict(n, p, diff, alpha=ALPHA):
    if n < 2:
        return "Insufficient data (n < 2)"
    if p is not None and p < alpha and diff > 0:
        return "B is better (significant)"
    if p is not None and p < alpha and diff < 0:
        return "B is worse (significant)"
    return "No significant difference"


def analyze(ids, a, b, alpha=ALPHA, threshold=THRESHOLD, seed=0, n_boot=N_BOOT, primary="auto", zero="wilcox"):
    """Paired analysis of per-id means a, b: every test side by side, flips and the explorer rows."""
    n = len(ids)
    d = [y - x for x, y in zip(a, b)]
    binary = all(v in (0.0, 1.0) for v in a + b)
    passed = (lambda v: v == 1.0) if binary else (lambda v: v >= threshold)
    flips = {"improved": [], "regressed": [], "both_pass": 0, "both_fail": 0}
    rows = []
    for i, x, y in zip(ids, a, b):
        pa, pb = passed(x), passed(y)
        if pa == pb:
            flips["both_pass" if pa else "both_fail"] += 1
            status = "unchanged"
        else:
            status = "improved" if pb else "regressed"
            flips[status].append({"id": i, "a": x, "b": y})
        rows.append({"id": i, "a": x, "b": y, "d": y - x, "status": status})
    nb, nc = len(flips["regressed"]), len(flips["improved"])
    ex, mid = mcnemar(nb, nc)
    sf, sf_exact = signflip(d, seed)
    w, wp, w_exact = wilcoxon(d, zero)
    z, zp, zci = ztest(d, alpha) if n >= 2 else (None, None, None)
    at = "" if binary else " (at threshold %g)" % threshold
    tests = [
        {"key": "mcnemar_exact", "label": "Exact McNemar" + at, "b": nb, "c": nc, "statistic": None, "p": ex},
        {"key": "mcnemar_midp", "label": "Exact McNemar (mid-p)" + at, "b": nb, "c": nc, "statistic": None, "p": mid},
        {"key": "signflip", "label": "Paired sign-flip permutation (%s)" % ("exact" if sf_exact else
                                                                           "Monte Carlo, R=%d" % R_PERM),
         "statistic": abs(sum(d)), "p": sf},
        {"key": "wilcoxon", "label": "Wilcoxon signed-rank (%s)" % ("exact" if w_exact else "normal approximation"),
         "statistic": w, "p": wp},
        {"key": "ztest", "label": "Paired z-test", "statistic": z, "p": zp, "ci": zci},
    ]
    if n < 2:
        for t in tests:
            t["p"] = None
    if primary == "auto":
        primary = "mcnemar_midp" if binary else "signflip"
    main = next(t for t in tests if t["key"] == primary)
    p = main["p"]
    diff = sum(d) / n
    ci = bootstrap_ci(d, alpha, n_boot, seed) if n >= 2 else None
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
        "test": main["label"],
        "primary": primary,
        "p_value": p,
        "verdict": verdict(n, p, diff, alpha),
        "alpha": alpha,
        "pd": (nb + nc) / n,  # discordant share, used by the Connor power method
        "var_d": statistics.variance(d) if n >= 2 else None,
        "seed": seed,
        "tests": tests,
        "flips": flips,
        "rows": rows,
        "changes": changes,
        "warnings": warnings,
        "note": note,
    }
