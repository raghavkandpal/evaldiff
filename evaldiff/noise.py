"""Trial and judge-run noise (spec Sprint 4). Pure functions over cells {id: {trial: [judge scores]}}."""
import statistics

NEEDS_J = "n/a (needs ≥2 judge runs)"
NEEDS_K = "n/a (needs ≥2 trials)"


def _var(v):
    return statistics.variance(v) if len(v) > 1 else None


def _mean(v):
    return sum(v) / len(v) if v else None


def side(cells, ids):
    """Variance components and the noise this side adds to Var(d) at its observed design."""
    cs = [list(cells[i].values()) for i in ids]  # per id: list of cells (one per trial)
    allc = [c for ic in cs for c in ic]
    nested = any(len(c) > 1 for c in allc)
    k, j = _mean([len(ic) for ic in cs]), _mean([len(c) for c in allc])
    multi = [c for c in allc if len(c) > 1]
    sj = _mean([_var(c) for c in multi])
    dis = sum(1 for c in multi if len(set(c)) > 1)
    if nested:  # trial-mean variance contains sigma_J^2 / J; remove it
        tv = [_var([_mean(c) for c in ic]) for ic in cs if len(ic) > 1]
        sg = max(0.0, _mean(tv) - sj / j) if tv else None
    else:
        tv = [_var([c[0] for c in ic]) for ic in cs if len(ic) > 1]
        sg = _mean(tv)
    gen = _mean([(sg or 0) / len(ic) for ic in cs])
    judge = _mean([(sj or 0) * _mean([1 / len(c) for c in ic]) / len(ic) for ic in cs])
    return {"k": k, "j": j, "nested": nested, "sg": sg, "sj": sj, "disagree": dis / len(multi) if multi else None,
            "disagree_n": dis, "disagree_cells": len(multi), "gen": gen, "judge": judge}


def analyze(ids, ca, cb, var_d):
    """The #noise panel numbers. var_d is Var(d) of the per-id differences, or None when n < 2."""
    rows = lambda c: sum(len(x) for i in ids for x in c[i].values())
    if var_d is None or rows(ca) == len(ids) and rows(cb) == len(ids):
        return {"repeated": False}
    a, b = side(ca, ids), side(cb, ids)
    nested = a["nested"] or b["nested"]
    gen, judge = a["gen"] + b["gen"], a["judge"] + b["judge"]
    share = (lambda x: x / var_d) if var_d > 0 else (lambda x: None)
    noise_share = share(gen + judge)
    binary = all(s in (0.0, 1.0) for c in (ca, cb) for i in ids for x in c[i].values() for s in x)
    unstable = []
    if binary:
        frac = lambda c, i: _mean([s for x in c[i].values() for s in x])
        unstable = [{"id": i, "a": frac(ca, i), "b": frac(cb, i)} for i in ids
                    if 0 < frac(ca, i) < 1 or 0 < frac(cb, i) < 1]
    n = len(ids)
    warn = ("Estimated noise exceeds the observed variance of differences (n = %d); the signal variance is "
            "clamped at 0 and the noise estimate is itself uncertain." % n) if gen + judge > var_d + 1e-12 else ""
    return {"repeated": True, "nested": nested, "a": a, "b": b, "var_d": var_d, "se_paired": (var_d / n) ** 0.5,
            "omega2": var_d - gen - judge, "noise_share": noise_share,
            "gen_share": share(gen), "judge_share": share(judge),
            "signal_share": None if noise_share is None else max(0.0, 1 - noise_share),
            "unstable": unstable, "warning": warn}
