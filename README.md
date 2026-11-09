# evaldiff

Is the difference between two eval runs real? Load a baseline (A) and a candidate (B) results file scored on
the same examples, and evaldiff shows a paired test, a paired bootstrap CI, a verdict and the examples that flipped.

Python 3.9+, standard library only.

## Start

```
cd /Users/raghav/projects/evaldiff
python3 -m evaldiff                              # http://127.0.0.1:8765/
python3 -m evaldiff --port 9000 --host 127.0.0.1
```

## Input

JSONL (one object per line) or CSV/TSV with a header. The id column is the first of `id`, `example_id`,
`sample_id`; the score column is the first of `score`, `passed`, `pass`, `correct`, `value`, `result`
(case-insensitive). Repeated ids are averaged. Example data lives in `fixtures/`. If the columns have other
names, click **Map columns** and pick them.

## Analysis

All paired tests run side by side: exact McNemar (and mid-p), sign-flip permutation, Wilcoxon signed-rank
(`wilcox` or `pratt` zero handling) and a z-test. The settings panel sets alpha, seed, bootstrap resamples, the
pass threshold for continuous scores and which test drives the verdict. The flip explorer filters, searches and
sorts every paired example; click a row to see its raw fields.

The power panel shows the minimum detectable effect at your n and the n needed for a target effect
(Connor for paired binary scores, Miller 2024's paired normal approximation for continuous ones). The
sample-size planner below the results needs no data.

## Tests

```
python3 -m unittest
```
