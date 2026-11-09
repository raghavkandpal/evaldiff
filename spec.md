# evaldiff: product spec

## 0. Product summary

You changed a prompt or a model, reran your evals, and saw "82% → 85%". evaldiff tells you whether that change is real. You give it two results files scored on the same examples, baseline **A** and candidate **B**. It answers four questions in a local web page:

1. **Is the difference real?** A paired test, a p-value, a paired bootstrap CI and a plain verdict.
2. **What moved?** Which examples flipped from pass to fail and back, and the largest score changes.
3. **How much is noise?** When there are repeated trials or LLM-judge re-runs, or an A/A re-run of the baseline, the variance is split into real signal, generation noise and judge noise.
4. **Could this eval even detect it?** The minimum detectable effect at this n, and the n needed for a target effect.

The methods and the reasons for choosing them are in `RESEARCH.md`. Honest positioning: paired-significance *libraries* already exist (evalci, errorbars, evalsig, and others). evaldiff's edge is a zero-install UI that joins flips, noise decomposition and power in one place.

---

## 1. Global constraints and conventions (apply to every sprint)

### 1.1 Runtime
- Python 3.9+ and the **standard library only**: `http.server`, `json`, `csv`, `random`, `math`, `statistics`. The UI is plain HTML, CSS and vanilla JS served by the same process. No build step, no CDN, no third-party packages. The page must make **no network requests to any host other than the server itself**.
- Deterministic: every bootstrap and Monte Carlo permutation uses `random.Random(seed)`, with **seed 0** by default. The same inputs and settings always give the same numbers.

### 1.2 Start command and port
```
cd /Users/raghav/projects/evaldiff
python3 -m evaldiff            # serves http://127.0.0.1:8765/
python3 -m evaldiff --port 9000 --host 127.0.0.1
```
- On start, print exactly `evaldiff running at http://127.0.0.1:8765/` (with the actual host and port).
- If the port is busy, print `Port 8765 is in use; try --port 8766` and exit with code 2.
- The server also serves `GET /fixtures/<file>` (the repo's `fixtures/` folder) and `GET /api/examples` (the list of examples).

### 1.3 Minimal file layout
```
evaldiff/
  __init__.py
  __main__.py      # arg parsing; `serve` (default). Sprint 7 adds `compare`
  server.py        # http.server handler: static files, /fixtures, /api/*
  parse.py         # JSONL/CSV parsing, validation, pairing
  stats.py         # all statistics (pure functions)
  static/index.html
  static/app.js
  static/style.css
fixtures/          # exact contents in §3
tests/test_stats.py  # unittest; asserts the fixture numbers in §3
README.md
```
Add modules only when a sprint needs them, for example `noise.py` in Sprint 4 or `report.py` in Sprint 7.

### 1.4 How numbers appear on screen (needed for grading)
- Every graded value is in an element with the **id** given in the criteria, for example `<span id="p-value">0.0117</span>`.
- Means, differences, CI bounds and SEs: 4 decimal places. Differences carry a sign: `+0.2000`, `-0.2667`. Exactly zero shows as `0.0000`.
- p-values: 4 decimal places. Values below 0.0001 show `<0.0001`. Undefined values show `n/a`.
- Variances: 6 decimal places. Percentages: 1 decimal place followed by `%`.
- **Grading tolerance:** a displayed value passes if it is within ±1 in its last displayed digit of the expected value, unless a criterion gives a wider window. Bootstrap CIs always come with explicit windows.
- `alpha` defaults to 0.05. A CI's confidence level is `1 − alpha`, and its label shows it, for example `95% paired bootstrap CI`.

### 1.5 Verdict strings (exact)
| Condition | `#verdict` text |
|---|---|
| n_paired < 2 | `Insufficient data (n < 2)` |
| primary p < alpha and mean diff > 0 | `B is better (significant)` |
| primary p < alpha and mean diff < 0 | `B is worse (significant)` |
| otherwise | `No significant difference` |

The verdict always comes from the **primary test's p-value**, never from the CI.

---

## 2. Input formats and edge cases

### 2.1 Files
- **JSONL.** One JSON object per line. Blank lines are skipped.
- **CSV.** A header row, comma-separated, parsed with Python's `csv` module. Files ending `.tsv` are split on tabs.
- **Format detection.** By file extension (`.jsonl`/`.json` is JSONL; `.csv`/`.tsv` is CSV). For pasted text, the format is JSONL if the first non-whitespace character is `{`, otherwise CSV.
- **Header and key matching** is case-insensitive:
  - id column, first match of: `id`, `example_id`, `sample_id`
  - score column, first match of: `score`, `passed`, `pass`, `correct`, `value`, `result`
  - optional: `trial` (Sprint 4), `judge_run` (Sprint 4), `cluster` (Sprint 5), `slice` or `tags` (Sprint 5; `tags` is a JSON list or a `|`-separated string)
  - other columns are kept and shown in row details (Sprint 2)
- **ids** are compared as strings. A JSON number `7` becomes `"7"`.
- **Valid scores:**
  - JSON numbers, finite only
  - JSON booleans (`true` → 1, `false` → 0)
  - strings, trimmed and case-insensitive: `true/pass/passed/yes` → 1, `false/fail/failed/no` → 0, or anything `float()` parses to a finite number
- **Invalid scores:** `null`, empty, `NaN`, `inf`, `-inf`, and non-numeric strings like `abc`. Rows with invalid scores are **excluded**, and the app warns about them (§2.2).
- **Score type.** `binary` if every per-id value on both sides is exactly 0 or 1 after averaging. Otherwise `continuous`. If one side is binary and the other continuous, the comparison is continuous.
- Files larger than 50 MB are rejected with `A: file is larger than 50 MB.`

### 2.2 Edge cases (exact behaviour)
| Case | Behaviour |
|---|---|
| Several rows with the same id on one side | Treated as repeated trials and **averaged per id**. Warning: `N ids have multiple rows in A; scores averaged per id` (or `in B`). |
| Ids in only one file | The analysis uses the intersection. Warnings: `N ids only in A: x4, x5` and `N ids only in B: x6`. List at most the first 10 ids, then `…`. |
| Invalid score rows | Excluded. Warning: `Excluded N rows from A with invalid scores (lines 3, 4, 5)`. Line numbers are 1-based in the file, and the CSV header is line 1. |
| No id column | Error: `A: no id column found (expected one of: id, example_id, sample_id)` (Sprint 1). Sprint 2 shows a column-mapping control instead. |
| No score column | Error: `A: no score column found (expected one of: score, passed, pass, correct, value, result)`. Sprint 2 shows mapping instead. |
| Malformed JSONL line | Error: `A: line N is not valid JSON` or `A: line N is not a JSON object`. The whole file is rejected. |
| Empty file, or no data rows | Error: `A: file contains no rows.` |
| n_paired = 0 | Error: `No example ids match between A and B.` No results panel. |
| n_paired = 1 | Means and diff are shown. Verdict `Insufficient data (n < 2)`. p-value and CI show `n/a`. |
| All paired differences are 0 | Diff `0.0000`, CI `0.0000` to `0.0000`, p-value `1.0000`, verdict `No significant difference`, note `All paired differences are zero.` |
| n_paired < 10 | Warning: `Small sample (n < 10): the bootstrap CI is unreliable; trust the exact test p-value.` |

Errors appear in `#error`. Warnings are `<li>` items in `#warnings`.

### 2.3 Statistics definitions (shared by all sprints)
Let `d_i = B_i − A_i` over the paired ids. Each `A_i` and `B_i` is that id's per-id mean.

- **Mean diff** is `mean(d)`.
- **Exact McNemar.** b = #(A=1, B=0), c = #(A=0, B=1), m = b+c, k = min(b,c), and X ~ Binomial(m, 0.5).
  - exact p = `min(1, 2·P(X ≤ k))`
  - **mid-p** = `min(1, 2·[P(X < k) + 0.5·P(X = k)])`
  - If m = 0, both are 1.
- **Sign-flip permutation.**
  - Statistic: `|Σ d_i|`. Zero differences are kept; flipping them changes nothing.
  - Let z be the number of nonzero d. If z ≤ 16, enumerate all 2^z sign patterns: p = (number of patterns with |Σ| ≥ observed − 1e-9) / 2^z.
  - Otherwise draw R = 10,000 random sign vectors with `random.Random(seed)`: p = (1 + hits)/(1 + R).
  - The label is `Paired sign-flip permutation (exact)` or `(Monte Carlo, R=10000)`.
- **Paired percentile bootstrap.**
  - Draw n indices with replacement B = 10,000 times using one `rng = random.Random(seed)`, each index drawn as `rng.randrange(n)` in order (resample 1's n indices, then resample 2's, …), and take the mean of d for each draw. This exact call sequence is required so the CI windows in §3 hold.
  - Sort the B means: lower = sorted[floor(B·alpha/2)], upper = sorted[ceil(B·(1−alpha/2)) − 1].
- **Wilcoxon signed-rank** (Sprint 2).
  - Round d to 12 decimals before ranking, so float noise does not break ties. Tied |d| values get their average rank.
  - `wilcox` drops zeros. `pratt` ranks the zeros with the rest and then drops their ranks.
  - Statistic = min(W+, W−).
  - If there are ≤ 50 nonzero ranks, p is exact: the two-sided probability that |W+ − W−| ≥ observed, over all sign assignments of the actual ranks. Compute it with a DP over doubled ranks.
  - Otherwise use the normal approximation with tie correction and no continuity correction.
  - If every d is zero, p = `n/a`.
- **z-test.** SE = `stdev(d)/sqrt(n)` with sample stdev (n−1). z = mean/SE, and the two-sided p uses `statistics.NormalDist`. The z CI is mean ± z_{1−α/2}·SE.
- **Thresholded flips** for continuous scores: pass means score ≥ threshold, default 0.5. For binary scores, pass means score = 1.

---

## 3. Fixtures (exact contents; the generator creates these in `fixtures/`)

Expected values were derived by hand and can be cross-checked with scipy (≥ 1.15 for Wilcoxon): `scipy.stats.binomtest`, `wilcoxon`, `permutation_test`, `norm`.

### F1: binary, CSV, n = 20, not significant
`fixtures/f1_a.csv` and `fixtures/f1_b.csv`. Each has the header `id,score`, then one line per id in this order:

| ids | A | B |
|---|---|---|
| q01 … q11 | 1 | 1 |
| q12, q13, q14 | 0 | 0 |
| q15 | 1 | 0 |
| q16 … q20 | 0 | 1 |

Expected values:
- mean A 0.6000, mean B 0.8000, diff +0.2000
- b = 1, c = 5, both pass 11, both fail 3
- exact McNemar p 0.21875, mid-p 0.12500, sign-flip p 0.21875 (exact, z = 6)
- Wilcoxon (wilcox) p 0.21875, statistic 3.5
- stdev(d) 0.523148, SE 0.116980, z-test p 0.0873, z CI [−0.0293, +0.4293]
- bootstrap 95% CI: lower in [−0.10, 0.00], upper in [0.35, 0.50]
- Power (§Sprint 3): p_d 0.3000, MDE 0.3233 ± 0.003

### F2: binary, JSONL, `passed` booleans, with `slice`, n = 30, significant
`fixtures/f2_a.jsonl`, `fixtures/f2_b.jsonl` and `fixtures/f2_a_rerun.jsonl`. Each line has the form `{"id":"m01","passed":true,"slice":"math"}`, in the id order of this table (T = true, F = false):

| ids | slice | A | A_rerun | B |
|---|---|---|---|---|
| m01, m02, m03 | math | T | T | T |
| m04, m05 | math | F | F | F |
| m06 … m10 | math | F | F | T |
| k01, k02 | code | T | **F** | T |
| k03 … k12 | code | T | T | T |
| k13, k14 | code | F | **T** | F |
| k15 | code | F | F | F |
| k16 | code | T | T | F |
| k17 … k20 | code | F | F | T |

Expected values, A vs B:
- mean A 0.5333, mean B 0.8000, diff +0.2667
- b = 1, c = 9, both pass 15, both fail 5
- exact p 0.021484, mid-p 0.011719, sign-flip 0.021484, Wilcoxon 0.021484
- stdev(d) 0.520830, SE 0.095090, z = 2.8044, z-test p 0.0050 ± 0.0003, z CI [+0.0803, +0.4530]
- bootstrap 95% CI: lower in [0.0333, 0.1334] (must be > 0), upper in [0.40, 0.50]
- Var(d) = 0.271264

Slices (Sprint 5):

| slice | n | A | B | diff | b | c | mid-p | Holm |
|---|---|---|---|---|---|---|---|---|
| math | 10 | 0.3000 | 0.8000 | +0.5000 | 0 | 5 | 0.03125 | 0.0625 |
| code | 20 | 0.6500 | 0.8000 | +0.1500 | 1 | 4 | 0.21875 | 0.21875 |

Power (Sprint 3), with alpha 0.05, power 0.80, target δ 0.05:
- p_d 0.3333, MDE 0.2839 ± 0.003, required n 1045 ± 3

A vs A_rerun (Sprint 6):
- 2 flips each way (4 of 30 = 13.3%), diff 0.0000
- exact p and mid-p both 1.0000
- Var(d_AA) 0.137931, noise share Var(d_AA)/Var(d_AB) = 50.8%

A_rerun vs B (Sprint 6): b = 3, c = 11, mid-p 0.035156, diff +0.2667.

### F3: continuous, JSONL, with clusters and a second metric, n = 8
`fixtures/f3_a.jsonl` and `fixtures/f3_b.jsonl`. Each line has the form `{"id":"c01","score":0.4,"alt_score":0.4,"cluster":"doc1"}`. In **both** files, `alt_score` equals **A's** score, so it does not change between A and B.

| id | cluster | A score | B score | d |
|---|---|---|---|---|
| c01 | doc1 | 0.4 | 0.8 | 0.40 |
| c02 | doc1 | 0.5 | 0.85 | 0.35 |
| c03 | doc2 | 0.3 | 0.6 | 0.30 |
| c04 | doc2 | 0.6 | 0.85 | 0.25 |
| c05 | doc3 | 0.2 | 0.4 | 0.20 |
| c06 | doc3 | 0.7 | 0.85 | 0.15 |
| c07 | doc4 | 0.5 | 0.6 | 0.10 |
| c08 | doc4 | 0.6 | 0.55 | −0.05 |

Expected values:
- mean A 0.4750, mean B 0.6875, diff +0.2125
- sign-flip exact p 0.015625 (4/256)
- Wilcoxon: statistic 1, exact p 0.015625
- stdev(d) 0.145774, SE 0.051539, z-test p < 0.0001, z CI [+0.1115, +0.3135]
- bootstrap 95% CI: lower in [0.08, 0.16], upper in [0.26, 0.34]

Flips at threshold 0.5:
- improved: c01, c03
- regressed: none
- McNemar at threshold: b = 0, c = 2, exact 0.5000, mid-p 0.2500

Flips at threshold 0.6:
- improved: c01, c02, c03, c07
- regressed: c08
- McNemar: exact 0.3750, mid-p 0.2188

Power: Var(d) 0.021250, MDE 0.1444 ± 0.001, required n for δ 0.05 is 67 ± 1, and for δ 0.10 is 17 ± 1.

Clusters (Sprint 5):
- naive plug-in SE 0.0482, clustered SE 0.0647, ratio 1.34
- cluster sign-flip p 0.1250 (cluster sums of d are 0.75, 0.55, 0.35, 0.05)

Metrics (Sprint 5):
- `score`: p 0.0156, Holm 0.0313
- `alt_score`: diff 0.0000, p 1.0000, Holm 1.0000

### F4: repeated trials, continuous, n = 4, K = 2
`fixtures/f4_a.jsonl` and `fixtures/f4_b.jsonl`. Each line has the form `{"id":"r1","trial":1,"score":0.2}`.

| id | A trial 1, trial 2 | B trial 1, trial 2 |
|---|---|---|
| r1 | 0.2, 0.4 | 0.6, 0.6 |
| r2 | 0.5, 0.5 | 0.6, 0.8 |
| r3 | 0.6, 0.8 | 0.8, 0.8 |
| r4 | 0.1, 0.1 | 0.4, 0.6 |

Expected values:
- per-id means A: 0.3, 0.5, 0.7, 0.1, so mean A 0.4000
- per-id means B: 0.6, 0.7, 0.8, 0.5, so mean B 0.6500
- d = 0.3, 0.2, 0.1, 0.4, so diff +0.2500
- sign-flip exact p 0.1250
- bootstrap 95% CI: lower in [0.10, 0.20], upper in [0.30, 0.40]. The CI excludes 0 even though p = 0.125, which demonstrates the small-n warning.

Noise (Sprint 4):
- within-example variance σ_A² = 0.010000 and σ_B² = 0.010000 (mean over ids of the sample variance across trials)
- noise term σ_A²/2 + σ_B²/2 = 0.010000
- Var(d) = 0.016667, so trial-noise share is 60.0% and signal ω² = 0.006667
- paired SE = 0.0645
- what-if K = 4: projected Var(d) 0.011667, projected SE 0.0540

### F6: continuous, CSV, zeros, Pratt vs Wilcox
`fixtures/f6_a.csv` and `fixtures/f6_b.csv`, header `id,score`:

| id | A | B | d |
|---|---|---|---|
| w1 | 0.5 | 0.5 | 0 |
| w2 | 0.4 | 0.5 | 0.1 |
| w3 | 0.3 | 0.5 | 0.2 |
| w4 | 0.2 | 0.5 | 0.3 |
| w5 | 0.9 | 0.5 | −0.4 |

Expected values:
- diff +0.0400
- sign-flip exact p 0.8750 (14/16)
- Wilcoxon `wilcox`: statistic 4, p 0.8750
- Wilcoxon `pratt`: statistic 5, p 0.7500
- verdict `No significant difference`

### F7: generation trials × judge re-runs, binary, n = 3, K = 2, J = 2
`fixtures/f7_a.jsonl` and `fixtures/f7_b.jsonl`. Each line has the form `{"id":"j1","trial":1,"judge_run":1,"score":1}`. The table lists judge runs 1 and 2:

| id | A trial 1 | A trial 2 | B trial 1 | B trial 2 |
|---|---|---|---|---|
| j1 | 1, 1 | 1, 0 | 1, 1 | 1, 1 |
| j2 | 0, 0 | 0, 1 | 1, 0 | 1, 1 |
| j3 | 1, 1 | 0, 0 | 1, 1 | 1, 1 |

Expected values:
- per-id means A: 0.75, 0.25, 0.50, so mean A 0.5000
- per-id means B: 1.00, 0.75, 1.00, so mean B 0.9167
- diff +0.4167, sign-flip exact p 0.2500

Noise (Sprint 4):
- judge variance σ_J² (mean over (id, trial) of the sample variance across judge runs): A 0.166667, B 0.083333
- judge disagreement rate (share of (id, trial) cells whose judge runs disagree): A 33.3% (2 of 6), B 16.7% (1 of 6)
- generation variance σ_G² = mean over ids of the sample variance of the trial means, minus σ_J²/J, clamped at 0: A 0.166667, B 0.000000
- Var(d) 0.020833
- generation share (σ_GA²/K + σ_GB²/K)/Var(d) = 400.0%
- judge share (σ_JA²/(KJ) + σ_JB²/(KJ))/Var(d) = 300.0%
- signal share 0.0%
- warning that noise exceeds the observed variance (see Sprint 4)
- unstable examples (0 < pass fraction < 1): A has j1, j2, j3; B has j2

### BIG: performance, binary, n = 2000
`fixtures/big_a.jsonl` and `fixtures/big_b.jsonl`. For i = 0 … 1999:
- id is `"b%04d" % i`
- A score is `1 if (7*i) % 10 < 6 else 0`
- B score is `1 if (7*i + 3) % 10 < 7 else 0`

Each line has the form `{"id":"b0000","score":1}`.

Expected values:
- mean A 0.6000, mean B 0.7000, diff +0.1000
- b = 400, c = 600, mid-p `<0.0001`
- verdict `B is better (significant)`

### Example selector
`GET /api/examples` returns these entries, and `#example-select` shows them as options. Loading an example fills A and B, or A, B and A′ where it applies.

| value | label | files |
|---|---|---|
| `f1` | F1 binary n=20 (CSV) | f1_a.csv, f1_b.csv |
| `f2` | F2 binary n=30 (JSONL) | f2_a.jsonl, f2_b.jsonl |
| `f3` | F3 continuous n=8 | f3_a.jsonl, f3_b.jsonl |
| `f4` | F4 repeated trials | f4_a.jsonl, f4_b.jsonl |
| `f6` | F6 zeros (Wilcoxon) | added in Sprint 2 |
| `f7` | F7 trials × judge runs | added in Sprint 4 |
| `f2aa` | F2 with A/A re-run | added in Sprint 6 (A, B, A′ = f2_a_rerun) |
| `big` | BIG n=2000 | big_a.jsonl, big_b.jsonl |

---

## 4. Sprints

Each sprint is built, committed, and graded on its own through the browser. Criteria from earlier sprints must keep passing.

**Generator obligations (not graded through the UI, but required):**
- `tests/test_stats.py`, runnable with `python3 -m unittest`, asserts every §3 number that the sprint introduces.
- The README gives the start command.

---

### Sprint 1: Paired verdict, CI and flips (smallest useful slice)

**Goal.** Load two files in the browser and see whether B really beats A, with a CI and the examples that flipped.

**Scope.**
- Server and start command (§1.2).
- Parsing and every §2.2 edge case.
- Score-type detection.
- Primary test: mid-p McNemar for binary scores, sign-flip permutation for continuous ones.
- Paired bootstrap CI with seed 0, B = 10,000.
- Verdict, flip tables, and the example selector (f1, f2, f3, f4, big).
- A swap button.
- Fixed settings: alpha 0.05 and threshold 0.5.

**UI elements:**
- Inputs: `#file-a`, `#file-b` (file inputs), `#paste-a`, `#paste-b` (textareas), `#example-select`, `#load-example`, `#swap-btn`, `#compare-btn`.
- Results: `#verdict`, `#n-paired`, `#score-type`, `#mean-a`, `#mean-b`, `#diff`, `#ci-label`, `#ci-low`, `#ci-high`, `#test-name`, `#p-value`, `#seed`, `#count-improved`, `#count-regressed`, `#count-both-pass`, `#count-both-fail`, `#improved-table`, `#regressed-table` (rows are `tr[data-id]`), `#changes-table` (continuous only: top 20 by |d|, with columns id, A, B, Δ).
- Messages: `#warnings`, `#error`, `#note`.
- File input takes precedence over paste. Loading an example fills the paste areas with the file text and shows the file names.

**Acceptance criteria.**
1. Running `python3 -m evaldiff` prints `evaldiff running at http://127.0.0.1:8765/`. Opening that URL shows a page titled `evaldiff` with two panels headed `Baseline (A)` and `Candidate (B)`, each with a file input and a paste textarea, and a `Compare` button.
2. Uploading `fixtures/f1_a.csv` to `#file-a` and `fixtures/f1_b.csv` to `#file-b` and clicking Compare shows `#n-paired` = `20`, `#score-type` = `binary`, `#mean-a` = `0.6000`, `#mean-b` = `0.8000` and `#diff` = `+0.2000`.
3. F1 shows `#test-name` = `Exact McNemar (mid-p)`, `#p-value` = `0.1250` and `#verdict` = `No significant difference`.
4. F1 shows `#ci-label` = `95% paired bootstrap CI`, `#seed` = `0`, `#ci-low` in [−0.10, 0.00] and `#ci-high` in [0.35, 0.50].
5. F1 shows `#count-improved` = `5`, `#count-regressed` = `1`, `#count-both-pass` = `11` and `#count-both-fail` = `3`. `#improved-table` contains exactly the rows q16, q17, q18, q19, q20, and `#regressed-table` contains exactly q15.
6. Choosing `f2` in `#example-select`, clicking `#load-example`, then Compare shows:
   - n `30`, mean A `0.5333`, mean B `0.8000`, diff `+0.2667`
   - p `0.0117`, verdict `B is better (significant)`
   - `#ci-low` in [0.0333, 0.1334] and greater than 0, `#ci-high` in [0.40, 0.50]
   - improved `9`, regressed `1`
7. After the F2 comparison, clicking `#swap-btn` then Compare shows diff `-0.2667`, p `0.0117`, verdict `B is worse (significant)`, improved `1` and regressed `9`.
8. Example `f3` shows:
   - `#score-type` = `continuous`, n `8`, mean A `0.4750`, mean B `0.6875`, diff `+0.2125`
   - `#test-name` = `Paired sign-flip permutation (exact)`, p `0.0156`, verdict `B is better (significant)`
   - `#ci-low` in [0.08, 0.16], `#ci-high` in [0.26, 0.34]
   - `#improved-table` = c01, c03, and `#regressed-table` empty
   - the first row of `#changes-table` is c01 with Δ `+0.4000`
9. Example `f4` shows:
   - warnings containing `4 ids have multiple rows in A; scores averaged per id` and the same for B
   - n `4`, mean A `0.4000`, mean B `0.6500`, diff `+0.2500`
   - p `0.1250`, verdict `No significant difference`
   - a warning containing `Small sample (n < 10)`
10. Clicking Compare twice on F1 gives identical `#ci-low` and `#ci-high` both times. Reloading the page and comparing F1 again gives the same values.
11. Mismatched ids. Paste this into A:
    ```
    id,score
    x1,1
    x2,0
    x3,1
    x4,1
    x5,0
    ```
    and this into B:
    ```
    id,score
    x1,1
    x2,1
    x3,1
    x6,0
    ```
    Compare shows n `3`, mean A `0.6667`, mean B `1.0000`, diff `+0.3333`, p `0.5000`, and warnings containing `2 ids only in A: x4, x5` and `1 ids only in B: x6`. The text `1 id only in B` is also accepted.
12. Invalid scores. Paste this into A:
    ```
    id,score
    v1,1
    v2,abc
    v3,NaN
    v4,
    v5,0
    ```
    and into B the lines `id,score`, `v1,1`, `v2,1`, `v3,1`, `v4,1`, `v5,1`. Compare shows a warning containing `Excluded 3 rows from A with invalid scores (lines 3, 4, 5)`, a warning that `3 ids only in B`, n `2`, diff `+0.5000` and p `0.5000`.
13. No overlap: A = `id,score` / `a1,1` / `a2,0`, B = `id,score` / `b1,1` / `b2,0`. `#error` shows `No example ids match between A and B.` and `#verdict` is empty or hidden.
14. n = 1: A = `id,score` / `s1,1`, B = `id,score` / `s1,0`. This shows n `1`, diff `-1.0000`, `#p-value` = `n/a` and verdict `Insufficient data (n < 2)`.
15. All ties: uploading `f1_a.csv` as both A and B shows diff `0.0000`, `#ci-low` = `0.0000`, `#ci-high` = `0.0000`, p `1.0000`, verdict `No significant difference`, and `#note` containing `All paired differences are zero.`
16. Bad input files:
    - A = `name,score` / `z1,1` shows `#error` = `A: no id column found (expected one of: id, example_id, sample_id)`.
    - A = `{"id":"z1","score":1}` followed by a second line `{bad json` shows `A: line 2 is not valid JSON`.
    - An empty A shows `A: file contains no rows.`
17. Example `big` gives n `2000`, diff `+0.1000`, p `<0.0001` and verdict `B is better (significant)`. Results appear within 10 seconds of clicking Compare.
18. During criteria 1–17, the browser's network log shows no requests to any host other than 127.0.0.1:8765.

**Sprint 1 total: 18 criteria.**

---

### Sprint 2: Full test battery, settings, column mapping and flip explorer

**Goal.** Let users see every reasonable paired test side by side, tune the analysis, handle files with unusual column names, and dig into why examples flipped.

**Scope.**
- `#tests-table` with one row per test, each `tr[data-test]`, with columns statistic and p. Rows: `mcnemar_exact`, `mcnemar_midp` (for continuous data these are computed at the threshold and labelled `(at threshold 0.5)`), `signflip`, `wilcoxon`, `ztest` (with its z CI).
- Settings panel:
  - `#alpha` (0.01, 0.05 or 0.10)
  - `#seed` (integer)
  - `#n-boot` (1,000 to 100,000)
  - `#threshold`
  - `#primary-test` (`auto`, or any test row)
  - `#wilcoxon-zero` (`wilcox` or `pratt`)
  - Recomputes when Compare is clicked.
- Column mapping: when the id or score column can't be auto-detected, or the user clicks `#map-columns`, show `#map-a-id`, `#map-a-score`, `#map-b-id` and `#map-b-score` selects listing the file's headers.
- Flip explorer:
  - filter buttons `#filter-all`, `#filter-improved`, `#filter-regressed` and `#filter-unchanged` over one `#rows-table`
  - `#search-id`
  - sorting by Δ when the `Δ` header is clicked
  - clicking a row opens `#row-detail` with every raw field from A's and B's rows
- A plain-language summary in `#summary`: `{improved} improved, {regressed} regressed, {unchanged} unchanged. If A and B were equally good, a difference at least this large would occur with probability {p}.`
- Add example `f6`.

**Acceptance criteria.**
1. On F1, `#tests-table` shows:
   - `mcnemar_exact` p `0.2188`, `mcnemar_midp` p `0.1250`, `signflip` p `0.2188`
   - `wilcoxon` p `0.2188` with statistic `3.5`
   - `ztest` p `0.0873` and z CI `-0.0293` to `+0.4293`
2. On F2, `#tests-table` shows exact `0.0215`, mid-p `0.0117`, signflip `0.0215`, wilcoxon `0.0215`, ztest `0.0050` (±0.0003) and z CI `+0.0803` to `+0.4530`.
3. On F3:
   - `wilcoxon` statistic `1`, p `0.0156`
   - `signflip` `0.0156`
   - ztest p `<0.0001` and z CI `+0.1115` to `+0.3135`
   - the McNemar rows are labelled `(at threshold 0.5)`, with exact `0.5000` and mid-p `0.2500`
4. On F6 with `#wilcoxon-zero` = `wilcox`, the wilcoxon row shows statistic `4` and p `0.8750`. With `pratt` it shows statistic `5` and p `0.7500`. signflip is `0.8750`, diff `+0.0400`, verdict `No significant difference`.
5. Setting `#primary-test` to `wilcoxon` on F3 shows `#test-name` = `Wilcoxon signed-rank (exact)` and p `0.0156`. Setting it to `mcnemar_exact` on F1 shows p `0.2188`.
6. Setting `#alpha` = `0.01` on F2 shows verdict `No significant difference` and `#ci-label` = `99% paired bootstrap CI`. Setting it back to `0.05` restores `B is better (significant)`.
7. Setting `#seed` = `7` on F1 changes nothing except the CI values; `#seed` shows `7`. Setting the seed back to `0` reproduces the Sprint 1 CI values exactly.
8. Setting `#threshold` = `0.6` on F3 shows improved c01, c02, c03, c07, regressed c08, McNemar exact `0.3750` and mid-p `0.2188`.
9. Column mapping:
   - Pasting A = `qid,judge_score` / `a,1` / `b,0` / `c,1` and B = `qid,judge_score` / `a,1` / `b,1` / `c,1` shows the mapping selects instead of an error.
   - Choosing `qid` and `judge_score` for both sides and clicking Compare shows n `3` and diff `+0.3333`.
10. Mapping on F3: clicking `#map-columns` and choosing `alt_score` as the score on both sides shows diff `0.0000`, p `1.0000`, `No significant difference` and the note `All paired differences are zero.`
11. On F2, `#filter-regressed` leaves exactly one row (k16) in `#rows-table`. `#filter-improved` leaves 9. Typing `m0` in `#search-id` with `All` selected leaves exactly the 9 rows m01 to m09.
12. On F2, clicking row k16 opens `#row-detail` showing A's fields `passed: true, slice: code` and B's `passed: false, slice: code`.
13. On F3, clicking the `Δ` header sorts `#rows-table` ascending, with c08 (`-0.0500`) first. Clicking it again sorts descending, with c01 first.
14. On F2, `#summary` reads exactly `9 improved, 1 regressed, 20 unchanged. If A and B were equally good, a difference at least this large would occur with probability 0.0117.`
15. Entering `#n-boot` = `500` shows an inline validation message `Bootstrap resamples must be between 1000 and 100000` and doesn't run.

---

### Sprint 3: Power and sample-size planner

**Goal.** Tell users whether this eval could have detected the effect they care about, and how many examples they would need.

**Scope.** A `#power` panel under the results:
- Inputs: `#target-power` (default 0.80) and `#target-effect` (default 0.05). Alpha comes from settings.
- Binary method: `Connor (paired binary)`, using the observed `p_d = (b+c)/n`. MDE comes from solving Connor's equation for δ at the current n by bisection.
- Continuous method: `Paired normal approximation (Miller 2024)`, using Var(d) with the sample variance.
- Outputs:
  - `#power-method`, `#pd` or `#var-d`
  - `#mde`, `#n-required`
  - `#mde-table`: rows for n = 50, 100, 200, 500, 1000, 2000 and the current n (marked `current`)
  - `#mde-chart`: an inline SVG line chart of MDE against n with a marker at the current n
- If the result is not significant and |diff| < MDE, `#power-note` says `The observed difference is smaller than the minimum detectable effect at this n; a non-significant result here is not evidence of no effect.`
- If p_d = 0 or Var(d) = 0, `#mde` shows `n/a`, with the message `No variation between A and B; enter an assumed discordance rate or SD` and a `#assumed-pd` or `#assumed-sd` input.
- A standalone planner tab `#plan-tab`, which needs no data. Inputs: `#plan-design` (binary or continuous), `#plan-pd` or `#plan-sd`, `#plan-effect`. Outputs `#plan-n` and `#plan-mde-at-n` for a `#plan-n-input`.
- No "observed power" is shown anywhere. `RESEARCH.md` §5 explains why.

**Acceptance criteria.**
1. On F2, `#power-method` = `Connor (paired binary)`, `#pd` = `0.3333`, `#mde` = `0.2839` (±0.003) and `#n-required` = `1045` (±3) for target effect 0.05 and power 0.80.
2. On F1, `#pd` = `0.3000`, `#mde` = `0.3233` (±0.003), and `#power-note` shows the exact sentence in the scope above.
3. On F2, which is significant, `#power-note` is empty or hidden.
4. On F3, `#power-method` = `Paired normal approximation (Miller 2024)`, `#var-d` = `0.021250`, `#mde` = `0.1444` (±0.001) and `#n-required` = `67` (±1). Changing `#target-effect` to `0.10` gives `17` (±1).
5. On F3, `#mde-table` has 7 rows. The row marked `current` has n `8` and MDE `0.1444`. MDE strictly decreases as n increases down the table.
6. `#mde-chart` is an `<svg>` containing at least 6 plotted points and a visible marker labelled `current`.
7. Comparing `f1_a.csv` against itself shows `#mde` = `n/a` and the message `No variation between A and B; enter an assumed discordance rate or SD`. Entering `#assumed-pd` = `0.2` shows `#n-required` = `626` (±3) for effect 0.05.
8. In `#plan-tab`, choosing binary with `#plan-pd` 0.2 and `#plan-effect` 0.05 shows `#plan-n` = `626` (±3). Choosing continuous with `#plan-sd` 0.3 and effect 0.05 shows `283` (±1).
9. Changing `#target-power` to `0.90` on F3 makes `#n-required` larger than at 0.80. Expected 90 ± 1: 1.959964 + 1.281552 = 3.241516, squared is 10.5074, × 0.02125 / 0.0025 = 89.31, so 90.
10. No element on the page contains the text `observed power`.

---

### Sprint 4: Repeated trials and LLM-judge noise

**Goal.** When files contain repeated generations (`trial`) and/or judge re-runs (`judge_run`), show how much of the A/B difference variance is real signal and how much is generation or judge randomness. Also show how more trials or judge runs would shrink the SE.

**Scope.** A `#noise` panel. It appears when any id has more than one row. Rows are keyed by (id, trial, judge_run). A missing `trial` means trial 1, and a missing `judge_run` means run 1. Duplicate rows with no trial column count as trials.

Per side, the panel shows:
- `#k-a` and `#k-b`: mean trials per id, and `#j-a` and `#j-b`: mean judge runs per (id, trial)
- `#sigma2-a` and `#sigma2-b`: total within-example variance, used when there is no judge_run
- `#sigmaj-a` and `#sigmaj-b`, `#sigmag-a` and `#sigmag-b`: the nested decomposition from §3 F7
- `#judge-disagree-a` and `#judge-disagree-b`

Combined, it shows:
- `#var-d`, `#noise-share` (trial-only designs), `#gen-share` and `#judge-share` (nested designs), `#signal-share`, `#omega2`
- `#unstable-table`: ids whose binary pass fraction lies strictly between 0 and 1 on either side, with columns id, A fraction, B fraction
- What-if inputs `#whatif-k` and `#whatif-j`, giving `#whatif-se` = sqrt((ω²₊ + noise(K′, J′))/n), where ω²₊ = max(0, ω²)
- `#noise-warning` when the noise estimate exceeds Var(d)
- When there is exactly one judge run, or only one trial, the part that can't be identified shows `n/a (needs ≥2 judge runs)` or `n/a (needs ≥2 trials)`.
- Unbalanced designs: the noise term is the mean over ids of σ_i²/K_i, and ids with K_i = 1 are left out of the σ² estimate.

Power (Sprint 3) uses ω² + noise/K′ when trials exist, and `#power-method` adds ` with trials`. Add example `f7`.

**Acceptance criteria.**
1. On F4, `#noise` is visible with `#k-a` = `2`, `#k-b` = `2`, `#sigma2-a` = `0.010000`, `#sigma2-b` = `0.010000`, `#var-d` = `0.016667`, `#noise-share` = `60.0%`, `#signal-share` = `40.0%` and `#omega2` = `0.006667`.
2. On F4, the paired SE shown in `#se-paired` is `0.0645`. Setting `#whatif-k` = `4` shows `#whatif-se` = `0.0540`. A larger K′ always gives a smaller `#whatif-se`, but never below sqrt(ω²/n) = `0.0408`.
3. On F7:
   - `#j-a` = `2`, `#sigmaj-a` = `0.166667`, `#sigmaj-b` = `0.083333`
   - `#sigmag-a` = `0.166667`, `#sigmag-b` = `0.000000`
   - `#judge-disagree-a` = `33.3%`, `#judge-disagree-b` = `16.7%`
4. On F7, `#var-d` = `0.020833`, `#gen-share` = `400.0%`, `#judge-share` = `300.0%` and `#signal-share` = `0.0%`. `#noise-warning` contains `Estimated noise exceeds the observed variance of differences` and `n = 3`.
5. On F7, `#unstable-table` lists j1, j2 and j3. j2 shows A `0.25` and B `0.75`, j1 shows A `0.75` and B `1.00`, and j3 shows A `0.50` and B `1.00`.
6. On F7, mean A `0.5000`, mean B `0.9167`, diff `+0.4167`, p `0.2500`.
7. On F1, where every id has one row, `#noise` shows the text `No repeated trials or judge re-runs found.` and no variance numbers.
8. Deleting all trial-2 rows from F4 (paste the trial-1 rows only) hides the noise numbers and shows the same message as criterion 7.
9. On F4, `#power-method` ends with ` with trials`. Changing `#whatif-k` to `4` lowers `#mde`.
10. Clicking a row in `#unstable-table` opens `#row-detail` listing every trial and judge row for that id on both sides. For F7 j2, that is 4 rows for A and 4 for B.

---

### Sprint 5: Clusters, slices and multiple metrics

**Goal.** Handle correlated examples (several questions per document), per-slice breakdowns, and several score columns, without fooling users through multiple testing.

**Scope.**

Clusters, when there is a `cluster` column. A `#cluster` panel shows:
- `#n-clusters`
- `#se-naive` (plug-in, `sqrt(Σ(d−d̄)²)/n`) and `#se-clustered` (Miller Eq. 8), plus `#se-ratio`
- `#cluster-p`: sign-flip on cluster sums of d, exact when ≤ 16 clusters
- `#cluster-ci`: a cluster bootstrap that resamples clusters, with the seed from settings
- `#cluster-warning` when there are fewer than 10 clusters
- A `#use-clusters` checkbox. When it is on, the verdict uses `#cluster-p`.

Slices, from a `slice` column or `tags`. `#slices-table` has one row per slice (`tr[data-slice]`) with columns n, mean A, mean B, diff, p (the primary test within the slice), Holm-adjusted p and a significant flag computed from the Holm p. The rows are sortable. An id with several tags belongs to every one of them.

Metrics: `#metric-select` lists every numeric column found in both files. `#metrics-table` (`tr[data-metric]`) shows diff, p and Holm p for every metric at once.

**Acceptance criteria.**
1. On F3, `#n-clusters` = `4`, `#se-naive` = `0.0482`, `#se-clustered` = `0.0647` and `#se-ratio` = `1.34`.
2. On F3, `#cluster-p` = `0.1250` and `#cluster-warning` contains `Fewer than 10 clusters`.
3. On F3, checking `#use-clusters` changes `#verdict` from `B is better (significant)` to `No significant difference` and `#p-value` to `0.1250`. Unchecking restores the original.
4. On F3, `#cluster-ci` shows two numbers with lower ≤ upper, and the interval is at least as wide as the unclustered bootstrap CI. Changing the seed and back to 0 reproduces it.
5. On F2, `#slices-table` row `math` shows n `10`, mean A `0.3000`, mean B `0.8000`, diff `+0.5000`, p `0.0313` (0.0312 also accepted), Holm `0.0625`, and is not marked significant.
6. On F2, row `code` shows n `20`, mean A `0.6500`, mean B `0.8000`, diff `+0.1500`, p `0.2188` and Holm `0.2188`.
7. On F3, `#metrics-table` shows `score` with p `0.0156` and Holm `0.0313` (0.0312 also accepted), and `alt_score` with diff `0.0000`, p `1.0000` and Holm `1.0000`.
8. On F3, choosing `alt_score` in `#metric-select` updates the main verdict to `No significant difference`.
9. On F1, which has no cluster, slice or extra metric columns, `#cluster` and `#slices-table` are hidden, and `#metrics-table` has exactly one row (`score`).
10. With tags, paste A = `id,score,tags` / `t1,0,x|y` / `t2,1,x` / `t3,0,y` and B = `id,score,tags` / `t1,1,x|y` / `t2,1,x` / `t3,1,y`. `#slices-table` shows slice `x` with n `2` and slice `y` with n `2`.

---

### Sprint 6: Multiple candidates and the A/A noise floor

**Goal.** Compare one baseline against several candidates with correct multiple-testing control. Also measure run-to-run noise from a plain re-run of the baseline when there are no repeated trials.

**Scope.**

Multiple candidates:
- `#add-candidate` adds candidate slots B2, B3 and so on, up to 8 in total. Each slot has a file input and a paste area (`#file-b2`, `#paste-b2`, …).
- `#candidates-table` (`tr[data-candidate]`, labelled by file name) shows diff, CI, p, Holm p and verdict for each candidate against A.
- `#pairwise` toggle: all pairs among {A, candidates}, Holm-corrected over every pair.

Noise floor:
- A `Baseline re-run (A′)` slot, with `#file-a2` and `#paste-a2`.
- When it is filled, `#aa-panel` shows:
  - `#aa-discordant`, shaped like `4 of 30 (13.3%)`
  - `#aa-p`: the primary test of A against A′
  - `#aa-var` = Var(d_AA) and `#ab-var` = Var(d_AB)
  - `#aa-noise-share` = Var(d_AA)/Var(d_AB)
  - `#aa-expected-flips` = the number of A/A discordant pairs, with the sentence `About {k} of the {m} A/B flips could be run-to-run noise.`
  - If the A/A comparison is itself significant, `#aa-warning` = `A and its re-run differ significantly: your pipeline changed between runs or is not comparable.`

Add example `f2aa`.

**Acceptance criteria.**
1. Baseline f2_a with candidates f2_b and f2_a_rerun. Candidate rows are labelled by file name (or by example file name when loaded through the example selector).
   - The `f2_b.jsonl` row shows diff `+0.2667`, p `0.0117`, Holm `0.0234` and verdict `B is better (significant)`.
   - The `f2_a_rerun.jsonl` row shows diff `0.0000`, p `1.0000`, Holm `1.0000` and `No significant difference`.
2. In the same setup, turning on `#pairwise` shows 3 rows:
   - A vs f2_b: p `0.0117`, Holm `0.0352`
   - f2_a_rerun vs f2_b: p `0.0352`, Holm `0.0703`, not significant
   - A vs f2_a_rerun: p `1.0000`, Holm `1.0000`
3. Loading example `f2aa` and comparing shows `#aa-discordant` = `4 of 30 (13.3%)`, `#aa-p` = `1.0000`, `#aa-var` = `0.137931`, `#ab-var` = `0.271264` and `#aa-noise-share` = `50.8%`.
4. On `f2aa`, the A/A panel contains `About 4 of the 10 A/B flips could be run-to-run noise.`, and `#aa-warning` is hidden.
5. Using f2_a as A and f2_b as the "re-run" A′ shows `#aa-warning` with the exact text above.
6. With one candidate, the page behaves exactly as in Sprint 1. The Sprint 1 criteria still pass, and `#candidates-table` is hidden.
7. `#add-candidate` adds slots up to 8 candidates, after which it is disabled.
8. Removing a candidate slot (its `×` button) and comparing again removes its row and recomputes Holm. With only f2_b remaining, Holm equals the raw p `0.0117`.

---

### Sprint 7: Reports, history, CI gate and CLI

**Goal.** Make results shareable and automatable: downloadable reports, a printable page, a comparison history, and a gate rule that matches the CLI.

**Scope.**

Reports:
- `#download-md` saves `evaldiff-report.md`.
- `#download-json` saves `evaldiff-report.json`, with keys `n`, `score_type`, `mean_a`, `mean_b`, `diff`, `ci` [lo, hi], `test`, `p_value`, `verdict`, `flips` {`improved`: [ids], `regressed`: [ids]}, `settings` {`alpha`, `seed`, `n_boot`, `threshold`}, `warnings`.
- `#open-report` opens `/report/<id>`, a read-only printable page with the same numbers and the flip tables.

History:
- The server appends every comparison to `./.evaldiff/history.jsonl`, relative to the directory the server was started from.
- `#history` lists the 20 most recent entries: time, file names, diff, verdict.
- Clicking an entry restores its results without re-uploading.

Gate:
- `#gate-rule` is either `worse` (fail if B is significantly worse) or `margin` (fail if the CI lower bound < −`#gate-margin`).
- `#gate-result` shows `PASS` or `FAIL`.
- `#gate-command` shows the equivalent CLI command, for example `python3 -m evaldiff compare f2_a.jsonl f2_b.jsonl --gate worse`, and `#gate-exit` shows its exit code (0 or 1).

CLI:
- `python3 -m evaldiff compare A B [--json] [--seed N] [--alpha X] [--gate worse|margin:X]` prints the same numbers as the UI.
- `--json` prints the same object as the JSON download.
- Exit code 1 when the gate fails, 2 on input errors.

**Acceptance criteria.**
1. On F2, clicking `#download-json` downloads `evaldiff-report.json`. Its `p_value` is within 1e-6 of 0.011719, `verdict` is `B is better (significant)`, `flips.regressed` is `["k16"]`, and `settings.seed` is `0`.
2. On F2, `#download-md` downloads `evaldiff-report.md`, which contains the lines `Verdict: B is better (significant)` and `p-value: 0.0117`, and a table listing k16 under regressions.
3. On F2, `#open-report` opens a page whose URL path starts with `/report/`. It shows diff `+0.2667`, p `0.0117`, the verdict, and both flip tables, with no file inputs.
4. After comparing F1 and then F2, `#history` lists both, newest first. Reloading the page keeps the list. Clicking the F1 entry restores `#p-value` = `0.1250` and `#verdict` = `No significant difference`.
5. After restarting the server process, `#history` still lists the previous entries, read from `.evaldiff/history.jsonl`.
6. On F2 with gate `worse`, `#gate-result` = `PASS` and `#gate-exit` = `0`. After swapping A and B, `#gate-result` = `FAIL` and `#gate-exit` = `1`.
7. On swapped F2 (where the CI upper bound is below 0) with gate `margin` and `#gate-margin` = `0.05`, `#gate-result` = `FAIL`. On un-swapped F2 with margin `0`, it shows `PASS`.
8. `#gate-command` text starts with `python3 -m evaldiff compare `, contains both file names, and contains `--gate worse` or `--gate margin:0.05` to match the selected rule.
9. The report page and the main page both render in the browser's print preview (`window.print` available) with no horizontal scroll at 1024 px width.
10. A `/report/<unknown-id>` URL shows `Report not found` with HTTP status 404.

---

## 5. Out of scope (possible later work)
- Native adapters for promptfoo, Inspect `.eval`, lm-eval `--log_samples` and Braintrust exports. Their formats should be verified against current docs before they are specified.
- Bayesian comparisons, equivalence (TOST) tests, and sequential testing for early stopping.
- Hosted or multi-user mode and authentication. evaldiff binds to 127.0.0.1 only.
