# Spec — Skewvoir FDC 분석 view split and sequence alignment

Date: 2026-07-27
Scope: Skewvoir analysis workspace. Splits the `time-series` view into a single-MSR
**FDC 분석** view and a multi-MSR **Time-Series** view, and corrects the sequence axis
the FDC panes are drawn on. Touches `back_dev_home/msr_file/providers/mock.py`,
because the current mock structurally cannot reproduce the defect.

## Problem

### 1. The view is named for the wrong thing

`views/TimeSeries.vue:6-9` branches on `analysis.scope`:

| Scope | Body |
| --- | --- |
| `single` | `SequenceWorkbench` — measurement order + dynamic FDC |
| `set` | Multi-Measurement Trend + Sequence Trend |

Only the `set` branch is a time series. The `single` branch has no time axis at all —
`sequence.ts:8-12` is explicit that the MSR file carries no per-sequence timestamp, so
every slope there is per *sequence step*, never per second. One rail entry named
"Time-Series" therefore describes half of what it opens, and the two halves have no
analytical relationship to each other.

### 2. FDC panes are drawn on the wrong axis

`sequence.ts:171-175` builds the shared cursor axis as the **union** of the active
parameter's CD sequences and every sequence present in `dynamic_fdc`:

```ts
const axis = new Set<number>()
for (const r of cdRows) axis.add(r.sequence)
for (const [seq] of fdcSeqEntries) axis.add(seq)
```

`sequence` is a global running counter over the whole MSR — numbered from the first
measurement to the last, one number per row, with consecutive numbers belonging to
*different* parameters (office-confirmed 2026-07-27). So selecting parameter P yields
an interleaved **subset** of sequences, while `dynamic_fdc` holds an entry for all of
them. The union axis is therefore always the full MSR, and every FDC pane plots
points that belong to other parameters' measurements.

Three consequences, in ascending order of harm:

- The CD line is mostly gaps while the FDC lines are dense — the panes look like they
  disagree about what was measured.
- Each FDC pane's `stats` (start / end / range / OLS slope) are computed over the
  whole MSR, then displayed under a heading scoped to one parameter. These read as
  findings.
- The matrix sparkline cells (`paramMatrix.ts:104`, which takes `model.sequences`
  verbatim) sit directly beside an `r` badge computed on the *correctly* joined
  subset — `relationships.ts:178-185` already inner-joins CD and FDC on sequence. The
  picture and the statistic next to it are computed on different samples.

`relationships.ts` needs no change. It has always been right; the axis has not.

### 3. The mock hides both

`mock.py:528-580` emits a cartesian product — `for sequence in ...: for parameter in
selected_params:` — so one sequence number is reused across every parameter row. Every
parameter then covers every sequence, the union axis equals the CD axis, and the
defect is invisible at home. This also violates the office invariant below.

## Invariant

**`len(rows) == len(dynamic_fdc)`, always.** One row is one measurement, one
measurement has one sequence number, and `dynamic_fdc` holds the tool state captured
for that sequence. A mismatch means the data is wrong, not that the UI should cope
silently.

This is new to the codebase and is what makes §2's fix well-defined: because rows and
FDC entries are 1:1, "the FDC point for this CD point" is total and unambiguous.

## Design

### 1. Sequence axis — `utils/skewvoirAnalysis/sequence.ts`

`analyzeSequence` takes a fourth argument, `axisMode: 'param' | 'all'`, defaulting to
`'param'`.

**`'param'`** — the axis is the sequences of rows where `parameter === activeParam`,
sorted. This replaces the union at `sequence.ts:171-175`. Each FDC series is sampled
at exactly those sequences; a scoped sequence with no `dynamic_fdc` entry stays a
`null` gap rather than being dropped, so the invariant's failure mode stays visible.

**`'all'`** — today's union behavior, preserved verbatim so the toggle is a genuine
comparison rather than a second path that drifts.

Two rules the `'param'` axis commits to:

- **Failure rows stay on the axis.** A row with `parameter === P` and
  `cd_value === null` is an attempted measurement of P: the tool was at that point and
  `dynamic_fdc` recorded its state. The CD line shows an honest gap (`connectNulls:
  false` is already set) while the FDC panes show data. That combination is frequently
  the most diagnostic sequence on the chart, so dropping it would discard the point of
  the view.
- **Stats follow the axis.** `start / end / range / slope / missing` recompute over
  the scoped set. An FDC slope stops meaning "per sequence across the MSR" and starts
  meaning "per sequence of this parameter's measurement order". `slopeUnit` already
  says `per sequence` and stays accurate.

`SequenceModel` gains:

| Field | Meaning |
| --- | --- |
| `axisMode` | Which rule produced `sequences` |
| `excludedFdc` | Count of `dynamic_fdc` sequences off the scoped axis |
| `integrity` | `{ rows, fdc, matched }` — the §Invariant check |

`integrity` compares `source.rows.length` against `Object.keys(source.dynamic_fdc).length`.
`source.rows` is `analysis.siteRows`, which is the unfiltered `focusFile.rows`
(`useSkewvoirAnalysis.ts:208`), so the comparison is valid.

### 2. Axis toggle

URL query param `fdcaxis` (`all` to opt out; absent means scoped), parsed and patched
in `routeQuery.ts` / `useSkewvoirRoute.ts` mirroring the existing `grain` param
(`useSkewvoirRoute.ts:51,101`). `routeQuery.ts`'s module doc makes the URL the single
source of truth so an analysis screen is shareable by link; a local `ref` would carve
out an exception for this one control.

Rendered in the **측정 순서 (Sequence)** panel's `#actions` slot beside the cursor
readout — that panel is the axis, so the control belongs on it. Panel meta gains
`· 타 parameter {excludedFdc} 제외` when scoped.

When `integrity.matched` is false, the FDC 분석 view shows a warning badge naming both
counts. It does not block rendering: a diagnosable data problem should be reported,
not turned into a blank page.

### 3. View split

| File | Change |
| --- | --- |
| `useSkewvoirWorkspace.ts` | `SkewvoirViewKind` += `'fdc'`; `SKEWVOIR_VIEW_MODES` → 6 entries |
| `routeQuery.ts` | `VIEW_KINDS` += `'fdc'` |
| `views/Fdc.vue` | **new** — `SequenceWorkbench` when single, empty state when set |
| `views/TimeSeries.vue` | drops the `single` branch; gains an empty state |
| `Workspace.vue` | one more `v-else-if`; "Keys 1-5" comment → 1-6 |

Rail order becomes 측정 개요 (1) · 위치 비교 (2) · FDC 분석 (3) · Time-Series (4) ·
상관 / 분포 (5) · 이미지 갤러리 (6). `fdc` uses `i-lucide-waves`, matching the Dynamic
FDC panes it opens; `time-series` keeps `i-lucide-trending-up`.

Both entries are always visible. The one that does not match the current scope renders
its own empty state (`MSR을 2개 이상 선택하세요.` / `단일 측정에서만 사용할 수 있습니다.`)
rather than being hidden, so the rail does not reshuffle under the user when scope
changes.

Keyboard shortcuts need no change — `Workspace.vue:165` derives them from
`viewModes[].index`. `Workspace.vue:116`'s recently-viewed rule stays correct: `fdc` is
single-scope by definition, so `msrs.length > 1 || activeKind === 'time-series'` still
classifies correctly.

### 4. Mock — `back_dev_home/msr_file/providers/mock.py`

The die-walk stays; the sequence becomes a **global counter incremented inside the
parameter loop** rather than shared across it:

```text
step at die (3,4), params [CD_LINE, SPACE]
   →  sequence 7   CD_LINE   chip "3,4"
      sequence 8   SPACE     chip "3,4"
```

Parameters measured at one point keep that point's `chip_number` / `stage_coordinate`
and take consecutive sequence numbers.

| Quantity | Before | After |
| --- | --- | --- |
| `len(rows)` | N × P | N × P (unchanged) |
| distinct sequences | N | N × P |
| `len(dynamic_fdc)` | N | N × P |
| invariant holds | no | yes |

With 2-3 parameters selected, a parameter's CD axis becomes every 2nd or 3rd sequence
— reproducing the office interleave, so the fix is verifiable at home.

The every-20th empty-row rule keys on the **step**, not the sequence, so every
parameter at a failed point fails together — which is what a failed point means.

Blast radius: `back_dev_home/msr_file/tests/test_contract.py`,
`test_office_template.py`, and the `num_measurements ≤ total_images // 2` invariant
comment at `mock.py:504-506`.

`office_example.py` gains a log-only warning in `build_response` when the invariant
fails, for office-side diagnosis. It does not raise — serving flagged data beats
serving nothing.

## Testing

| Suite | Cases |
| --- | --- |
| `sequence.test.ts` | scoped axis excludes off-param FDC sequences; failure rows stay on axis; stats computed on the scoped sample; `axisMode: 'all'` reproduces the union verbatim; `excludedFdc` count; `integrity.matched` both ways |
| `paramMatrix.test.ts` | cells align to the scoped axis; CD row is no longer mostly null |
| `routeQuery.test.ts` | `'fdc'` parses and round-trips; unknown view still falls back to Dashboard; `fdcaxis` round-trips |
| `msr_file` (pytest) | mock satisfies `len(rows) == len(dynamic_fdc)`; sequences are unique per row; parameters at one point share `chip_number` |

Browser verification per the `verify` skill: FDC 분석 and Time-Series each reachable
and each showing its empty state off-scope; scoped axis visibly shorter than the `전체
sequence` axis on a multi-parameter MSR.

## Deferred

`features.ts::dynamicFdcFeatures` reduces FDC across all sequences regardless of
parameter, and the backend's `fdc_params` summaries (`mean` / `std` / `drift_sigma` /
`status`) do the same. Both stay as they are: they are declared MSR-grain, and "what
did the tool do during this MSR" is a legitimately parameter-independent question.
Recorded here so it reads as a decision rather than an oversight.
