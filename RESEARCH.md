# evaldiff: research notes

## Gap verdict (read this first)

**The gap is weaker than the original claim.** The *mainstream* eval platforms do not report paired significance in their compare views. Promptfoo's web UI diff, Braintrust's experiment comparison, OpenAI Evals' metrics, and lm-eval-harness all show deltas, or per-run standard errors at most, and none of them tests whether A and B really differ. But at least five open-source Python libraries released in 2025-2026 already do paired tests with CIs: evalci, errorbars, evalsig, inspect-mlflow and evalstats. Several of them also do power analysis and clustered SEs.

So evaldiff cannot claim "nobody does paired significance." What remains open, and what this product targets:

1. A **zero-install local web UI**. The existing tools are libraries or CLIs.
2. **Flip-level inspection** joined to the statistics: which examples moved and in which direction.
3. A **variance decomposition into generation noise and LLM-judge noise** when there are repeated trials or judge re-runs, plus an **A/A noise-floor** check. I found no tool that does this decomposition.
4. A **power and sample-size planner** placed next to the verdict.

Caveat: the PyPI pages for errorbars and evalsig would not render for me. Their feature lists come from search-result summaries, not from my own reading.

## 1. Existing tools: what they report

| Tool | Paired significance between two runs? | Evidence |
|---|---|---|
| promptfoo | **No.** Its web UI "Compare" is a visual diff, and its scatter plot colors each test by which prompt won. No p-values or CIs. | https://www.promptfoo.dev/docs/usage/web-ui/ |
| Braintrust | **No (per official docs).** It gives per-row score deltas, improvement and regression counts, and `summarize()` diffs. Some third-party blogs claim it runs t-tests, but the official docs do not support that. | https://docs.braintrust.dev/evaluate/compare-experiments.md |
| OpenAI Evals | **No.** `get_bootstrap_accuracy_std` gives one run's accuracy std, computed by subsampling half the events. There is no comparison between runs. | https://github.com/openai/evals/blob/main/evals/metrics.py |
| lm-eval-harness | **No.** It gives per-task bootstrap stderr (`bootstrap_iters`, default 100000). Its authors say these CIs answer a different question from "do two models differ." | https://lm-evaluation-harness.readthedocs.io/api/entry_points/ , https://arxiv.org/abs/2405.14782 |
| HELM | **Partial.** It ran paired bootstrap tests for its *human* evaluations. Its leaderboard reports means. | https://arxiv.org/abs/2211.09110 |
| Inspect AI | **Per-run only.** It computes correct stderr with `epochs`. Anthropic's post says the authors knew of no open-source framework that does paired differences. Paired comparison exists only in the third-party `inspect-mlflow` `compare_evals`. | https://www.anthropic.com/research/statistical-approach-to-model-evals , https://inspect-mlflow.readthedocs.io/en/latest/comparison.html |
| evalci (Jul 2026) | **Yes.** Paired permutation, bootstrap CI, power, clustered SE, multiple-comparison correction. It is a library built on numpy, scipy and pandas, with no UI. | https://arxiv.org/abs/2607.04429 |
| errorbars, evalsig, evalstats, agent-regress-cli | **Yes (per listings).** Paired mean difference with CI and p, McNemar, and imports of Inspect and lm-eval logs. These are CLIs or libraries. | https://pypi.org/project/errorbars/ , https://pypi.org/project/evalsig/ , https://pypi.org/project/evalstats/0.2.2/ , https://pypi.org/project/agent-regress-cli/0.1.7/ |

## 2. Paired statistics for small eval sets

- **Pairing matters.** Scoring both runs on the same examples cancels out how hard each question is. The paired SE is `sqrt(Var(d)/n)` with `d = s_B - s_A` per example, which equals `sqrt(SE_A² + SE_B² − 2·SE_A·SE_B·Corr)`. Frontier models' per-question correlations of 0.3 to 0.7 make the paired SE much smaller than the unpaired one. (Miller 2024, https://arxiv.org/abs/2411.00640, Eq. 7)
- **Binary outcomes: McNemar on the discordant pairs.** Only the flips carry information: b = A pass/B fail, c = A fail/B pass. The exact conditional test is binomial(b+c, 0.5). Fagerland, Lydersen and Laake (2013) found the exact conditional test overly conservative and the continuity-corrected asymptotic test poor. The **mid-p** test (the exact p minus the point probability) performed well and came close to the far more complex exact unconditional test. The usual rule of thumb is to use the exact or mid-p test when b+c < 25. (https://doi.org/10.1186/1471-2288-13-91)
- **Sign-flip permutation test.** Randomly flipping the sign of each paired difference is the exact randomization test for paired data and works for any score type. On {−1, 0, +1} differences it reproduces the two-sided exact McNemar p, which gives the evaluator a useful cross-check. Permutation and paired-bootstrap tests are the standard recommendation for NLP system comparison. (Dror et al. 2018, https://aclanthology.org/P18-1128/ ; Berg-Kirkpatrick et al. 2012, https://aclanthology.org/D12-1091/)
- **Wilcoxon signed-rank: zeros and ties.** scipy's `zero_method` can be `wilcox` (drop zeros, the default), `pratt` (rank the zeros, then drop their ranks) or `zsplit`. Before scipy 1.15, `auto` used the exact distribution only with no ties (n ≤ 25 in old docs, ≤ 50 later), and otherwise a normal approximation. Since 1.15, small samples with zeros or ties use an exact permutation distribution. When every difference is zero, the p-value is NaN. (https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.wilcoxon.html , https://github.com/scipy/scipy/pull/21867)
  The evaluator should cross-check Wilcoxon fixtures with scipy ≥ 1.15.
- **Percentile bootstrap at small n.** The bootstrap needs no distributional assumption, but at very small n its CI is too narrow. It cannot be wider than the data's range: with n = 4 differences that are all positive, the CI excludes 0 while the exact permutation p is 0.125. This is a standard resampling result that I did not source separately here. Miller adds that the bootstrap is unnecessary unless the sampling scheme or estimator is complicated. evaldiff therefore uses an exact or permutation test for the verdict, uses the bootstrap only for the CI, and warns when n < 10.

## 3. Clustered and repeated measurements (Miller 2024)

Source: Evan Miller, "Adding Error Bars to Evals", https://arxiv.org/abs/2411.00640 ; summary post https://www.anthropic.com/research/statistical-approach-to-model-evals

- **Clustered SE (Eq. 4 and 8).** When questions share a passage or other unit, use `SE_clustered = (1/n)·sqrt(Σ_c (Σ_{i∈c}(d_ic − d̄))²)`. On real evals it came out more than 3× the naive SE. With singleton clusters the formula reduces to the plug-in CLT SE `sqrt(Σ(d−d̄)²)/n`.
- **Repeated trials.** Resample K answers per question, average them per question, then apply the CLT to the per-question means. Pooling all K·n rows as if they were independent is wrong.
- **Law of total variance.** `Var(μ̂) = (Var(x) + E[σ_i²]/K)/n`, where `Var(x)` is the variance of the true per-question scores and `E[σ_i²]` is the within-question (sampling) variance. Choose K so that `E[σ_i²]/K ≪ Var(x)`.
- **Power (Eq. 9 and 10).** `n = (z_{α/2}+z_β)²·(ω² + σ_A²/K_A + σ_B²/K_B)/δ²`, where `ω² = Var(x_A)+Var(x_B)−2Cov(x_A,x_B)`. Inverted for the minimum detectable effect: `δ = (z_{α/2}+z_β)·sqrt((ω² + σ_A²/K_A + σ_B²/K_B)/n)`.
- Wang (2025/2026), "Measuring all the noises of LLM evals", decomposes noise into prediction and data components. He finds that paired prediction noise typically *exceeds* paired data noise, so averaging repeated predictions raises power substantially. (https://arxiv.org/abs/2512.21326)

## 4. How much do LLM judges vary run to run?

- Judges at temperature 0 are not deterministic. Inference batching changes the kernels, and votes changed for 1.6–5.7% of items across judges, enough to flip some preferences. The authors recommend averaging repeated runs. (https://arxiv.org/abs/2503.09347)
- Scores varied substantially across GPT-4o, Gemini-2.5-Flash and Claude judges at temperature 0, with completeness criteria the least stable. (https://arxiv.org/abs/2603.04417)
- The variation depends on the task. For structured-question marking, temperature was *not* a meaningful variance source. (https://arxiv.org/abs/2603.14732)
- **Consequence for evaldiff.** Judge noise has to be measured per dataset; there is no single constant to assume. With a nested design (generation trial k, judge re-run j), the variance of the per-example mean splits into three parts: between-example signal ω², generation noise σ_G²/K, and judge noise σ_J²/(K·J). σ_J² is estimated from the spread across judge re-runs of the same output, and σ_G² from the spread across trial means minus σ_J²/J. This is the same law-of-total-variance argument as Miller's, applied one level deeper. Without repeated rows, an **A/A pair** (the baseline config run twice) estimates the total run-to-run noise: `Var(d_AA) ≈ 2σ²`, so `Var(d_AA)/Var(d_AB)` approximates the share of the A/B variance that comes from noise.

## 5. Sample size and minimum detectable effect

- **Paired binary (Connor 1987, Biometrics 43:207–211).** `n = [z_{α/2}·sqrt(p_d) + z_β·sqrt(p_d − δ²)]² / δ²`, where p_d is the discordant proportion and δ = p_c − p_b. SAS PROC POWER implements it as `METHOD=CONNOR`. (https://support.sas.com/documentation/cdl/en/statug/67523/HTML/default/statug_power_syntax49.htm , https://metricgate.com/docs/sample-size-mcnemar-paired)
- **Paired continuous.** Miller Eq. 9 and 10 with ω² estimated by the sample variance of d (or by ω² + noise/K when trials exist).
- Post-hoc "observed power" is deliberately left out. It is a monotone function of the p-value and adds no information. This is a standard argument that I did not source separately here.

## 6. Chosen methods (one-line reason each)

| Use | Method | Reason |
|---|---|---|
| Binary verdict | Exact McNemar **mid-p** (exact conditional p also shown) | Fagerland 2013: best simple small-sample performer. The exact test is too conservative. |
| Continuous verdict | Paired **sign-flip permutation** test on the mean difference. Exact enumeration when ≤ 16 nonzero differences, otherwise 10,000 seeded Monte Carlo draws with p = (1+hits)/(1+R). | Exact at small n, no distributional assumption, and it tests the same statistic the CI describes. |
| CI on the mean difference | Paired percentile bootstrap, B = 10,000, seed 0 | The CI the user asked for. Deterministic with a seed. A small-n warning makes up for its undercoverage. |
| Secondary tests | Wilcoxon signed-rank (`wilcox` or `pratt` zeros, average-rank ties, exact via DP for ≤ 50 nonzero, otherwise normal approximation with tie correction), and a z-test using `sd(d)/√n` | For cross-checking against scipy, and familiar to users. |
| Repeated trials | Average per example, then apply the paired methods. Decompose with the law of total variance. | Miller 2024. Pooled rows are not independent. |
| Clusters | Miller Eq. 8 clustered SE, a cluster-level sign-flip test, and a cluster bootstrap | Correlated questions inflate the real uncertainty. |
| Many comparisons (slices, metrics, candidates) | Holm step-down adjustment | Controls family-wise error and is uniformly more powerful than Bonferroni. |
| Power | Connor (binary) and Miller Eq. 9 and 10 (continuous or with trials). `z` from `statistics.NormalDist`. | Closed form and standard library only. |
| Run-to-run noise without trials | A/A pair: `Var(d_AA)/Var(d_AB)` | The only way to measure noise from single-trial files. |
