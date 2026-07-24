# SCE 시계열 — Full-Setting Param Trends + Per-Index Coefficient Trend — Design

Date: 2026-07-24
Feature: `hardware` → `sce` (CD-SEM, M-fab only)

## Goal

Extend the SCE 시계열 tab so every numeric setting parameter can be trended
across the bidaily collection dates (not just `SCEParam`), and add a coefficient
timeseries that tracks one index (0–359) over time — complementing the existing
all-index evolution overlay.

## Scope

In scope:

- `front-dev-home/app/utils/sceHistory.ts` — block-aware numeric key discovery,
  list-first value coercion, per-index coefficient series.
- `front-dev-home/app/utils/sceHistory.test.ts` — tests for the above.
- `front-dev-home/app/components/ebeam/hardware/ScePanel.vue` — grouped param
  chips, new per-index coefficient trend chart + index selector.
- `back_dev_home/.../providers/sce/mock.py` — realism: config blocks stable per
  tool, tuning outputs drift per date.
- `back_dev_home/.../tests/test_sce.py` — pin the stable/drift split.

Out of scope:

- The 비교 tab (settings compare table + coefficient overlay) — unchanged.
- `sce/office_example.py` — the office adapter already returns the full blocks;
  no shape change is needed for either new chart.

## Parameter Trend — all numeric setting params

Today `sceParamKeys` reads only the `SCEParam` block. Generalize to scan
`SCEParam`, `SemCond`, `ImgCond` (in that order) and keep only **numeric**
fields. `FileInfo` is excluded (paths), as are non-numeric strings
(`SemCond_Optics`, `SemCond_IpMode`, `SemCond_Detector`).

Value coercion — a field counts as numeric if it is either:

- a scalar that parses as a finite number (`SemCond_Vacc: '800'` → `800`), or
- a non-empty list whose **first** element parses (`ImgCond_Mag:
  ['150003298','150003298']` → `150003298`, `ImgCond_FocusOffset: ['-2']` → `-2`).

API:

- `sceTrendKeys(docs) -> {block, key, label}[]` — ordered by block, then key.
- `sceParamLabel(key)` — strips any of the three block prefixes.
- `sceParamSeries(docs, key)` — unchanged signature; resolves `key` in whichever
  block holds it. Field names are block-prefixed, so keys stay globally unique.

UI: the chip strip becomes grouped — a small block label followed by that
block's chips.

## Coefficient Trend — per index

New `sceCoeffIndexSeries(docs, index) -> {v0, v1}`: for each history doc, read
the `Coefficients` entry whose `index` matches and emit `values[0]` / `values[1]`
as `SceTrendPoint`s keyed by collection date. Reads only the target index (no
360-array build), so `sceHistory.ts` stays dependency-free.

Chart: dual y-axis (`values[0]` left, `values[1]` right dashed) over a time
x-axis, because the two live on different scales (~±0.02 vs ~0.9–1.0). Carries
the same BM/PM markLines as the param trend.

Index selection:

- A native `range` input (0–359) plus a number input for exact entry, following
  the existing `ToleranceKnob.vue` precedent. Default index `0`.
- Clicking the evolution chart also sets the index: its x-axis is a category
  axis of `0..359`, and `useEchart`'s `onClick` passes `params.name` (the
  category), so the click maps straight to an index.

시계열 tab order: param trend → **coefficient @ index trend (new)** →
coefficients evolution (existing).

## Mock Realism

`_tool_snapshot(tool, date_salt)` currently re-rolls every block per date, so
`SemCond_Vacc` would flip 500↔800 between collections — noise the new SemCond /
ImgCond trends would render as a meaningless zig-zag.

Split the seeding:

- **Config, stable per tool** — `SemCond`, `ImgCond` seed from the tool only, so
  they are identical on every collection date (a flat line = "stable", which is
  what production looks like).
- **Outputs, drift per date** — `SCEParam`, `Coefficients` keep the tool+date
  seed. `FileInfo` stays per-date (a fresh SharpChar file each collection).

This preserves the existing invariant that a history doc for date D equals a
snapshot taken as-of D: both sides compute config from the tool seed and outputs
from date D's seed.

## Testing

- `sceHistory.test.ts`: grouped keys across the three blocks (non-numeric
  excluded), list-first coercion, block-agnostic `sceParamSeries`, and
  `sceCoeffIndexSeries` across dates.
- `test_sce.py`: add a case asserting `SemCond`/`ImgCond` are identical across
  all history dates while `SCEParam`/`Coefficients` differ. Existing
  snapshot==history-as-of-date test must stay green.
- Manual: verify both charts render, the chips are grouped, the slider and
  evolution-click both move the index.
