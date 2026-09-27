# FDC and SCE — characterize the real data before we redesign the views

This brief is for an LLM running **at the office**, next to the real data.
Its sibling, `hardware_field_usage.md`, asks whether each field *exists* in the
shape the code reads. This one asks what the data *behaves* like: cadence,
ranges, noise, what the unexplained tokens mean, and which differences between
tools are real signal. Home cannot see any of this. The FDC and SCE panels were
built on a mock, so several of their display choices are guesses.

Run `hardware_field_usage.md` first. If the schema is wrong, these statistics
are meaningless.

Written 2026-09-28 from `frontend/app/components/ebeam/hardware/FdcPanel.vue`,
`ScePanel.vue`, `frontend/app/utils/fdcValues.ts`, `sceHistory.ts`,
`sceCompare.ts` and the two `hardware_*.txt` source notes.

## Rules for the run

- **Every question below exists to settle a display decision.** The "Decides"
  column names it. Answer with numbers, then say which option the numbers
  support. A generic "consider a heatmap" is not useful. "Cross-tool spread is
  8× the within-tool noise, so a fleet ranking is meaningful" is.
- **Report statistics, not rows.** Where a sample is requested, keep it to the
  size asked for.
- **Read-only.** Do not change code, indices, Redis or MinIO.
- **Mark provenance on every finding:** `office 확인 YYYY-MM-DD` for a number
  you computed today, `OFFICE-VERIFY` for an interpretation you could not
  confirm (for example what a token *means*).
- **Say what you could not answer and why.** A gap is useful; a guess dressed
  as a finding is not.

## Sample to use

- **Window:** 90 days ending today. The page shows 30, but PM steps and
  re-tunes need a longer baseline to show up.
- **Tools:** at least 3 M-fabs, at least 10 CD-SEM tools in total, covering
  every `eqp_model_cd` present. Include at least one tool with a BM/PM event in
  the window (`fab_inform_notes`).
- **How to pull:** reuse the adapters so you see what the page sees.

  ```python
  from backend.ebeam.hardware.providers.fdc.office import build_fdc_docs
  from backend.ebeam.hardware.providers.sce.office import build_sce_settings, build_sce_history
  ```

  A 90-day FDC pull can exceed the adapter's 10,000-doc cap. If it raises,
  split the window into 30-day slices, and report that it raised (see F0).
- For the fab-wide questions (F0, X1), query `network_fdc_cdsem` directly with
  aggregations (`terms` on `eqp_id.keyword` / `fdc_key.keyword`,
  `date_histogram` on `timestamp`). Use the `.keyword` subfields; bare fields
  raise a fielddata error.

## What the page does today

| Tab | View | Guess it rests on |
| --- | --- | --- |
| FDC · TemperatureEChuck | one line per position 1/2/3, tight y-range | positions are comparable on one axis; ~0.5 °C drift is the signal |
| FDC · SPMVoltages | pick one cycle, overlay the A/B/C profiles, show the judgment token as a badge | a gap of more than 30 min separates cycles; the judgment is a verdict |
| FDC · LaserPower | three lenses (raw by scale / % vs first sample / x-vs-y scatter) | meaning unknown, so all three are offered |
| FDC · ContactpinConductionInfo | a flat table, green only for the exact string `Conduction` | a two-value vocabulary |
| SCE · 비교 | settings table vs picked siblings, plus the 360-point curves (line or polar) | the siblings a user happens to pick are the right comparison |
| SCE · 시계열 | trend of one numeric setting; trend of one coefficient index; curves collapsed into revisions by exact equality | re-tunes are rare and collections repeat the curve bit-for-bit |

Every FDC view is **single-tool**. There is no view across the fleet.

## FDC — `network_fdc_cdsem`

### F0. Volume and coverage (do this first)

| # | Question | How | Decides |
| --- | --- | --- | --- |
| F0.1 | Distinct `fdc_key` values in the whole index, with counts | `terms fdc_key.keyword` | the adapter **raises** on any key outside the 4 known ones; a 5th key means a parser to write |
| F0.2 | Docs per tool per 30 days, per key: median, p95 and max | `terms eqp_id` × `terms fdc_key` × 30-day `date_histogram` | whether the 10,000 cap holds; whether shipping raw docs to the browser is acceptable, or the backend must pre-aggregate |
| F0.3 | Coverage matrix: `eqp_model_cd` × `fdc_key` (the share of tools that emit each key) | aggregation | whether sub-tabs must hide per model; whether an empty sub-tab is normal |
| F0.4 | Is `values[1]` always `'0'`? If not, list its distinct values and which tools have them | scan | if it varies, it may be a module or column index, and every series must split on it |
| F0.5 | Exact duplicates: same `eqp_id`, `fdc_key`, `timestamp` and `values` | group-by | whether the parser must dedupe (duplicates double-draw points and inflate counts) |
| F0.6 | Average `_source` size in bytes per key, especially SPMVoltages | `_source` length | the payload size for the 30-day page, together with F0.2 |

### F1. TemperatureEChuck

| # | Question | How | Decides |
| --- | --- | --- | --- |
| F1.1 | Sampling interval per tool: median gap, p90 gap, and gaps over 24 h | diff of sorted timestamps per position | point markers vs a line; whether gaps should break the line |
| F1.2 | Are positions 1/2/3 logged at the same timestamp or offset by minutes? | per-cycle timestamp spread | whether the three can be aligned into one row per cycle (needed for deltas) |
| F1.3 | Per tool: mean and std per position; the **offset** between positions (mean of pos2−pos1, pos3−pos1) and whether that offset is stable over time | pivot per cycle | plot absolute °C, or plot the position deltas (a stable offset hides the drift inside the band) |
| F1.4 | Noise vs drift: within-day std vs the range of daily means over 90 days | resample daily | whether a daily-mean trend is enough, or raw points are needed |
| F1.5 | Periodicity: autocorrelation at 24 h and 7 days | ACF on an hourly resample | whether a fab HVAC cycle dominates (then a daily aggregate hides nothing) |
| F1.6 | Steps at BM/PM: mean over 3 days before vs after each event | join `fab_inform_notes` | whether the BM/PM markers earn their place on this chart |
| F1.7 | Fleet spread: the distribution of per-tool means across a fab vs the within-tool std | variance decomposition | **whether a fab-wide ranking or heatmap view is meaningful** |
| F1.8 | Is there a known alarm or interlock limit for chuck temperature? Search the recipe/parameter docs and FDC alarm definitions | lookup | whether to draw a spec band; without one, the y-range is cosmetic |

### F2. SPMVoltages

| # | Question | How | Decides |
| --- | --- | --- | --- |
| F2.1 | Tokens `values[3..5]` (the `'7','1','1'` between the channel and the judgment): the distinct tuples with frequencies, by channel and by judgment. Do they change over time for one tool? | value counts; per-tool timeline | whether they are a series key (split on them), a quality flag (show them), or constant (ignore them). State the most likely meaning as `OFFICE-VERIFY` |
| F2.2 | The judgment vocabulary (`spline`, `quartic`, …), with frequency per tool and channel | value counts | **whether it is a verdict or the name of the fitted model.** If it is the fit model, the badge must not read as pass/fail |
| F2.3 | Profile length: always 100? Does it differ by channel or by F2.1 tuple? | length histogram | whether index positions line up across cycles (a heatmap needs equal length) |
| F2.4 | The gap between A, B and C inside one cycle, and between cycles | diff of sorted timestamps | whether the 30-min cycle split holds; whether a cycle ever lacks a channel |
| F2.5 | Shape stability: per tool and channel, the RMS difference of each profile to that tool's median profile, over time | numpy | stable → overlay many cycles or show the deviation from the median; drifting → a waterfall (cycle × index heatmap) |
| F2.6 | Which scalar summarizes a profile best (mean, slope, min, argmin, peak-to-peak, RMS to the median)? Pick the one that moves at BM/PM or separates tools | compare against F1.6-style events | the trend chart that replaces "pick one cycle from a dropdown" |
| F2.7 | Describe one typical profile in words (monotonic? a single dip? noisy?) and give one full cycle (A/B/C, ~300 numbers) from one tool | sample | mock realism; the axis name (is the index a voltage step?) |

### F3. LaserPower

| # | Question | How | Decides |
| --- | --- | --- | --- |
| F3.1 | Cadence (as F1.1) | diff | as F1.1 |
| F3.2 | Correlation matrix of x1, y1, x2, y2, within tool and across tools; also test whether x1 ≈ k·x2, y1 ≈ k·y2, or x1/y1 ≈ x2/y2 | pandas `corr`, ratios | if one pair is derived from the other, show one pair. **The goal is to delete two of the three lenses** |
| F3.3 | Drift vs noise per channel over 90 days; steps at BM/PM (especially notes that mention laser) | as F1.4, F1.6 | whether "% vs baseline" is the right default |
| F3.4 | Fleet spread of each channel (as F1.7) | variance decomposition | whether a fleet view is worth building |
| F3.5 | Any documentation of what the four numbers are (Hitachi manual, FDC definitions, a colleague's note) | lookup | the axis labels; today they read x1/y1/x2/y2 |

### F4. ContactpinConductionInfo

| # | Question | How | Decides |
| --- | --- | --- | --- |
| F4.1 | The judgment vocabulary with frequencies. Is it exactly `Conduction` / `NotConduction`? | value counts | the green/red rule (today, anything not `Conduction` is red) |
| F4.2 | The NotConduction rate per tool and per channel; is it clustered in a few tools or spread across all? Is it persistent or intermittent inside one tool? | group-by | a table vs a tool × time status strip vs a fleet rate ranking |
| F4.3 | `values[3]` (the integer before the judgment): distribution, and its relation to the judgment | crosstab | whether it is a count or a retry number worth a column |
| F4.4 | The numbers after the judgment: how many (always 5?), their ranges, and whether the judgment can be predicted from them (for example the spread of the first four, or a threshold) | describe; a small decision tree | whether we can show the margin to the threshold instead of a bare verdict |
| F4.5 | The last number (`182501`): is it monotonic per tool and channel? If so, what is its per-interval increment? | diff | if it is a counter, its rate is the useful signal, not the raw value |
| F4.6 | How often a number uses a comma decimal (`'25,0'`)? Which tools? | regex count | whether the parser must accept a comma (today such a value is silently dropped) |

## SCE — Redis `sce_info` + MinIO archive

### S0. Coverage

| # | Question | How | Decides |
| --- | --- | --- | --- |
| S0.1 | `HKEYS sce_info`; tools per fab; which fabs have no SCE at all | Redis | the empty-state wording; the size of the comparison pool |
| S0.2 | Archive span: the earliest date folder, cadence (gap distribution), and missing dates per fab | MinIO listing | whether a longer window than 30 days is possible and worthwhile |
| S0.3 | `Coefficients` shape: a list of `{index, values}`? always 360 entries, indices 0..359, 2 values each? Any NaN? | scan every tool | the renderer's gap handling |

### S1. The coefficient curves

| # | Question | How | Decides |
| --- | --- | --- | --- |
| S1.1 | Fleet ranges of v0 and v1 per fab (min, p5, median, p95, max) | describe | the axis ranges; mock calibration |
| S1.2 | **Harmonic content.** For each tool, run an FFT over the 360 angles of v0 and of (v1 − 1). What share of the variance do harmonics 0..4 carry? | `numpy.fft.rfft` | if a few low harmonics carry most of the curve (≥ 90 %), a curve reduces to a few scalars (mean, amplitude and phase of the 1st and 2nd harmonic). Those can be trended and ranked across the fleet, which 360-point curves cannot |
| S1.3 | Is there a **reference tool**? Read `FileInfo.BaseSharpCharFile` for every tool in a fab: do they point at one shared file, or name a tool? | compare paths | today `FileInfo` is ignored. If it names the reference, "deviation from the reference" replaces "pick siblings by hand" as the comparison |
| S1.4 | Cross-tool vs within-tool: the RMS distance between tools in a fab vs the RMS change of one tool between revisions | numpy | whether 비교 or 시계열 is the more informative default tab |

### S2. Revisions over time

| # | Question | How | Decides |
| --- | --- | --- | --- |
| S2.1 | Between consecutive collections of one tool: how often are the coefficients **exactly** equal? When they are not, what is the max absolute difference? Show the distribution | per tool, per pair of consecutive dates | the revision collapse uses exact equality. If "unchanged" days differ by ~1e-9 jitter, name a tolerance that separates jitter from real re-tunes |
| S2.2 | Re-tunes per tool per 90 days, and whether they line up with BM/PM events (±2 days) | join `fab_inform_notes` | whether the BM/PM markers belong on the SCE charts |
| S2.3 | When the curve changes, does an `SCEParam`, `SemCond` or `ImgCond` field change on the same date? | diff blocks | whether the settings change can label the revision ("FitRangeEd 79 → 81") |
| S2.4 | For each settings field: the number of distinct values across the fab (latest snapshot) and over time per tool | count | constant fields are hidden by default in the compare table and dropped from the trend chips. **List every field that is constant fleet-wide** |

## Cross-cutting

| # | Question | Decides |
| --- | --- | --- |
| X1 | Given F1.7, F3.4, F4.2 and S1.4: for which signals is the spread between tools large enough to rank tools across a fab? | whether to build a fab-level "which tool stands out" view per signal, and for which signals |
| X2 | Given F0.2 and F0.6: how many bytes does a 30-day FDC response carry for the busiest tool? | whether the backend must return parsed or aggregated series instead of raw `values` strings |
| X3 | Any other place a hardware engineer already looks at these signals (an EES/FDC system screen, an Excel report)? Describe what it shows | copy what engineers already trust before inventing a view |

## Report format

1. **Findings**, one line each, grouped by the question ids above:

   ```text
   <id> | <finding with numbers> | <provenance> | evidence (query/code + one sample value)
   ```

2. **Decision table**: for every row whose "Decides" names options, say which
   option the numbers support, or `undecided` with the reason.

3. **Mock calibration block**, so the home mocks stop teaching false shapes.
   Per FDC key and for SCE, give: cadence (median and p90 gap), value ranges
   (p5/median/p95), the categorical vocabularies with rates, null or
   unparseable rates, typical step size at BM/PM, and the between-tool vs
   within-tool std. Plain numbers are enough.

4. **Samples**: the one SPMVoltages cycle from F2.7, and one tool's latest SCE
   `Coefficients` (360 pairs).

The confirmed facts then go into `hardware_network_fdc_cdsem.txt`,
`hardware_sce_setting.txt` and the matching `mock.py` files, as `CLAUDE.md`
requires for any office-DB fact.
