# Trustworthy Evidence-Scoring Methods for MSR Review

## Research question

Which robust, explainable methods should Skewvoir use to decide whether a contextual MSR needs human review when strict reference cohorts may be small, contaminated, non-normal, or time-dependent?

This note covers method choice only. It does not define final thresholds, implement a detector, or claim that a flagged MSR is defective.

## Executive conclusion

The first official detector should not be a single anomaly score. It should be a versioned set of explicit evidence rules:

1. Run deterministic execution/data-quality gates first.
2. For each predeclared scalar measurement, site, and tool-condition feature, compare the candidate with compatible peers using a leave-candidate-out median and median absolute deviation (MAD). Preserve the signed raw and percentage difference for explanation.
3. Keep percentage limits only when a domain owner has declared them as engineering review limits. Do not present them as statistically calibrated probabilities.
4. Detect sustained temporal change separately with one frozen-baseline EWMA per valid time stream. Do not enable every run rule by default.
5. Do not use a multivariate distance for the initial official verdict. Reconsider a small, predeclared multivariate model only after the office inventory and offline acceptance data establish adequate sample size, covariance stability, and a useful explanation design.

This method set is robust enough for a first release, maps cleanly to user-visible reasons, and preserves the agreed quality-gate-plus-worst-trustworthy-evidence roll-up.

## What the current implementation does

The current frontend evaluates the selected comparison set rather than an automatic official cohort:

- [`peer.ts`](../../../front-dev-home/app/utils/anomaly/peer.ts) computes, for each point, the mean and sample standard deviation of the other finite points.
- [`score.ts`](../../../front-dev-home/app/utils/anomaly/score.ts) applies either signed percentage deviation from that leave-one-out mean or signed distance in leave-one-out standard deviations.
- [`types.ts`](../../../front-dev-home/app/utils/anomaly/types.ts) uses fixed defaults of 10%/20%, 2/3 sigma, and effective minimum counts of 3 for percentage scoring and 5 for sigma scoring.
- [`useSkewvoirAnalysis.ts`](../../../front-dev-home/app/composables/useSkewvoirAnalysis.ts) evaluates parameter mean and spread independently, then keeps the worst evaluated severity.

Leaving the candidate out is a useful protection against the candidate inflating its own reference center or scale. It does not protect against two or more contaminated peers influencing one another. NIST calls this failure **masking**, and notes the related risk of **swamping** legitimate points when the assumed number of outliers is wrong ([NIST, Detection of Outliers](https://www.itl.nist.gov/div898/handbook/eda/section3/eda35h.htm)).

## Comparison of candidate methods

| Method | Useful property | Main assumptions and failure modes | Initial role |
| --- | --- | --- | --- |
| Leave-one-out mean + percentage | Very easy to explain; preserves direction and engineering magnitude | Mean is non-robust; denominator fails near zero; 10%/20% has no statistical meaning unless domain-defined; comparable percentages can still have different operational meaning | Keep only as an explicitly configured engineering-limit rule and explanation value |
| Leave-one-out mean + standard deviation | Familiar scale unit; excludes the candidate from its own baseline | Mean and standard deviation are distorted by contaminated peers and heavy tails; fixed 2/3 sigma bands are miscalibrated when parameters are estimated from small samples; assumes a roughly stable, symmetric distribution for probability language | Do not use as the default official peer detector |
| Median + MAD modified score | Resistant to a minority of extreme peers; univariate and value-bearing; simple reason text | MAD can be zero with quantized/tied data; a majority/common-mode shift becomes the new center; skew or multimodality still needs treatment; a threshold is not universal | Default initial peer evidence method |
| Shewhart point/run rules | Rules identify an isolated excursion, side-of-center run, or trend in an ordered stream | Requires a meaningful time order, stable baseline, and calibrated false-alarm policy; multiple run rules substantially increase false alarms | Use one isolated-point rule only if calibrated; add selected run rules only from acceptance evidence |
| EWMA | Accumulates weak, sustained shifts while remaining explainable as a weighted history | Requires a representative frozen baseline; standard tables assume independent normal observations; mixes regimes if the stream key is wrong | Default initial temporal-drift evidence method |
| CUSUM | Strong for a specified directional shift and can identify the onset region | Requires a target shift, decision interval, and stable baseline; adds configuration and explanation burden | Later alternative when a specific shift size matters more than EWMA simplicity |
| Hotelling T-squared / Mahalanobis distance | Accounts for correlation between a small feature set | Classical form assumes independent multivariate-normal observations and invertible, stable covariance; aggregate distance obscures the responsible features; classical covariance is contamination-sensitive | Defer from the initial official verdict |
| Robust or shrunk multivariate covariance | MCD resists casewise contamination; shrinkage improves conditioning | MCD still expects an approximately unimodal/symmetric distribution and needs many observations per feature; shrinkage fixes conditioning, not contamination; neither creates a self-explaining reason | Later, constrained research only |

## Current percentage and sigma rules

### Percentage deviation

Percentage difference is best treated as an engineering signal:

\[
d_{pct}=100\frac{x-c}{|c|}
\]

It answers a useful user question: “How much higher or lower is this MSR than its compatible peers?” However:

- It is undefined or unstable when the reference center is zero or near zero.
- A universal percentage does not represent equal risk across CD-SEM/HV-SEM parameters, FDC values, spatial features, or failed-image ratios.
- Its threshold has no false-alarm interpretation unless a distribution and sampling plan are added.

NIST explicitly distinguishes statistical tolerance intervals, which have population coverage and confidence, from engineering tolerances prescribed by domain owners ([NIST, Tolerance Intervals for a Normal Distribution](https://www.itl.nist.gov/div898/handbook/prc/section2/prc263.htm)). Therefore the UI and persisted evidence should say “engineering review limit” rather than “statistical confidence” when a percentage limit fires.

### Standard-deviation distance

The fixed 2/3 sigma rule should not be treated as a formal outlier test. NIST warns that ordinary Z-scores can be misleading for small samples and shows that formal Grubbs critical values depend on sample size and a normal model ([NIST, Detection of Outliers](https://www.itl.nist.gov/div898/handbook/eda/section3/eda35h.htm); [NIST, Grubbs' Test](https://www.itl.nist.gov/div898/handbook/eda/section3/eda35h1.htm)). Grubbs' test also targets a single outlier; it is not a solution to an unknown number of contaminated peers.

The current leave-one-out calculation is better than letting the candidate inflate its own standard deviation, but a fixed `3` is still not a sample-size-adjusted critical value. At the current minimum of five finite points, the four-point reference scale is especially unstable. It also becomes over-wide under heavy tails: NIST demonstrates that extreme tails can severely distort the standard deviation while leaving MAD comparatively stable ([NIST, Measures of Scale](https://www.itl.nist.gov/div898/handbook/eda/section3/eda356.htm)).

## Recommended peer method: median and MAD

For candidate value \(x\) and eligible reference values \(R\) that exclude the candidate:

\[
c=\operatorname{median}(R)
\]

\[
MAD=\operatorname{median}_{r\in R}|r-c|
\]

\[
M=0.6745\frac{x-c}{MAD}
\]

NIST documents this modified score and reports the common `|M| > 3.5` rule as a label for a **potential** outlier, not a defect declaration ([NIST, Detection of Outliers](https://www.itl.nist.gov/div898/handbook/eda/section3/eda35h.htm)). Rousseeuw and Croux report that normal-consistent MAD has a bounded influence function and 50% breakdown point, while also documenting its relatively low Gaussian efficiency and proposing the more efficient robust `Qn` and `Sn` alternatives ([Rousseeuw and Croux, 1993](https://doi.org/10.1080/01621459.1993.10476408)).

For Skewvoir:

- Use median/MAD first because users can reconstruct the reason from displayed values.
- Retain raw signed delta and signed percentage delta alongside `M`; the statistical score must not hide the operational magnitude.
- Treat 3.5 only as a starting candidate for offline calibration. `Watch` and `Needs review` thresholds must be versioned and validated per feature or feature class.
- Do not silently substitute a tiny epsilon when `MAD = 0`. Quantized parameters and repeated default values can legitimately produce zero MAD. Apply a domain resolution/engineering limit if one exists; otherwise return `Not evaluated` for that statistical signal.
- Keep `Qn` as a later offline comparison, especially for frequent zero-MAD or low-efficiency cases. Adding it initially would increase implementation and explanation complexity before office data shows a need.

### What robustness does not solve

A 50% breakdown point protects the center and scale only while contamination remains below the estimator's tolerance. If most compatible peers move together, median/MAD will describe the shifted regime as typical. That is why frozen-baseline temporal evidence is a separate detector rather than another peer score.

Median/MAD is also not automatically probability-calibrated for skewed, multimodal, or mixed-regime cohorts. Positive skewed measures may use a declared log transform, followed by the same transparent calculation; NIST recommends transformation when an approximately lognormal model is appropriate ([NIST, Detection of Outliers](https://www.itl.nist.gov/div898/handbook/eda/section3/eda35h.htm)). A transform must be part of the versioned detector configuration and shown in the explanation.

Do not rely on empirical outer quantiles as a small-cohort escape hatch. Distribution-free tail coverage is data-hungry: NIST's min/max tolerance example needs 46 observations to cover 90% of an unknown distribution with 95% confidence, and 473 for 99% coverage at the same confidence ([NIST, Distribution-Free Tolerance Intervals](https://www.itl.nist.gov/div898/handbook/prc/section2/prc264.htm)).

## Temporal drift and run evidence

Peer unusualness and process change answer different questions:

- Peer evidence: “Is this MSR different from compatible MSRs?”
- Temporal evidence: “Has this compatible stream moved away from its previously accepted baseline?”

The temporal stream key must be explicit. For tool-condition drift it will normally include individual equipment identity in addition to the strict compatibility signature; pooling equipment can hide a tool-specific shift. For a fleet/process stream, a separate named stream and baseline are required.

### Shewhart and run rules

NIST lists common Western Electric rules: one point beyond 3 sigma, two of three beyond 2 sigma on one side, four of five beyond 1 sigma, eight on one side, six trending, and fourteen alternating ([NIST, Variables Control Charts](https://www.itl.nist.gov/div898/handbook/pmc/section3/pmc32.htm)). These rules are not free sensitivity. In NIST's normal/known-parameter example, adding the WECO rules changes average false-alarm run length from about 371 points to about 91.75 points.

Initial policy:

- Do not enable all run rules.
- If the robust peer extreme rule already covers isolated points, do not duplicate it with an unexplained classical 3-sigma flag.
- Consider one sustained-side or monotonic-trend rule only if the offline acceptance set demonstrates useful lead time at an acceptable alerts-per-day cost.
- Record the exact rule and the observations that satisfied it; “trend detected” alone is insufficient.

### EWMA

EWMA recursively combines the current value and prior EWMA, giving recent observations the greatest weight. Roberts introduced geometric moving-average control tests in the original paper ([Roberts, 1959](https://doi.org/10.1080/00401706.1959.10489860)). NIST notes that EWMA is suited to small shifts, commonly uses `lambda` between 0.2 and 0.3, and requires a historical database representative of an in-control process ([NIST, EWMA Control Charts](https://www.itl.nist.gov/div898/handbook/pmc/section3/pmc324.htm)).

Use one EWMA over a predeclared raw feature or robustly standardized residual. Freeze and version the accepted baseline; do not continuously absorb flagged or unreviewed MSRs into it. The explanation should show `lambda`, current EWMA, center, limit, direction, baseline period, and first crossing time.

Standard EWMA limit tables assume independent normal observations. NIST identifies randomness as a key control assumption and recommends time-series modeling when autocorrelation invalidates it ([NIST, Autocorrelation](https://www.itl.nist.gov/div898/handbook/eda/section3/eda35c.htm)). Therefore serial dependence, irregular sampling, maintenance boundaries, and recipe revisions must be checked in the office data before interpreting nominal false-alarm rates.

### CUSUM

CUSUM accumulates deviations from a target and is well suited to a specified sustained shift. Page's original continuous-inspection scheme is the foundational method ([Page, 1954](https://doi.org/10.1093/biomet/41.1-2.100)). NIST's design requires a false-alarm risk, missed-detection risk, and target shift size, and the chart can help locate the shift onset ([NIST, CUSUM Control Charts](https://www.itl.nist.gov/div898/handbook/pmc/section3/pmc323.htm)).

Defer CUSUM from the initial method set unless engineers can name the minimum shift worth detecting. EWMA requires fewer user-facing configuration concepts and is adequate for the first temporal signal.

## Constrained multivariate methods

Hotelling's T-squared accounts for feature covariance through an inverse covariance matrix. NIST states the classical model as independent observations from a multivariate normal distribution with `p < n - 1` ([NIST, Hotelling Control Charts](https://www.itl.nist.gov/div898/handbook/pmc/section3/pmc341.htm)). That algebraic minimum is not evidence that the covariance estimate is operationally stable.

Two improvements address different problems:

- Minimum Covariance Determinant (MCD) robustly estimates multivariate location and scatter from a subset and resists casewise contamination ([Rousseeuw and Van Driessen, 1999](https://doi.org/10.1080/00401706.1999.10485670)).
- Ledoit-Wolf shrinkage produces a well-conditioned covariance estimator when the ordinary sample covariance is unstable or non-invertible in high dimensions ([Ledoit and Wolf, 2004](https://doi.org/10.1016/S0047-259X(03)00096-4)).

Shrinkage does not make contaminated data robust, and MCD does not solve multimodality or feature explanation. A high aggregate distance can also be caused by correlated moderate shifts that cannot honestly be presented as additive per-feature blame.

If multivariate evidence is revisited later, constrain it as follows:

- Use a predeclared feature vector within one evidence family; never mix execution/data-quality gates into a latent health score.
- Keep `p` small and semantically stable. Do not feed every site, raw FDC time point, or missingness-derived feature into one model.
- Require `p < n - 1` as a hard floor and begin validation only with substantially more observations than dimensions; scikit-learn's official MCD example reports low estimation error when `n > 5p`, so use that only as a research gate, not a deployment guarantee ([scikit-learn, Robust vs Empirical Covariance](https://scikit-learn.org/stable/auto_examples/covariance/plot_robust_vs_empirical_covariance.html)).
- Compare classical, MCD, and shrinkage behavior under realistic contamination and time splits.
- Show the multivariate distance and the signed univariate robust deviations of every included feature. Do not call those deviations an exact additive decomposition of the correlated distance.

Until those conditions are demonstrated, the official verdict should remain a worst-of set of interpretable univariate and temporal evidence.

## Minimum-data and readiness policy

There is no universally correct minimum sample count. NIST states that sample size depends on false-positive risk, false-negative risk, variance, and the shift that must be detected ([NIST, Sample Sizes Required](https://www.itl.nist.gov/div898/handbook/prc/section2/prc222.htm)). It also warns that control-chart false-alarm properties can differ substantially when limits are estimated from little data, and quotes the classical starting point of at least 25 in-control subgroups for establishing statistical control ([NIST, Variables Control Charts](https://www.itl.nist.gov/div898/handbook/pmc/section3/pmc32.htm)).

Use the following as conservative **product starting gates**, not scientific constants:

| Evidence | Initial readiness gate | If the gate fails |
| --- | --- | --- |
| Deterministic execution/data quality | Required fields and denominator are present; rule has a domain-defined meaning | `Not evaluated` for the affected rule; explicit missing/invalid reason |
| Median/MAD peer feature | At least 20 finite eligible peers after exclusions, nonzero MAD, compatible units/layout, no unresolved cohort-mixture warning | `Not evaluated`; an optional domain engineering limit may still run independently |
| Domain percentage limit | Valid non-near-zero reference and a versioned feature-specific limit approved by a domain owner | `Not evaluated`; never borrow a global percentage |
| Temporal EWMA | At least 25 accepted, time-ordered baseline observations in the exact stream, with maintenance/regime boundaries and dependence checked | `Not evaluated` for temporal drift |
| Empirical distribution-free tail | Sample size calculated for the desired coverage/confidence; do not use 20 as a generic tail-calibration count | `Not evaluated` |
| Multivariate distance | Deferred initially; later require `p < n - 1`, begin research only at `n > 5p`, and pass covariance/contamination validation | No multivariate official evidence |

The peer count of 20 is deliberately a product policy to test, not a source-derived universal cutoff. The offline acceptance study must report performance and cohort coverage at alternative counts such as 10, 15, 20, 30, and 50. If 20 leaves too many strict cohorts unevaluated, the system must surface that limitation rather than silently relax compatibility.

## Masking, contamination, and regime controls

Every detector should assume that the candidate may not be the only unusual MSR:

- Exclude the candidate from the reference calculation.
- Use robust peer center/scale so a minority of contaminated peers cannot dominate.
- Report eligible count, excluded count, and exclusion reasons.
- Do not delete flagged peers automatically. Retain the evidence snapshot so users can inspect clusters and common causes.
- Freeze official temporal baselines and update them only through a versioned re-evaluation operation.
- Segment known maintenance, recipe, model, software, calibration, and layout changes. A strict compatibility signature is necessary but may not capture every regime boundary.
- Treat a cluster of similar flags as possible common-mode evidence, not as proof that the cluster is bad.

## Explanation contract

NIST distinguishes explainability of how a system operates from interpretability of what its output means in the user's context, and recommends documentation that supports monitoring, audit, and governance ([NIST AI RMF 1.0, section 3.5](https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.100-1.pdf)). Each Skewvoir evidence reason should therefore persist and display enough values for an engineer to reconstruct the flag:

- Review Candidate MSR and evidence family.
- Metric, parameter/site/FDC feature, units, and direction.
- Detector name, version, transform, and exact crossed rule.
- Candidate raw value.
- Reference center and scale, or temporal statistic and control limit.
- Signed raw delta, signed percentage delta when valid, and robust/statistical score when used.
- `Watch` or `Needs review` threshold and why that threshold applies to this feature.
- Full compatibility signature, cohort/baseline time window, eligible count, and excluded count/reasons.
- Data-quality prerequisites and any suppressed conclusions.
- Evaluation time, baseline version, and known limitation such as small cohort, zero MAD, skew, or autocorrelation.
- For later multivariate evidence, every included feature and its signed univariate deviation; no opaque aggregate “health” score.

Reasons should use the agreed vocabulary: `Not evaluated`, `No review flag`, `Watch`, and `Needs review`. They should say “potential review evidence,” not “defect,” “bad data,” or “abnormal equipment.”

## Initial recommended method set

### 1. Execution/data-quality family

Use deterministic, domain-meaningful rules for missing values, alignment failure, failed-image ratio, invalid denominators, parse/schema failure, and measurement-score validity. These rules run first. When they make measurement outcomes untrustworthy, persist the quality reason and suppress unsupported measurement conclusions.

### 2. Measurement-outcome and tool-condition peer evidence

For each predeclared feature:

1. Build the automatic strict Reference Cohort.
2. Exclude the candidate and invalid/missing values.
3. Require the initial peer readiness gate.
4. Compute median, MAD, signed raw delta, signed percentage when valid, and modified score.
5. Evaluate a versioned feature-specific threshold.
6. Evaluate a separate engineering percentage limit only when one is explicitly configured.
7. Persist all inputs needed by the explanation contract.

Parameter mean, parameter spread, site/spatial summaries, fixed FDC values, sequence-derived FDC features, and tool-condition features remain separate evidence. Do not average them.

### 3. Temporal evidence

Add one EWMA only for features and stream keys shown by office inventory to have a stable, meaningful sequence. Initialize it from at least 25 accepted historical observations, freeze/version the baseline, and calibrate `lambda` and limits against the historical acceptance set. A run rule or CUSUM is added only if it provides measured incremental value.

### 4. Priority roll-up

- `Not evaluated`: the relevant detector could not run; this is never equivalent to `No review flag`.
- `No review flag`: every required quality prerequisite passed and no trustworthy evidence crossed a configured threshold.
- `Watch`: an explicit soft engineering limit or calibrated early temporal signal crossed.
- `Needs review`: a high-severity deterministic quality issue or strong calibrated peer/temporal evidence crossed.

The highest trustworthy evidence determines MSR priority after quality gating. Store every family status and reason; do not synthesize a hidden numeric health score.

## Offline acceptance requirements for method selection

Thresholds and minimum counts should be selected with time-separated, engineer-reviewed historical MSRs, not chosen from a generic rule alone. The acceptance report should include:

- Reference-cohort coverage and `Not evaluated` rate by fab, tool model, recipe, parameter, and layout.
- Precision of `Needs review`, precision of `Watch`, known-concern recall, and alerts per day/user.
- Lead time for EWMA versus point-only evidence.
- Performance at peer-count gates of 10, 15, 20, 30, and 50.
- Sensitivity to one, two, and clustered contaminating peers; skew; heavy tails; tied/zero-MAD values; missingness; and common-mode shifts.
- Stability across time splits, individual equipment, lots, and maintenance boundaries.
- Incremental value of each evidence rule and the combined worst-of roll-up.
- A reason-level audit showing that engineers can identify the exact value, cohort, threshold, and rule responsible for every flag.

Promote only a versioned configuration that meets the agreed cohort-coverage, false-alert, missed-concern, and alerts-per-day criteria. Human Review Outcomes may inform later offline tuning, but they must not trigger automatic online retraining.

## Decision for the Wayfinder map

Adopt median/MAD peer scoring plus explicit domain limits and a separate frozen-baseline EWMA as the initial method set. Retire the current fixed leave-one-out mean/sigma rule from official assessment, while preserving signed percentage difference as an explanation and optional domain rule. Defer multivariate official scoring until data volume, covariance stability, and reason-level explainability are demonstrated by office inventory and offline acceptance.
