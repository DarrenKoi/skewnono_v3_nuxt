# Skewvoir — distinct color per selected measurement point

**Date:** 2026-07-25
**Status:** Design approved, pending spec review
**Scope:** `skewvoir/analysis` dashboard overview panels (CD-SEM + HV-SEM)

## Problem

When a user selects several measurement points (the checkboxes in the
**Measurement Points** table), those picks are meant to stand out across the
linked overview charts so a specific point can be traced from its wafer position
to its radial value to where it sits in the distribution.

Today that linkage is weak and incomplete:

- **Wafer Map** and **Radius Plot** already draw a "selected" halo, but every
  selected point shares **one** color — and the two charts don't even match each
  other (`WaferMap.vue:253` uses `sk.brand`, `RadiusChart.vue:270` uses
  `sk.series`). You can see *that* points are selected, never *which is which*.
- **Distribution** receives no selection information at all
  (`Distribution.vue` passes only `rows` + `parameter`), so selected points are
  invisible there.

There is no per-point identity: two selected points look identical, so
cross-chart tracing ("where is *this* one on the wafer vs. in the tail of the
distribution?") is impossible.

## Goals

- Each selected measurement point gets its **own color**, held **constant across
  the Wafer Map, Radius Plot, and Distribution** — the same hue identifies the
  same point in every panel.
- The **Measurement Points table** shows a matching color swatch per selected
  row, acting as the legend (color → which point).
- Reuse the repository's existing "color = identity" convention rather than
  inventing a parallel one.

## Non-goals (explicitly out of scope)

- **Multi-parameter overlay.** Each chart still renders a single parameter (the
  active/primary one). We are coloring *selected sites within the active
  parameter*, not overlaying `selectedParams` as separate series. (This was the
  larger alternative the user considered and declined.)
- The `position/` spatial views (`SpatialWorkbench`, `SpatialLayerMap`,
  `RadialProfile`) and the Correlation view. Untouched.
- A true value-positioned rug in **Histogram** mode (see Distribution below).

## Current architecture (facts this design builds on)

- **Selection state** lives in `useSkewvoirAnalysis.ts`:
  - `selectedSites: useState<string[]>` — keyed by `siteKey(param, seq)` =
    `` `${param} ${seq}` `` (`utils/mpSelection.ts`). Insertion-ordered:
    `toggleKey` appends new keys (`[...list, key]`). Kept across `activeParam`
    changes; cleared when the focus MSR (wafer) changes.
  - `selectedSeqsForActiveParam: computed<number[]>` — the subset of selected
    sequences belonging to the currently active parameter. This is what the
    single-parameter charts already consume.
- **Charts bind only the active parameter**: `WaferMap.vue:42`,
  `RadiusPlot.vue:39/90`, `Distribution.vue:23`.
- **Existing "color = identity" precedent**: `utils/hardwareCompare.ts` — a pure
  `cycle(keys, ramp) → Record<key, color>` map plus a curated 8-hue fallback
  ramp, consumed identically by every chart so a picked tool is one color
  everywhere. Unit-tested in `hardwareCompare.test.ts`. This design mirrors it,
  keyed by *site* instead of *tool*.
- **Color philosophy** (`utils/chartPalette.ts`): colors whose *meaning* is fixed
  (`SK_SCALE` heat ramp, `SK_STATE` severity) are theme-independent constants;
  colors that are mere *presentation* follow the ECharts theme. A selected
  point's identity color is *meaning* (it must stay comparable across
  screenshots and not collide with severity), so it belongs with the constants.

## Design

### 1. One deterministic color source

A pure, unit-testable helper assigns colors, mirroring `hardwareCompare.ts`:

```text
assignSiteColors(orderedSiteKeys: string[], ramp: readonly string[])
  → Record<siteKey, string>
```

- Input is `selectedSites` verbatim (already insertion-ordered).
- Assigns `ramp[i]` to the i-th key. **Caps at `ramp.length`**: keys beyond the
  ramp get **no entry** (consumers substitute a neutral tone). Colors are **not**
  repeated past the cap — a repeated hue would be a false identity match. This is
  the one deliberate deviation from `hardwareCompare`'s modulo cycling.
- **Deselect behavior:** colors follow insertion order, so removing an
  early-picked point renumbers the rest. Accepted as-is (highlights are
  ephemeral; no persistent slot map).

Placement: the helper is pure → co-locate with the other selection helpers in
`utils/mpSelection.ts` (or a sibling `utils/siteColors.ts`), importing the ramp
constant. Tested under `node --test` like `mpSelection.test.ts`.

### 2. Palette

Add a fixed identity ramp to `utils/chartPalette.ts`, alongside `SK_SCALE` /
`SK_STATE`:

```text
export const SK_SITE = [ ~10 hues ] as const
```

- **Cool-first ordering** (teal, blue, violet, green, …) so the earliest picks
  are visually farthest from the heat ramp's warm end (`SK_SCALE`) and from the
  semantic red (`SK_STATE.bad`). Warm/red-adjacent hues, if included at all, come
  last. This prevents an identity halo from being misread as severity on the
  wafer map, where red rings already mean "outlier/bad."
- **Neutral overflow** = the theme's muted tone (`sk.muted`), resolved at render
  time in each chart, used for any selected point past the cap.

### 3. Composable exposure

`useSkewvoirAnalysis.ts` adds a derived map and accessor:

- `siteColorMap = computed(() => assignSiteColors(selectedSites.value, SK_SITE))`
- `siteColor(param, seq): string | null` → `siteColorMap.value[siteKey(param, seq)] ?? null`
  (`null` = overflow; consumer paints it `sk.muted`).

Both are returned from the composable so every surface reads the same source.

### 4. Per-panel rendering

Each panel keeps its single active parameter.

- **Wafer Map** (`WaferMap.vue` leaf + dashboard wrapper): the existing selected
  halo (`WaferMap.vue:253`) becomes per-point. The wrapper derives, for each seq
  in `selectedSeqsForActiveParam`, its identity color and passes a
  `seq → color` map to the leaf (additive prop; existing `selectedSeqs` stays as
  the membership set). The halo **ring/border** takes the identity color; the
  point's heat-ramp *fill* is untouched. Overflow seqs → `sk.muted` ring.
  The **WaferDetailModal** (the expand view sharing the same leaf) gets the same
  prop for consistency.
- **Radius Plot** (`RadiusChart.vue` leaf + `RadiusPlot.vue` wrapper): the
  selected-overlay dot (`RadiusChart.vue:270`) takes the identity color per seq
  via the same `seq → color` map. Also resolves today's brand/series mismatch.
- **Distribution** (`Distribution.vue` wrapper + `DistributionChart.vue` leaf):
  the wrapper computes the selected points' `(value, color)` pairs for the active
  parameter (from `siteRows` ∩ `selectedSeqsForActiveParam` + `siteColor`) and
  passes them to the leaf. Per the chosen scope — **Box + Violin only**:
  - **Box** — color and enlarge the selected values' raw dots (the jittered
    raw-point overlay at `DistributionChart.vue:200-213` already plots every
    value; selected ones switch from the shared brand to their identity color).
  - **Violin** — a colored rug tick per selected value along the value axis (the
    violin's x-axis is `type: 'value'`, so ticks sit at true positions).
  - **Hist** — **no true rug** (its x-axis is categorical bin-centers). Instead,
    tint the histogram bar(s) of the bin(s) that contain a selected value, as a
    lightweight approximation. If a single bin holds multiple selected points of
    different colors, it takes the first (or a neutral "mixed" tint) — precise
    per-point marks are out of scope for Hist.

### 5. Measurement Points table = legend

`MeasurementPoints.vue`: each **selected** row shows a small color swatch in its
identity color (unselected rows: none), placed in/next to the checkbox cell.
This is the key that maps a color back to its point. Because the color map is
keyed globally by `(param, seq)`, swatches stay consistent even for selected
points of a non-active parameter shown in the multi-param table.

## Data flow

```text
selectedSites (ordered site keys)                     ── useSkewvoirAnalysis
      │  assignSiteColors(·, SK_SITE)
      ▼
siteColorMap : Record<siteKey, color>  ─────────────► MeasurementPoints (row swatch)
      │  siteColor(activeParam, seq)
      ▼
seq → color (active param) ──► WaferMap wrapper ──► WaferMap leaf   (halo ring)
                           └─► RadiusPlot wrapper ─► RadiusChart leaf (selected dot)
      │  (value, color) pairs (active param)
      └────────────────────► Distribution wrapper ─► DistributionChart leaf
                                                       (Box dots / Violin rug / Hist bin tint)
```

## Edge cases

- **> cap (~10) selected:** overflow points render in `sk.muted` everywhere
  (ring, dot, box dot, rug, swatch). No hue repeats.
- **Cross-parameter selection:** `selectedSites` can span parameters, but each
  chart only draws the active parameter's subset; the swatch legend covers all.
  Keying by `(param, seq)` keeps identity global and collision-free.
- **Deselect reshuffle:** accepted (see §1).
- **Duplicate values in Hist bins:** first-color / neutral-mixed tint (see §4).
- **Focus ring vs. identity ring (wafer):** the focused-sequence ring
  (`sk.ink`, `WaferMap.vue:261`) and outlier ring (`SK_STATE.bad`) are separate
  z-layers and keep their current styling; the identity ring is the existing
  selected-halo layer, only its color changes. Ordering/precedence unchanged.

## Testing

- **Unit** (`node --test`): `assignSiteColors` — order mapping, cap → omitted
  keys, empty input, ramp shorter than input. Parallels `hardwareCompare.test.ts`.
- **Existing suites** must stay green (`chartPalette.test.ts`, `mpSelection`
  consumers, `useSkewvoirAnalysis.focusCache.test.ts`).
- **Manual/visual** (per `verify` skill): select 3–4 points, confirm the same
  hue identifies each point across Wafer Map, Radius Plot, Distribution
  (Box + Violin), and the table swatch; switch active parameter and confirm only
  that parameter's picks light up; exceed the cap and confirm neutral overflow;
  toggle color mode (light/dark) and confirm the ramp stays legible.

## Files touched

| File | Change |
| --- | --- |
| `utils/chartPalette.ts` | Add `SK_SITE` identity ramp constant |
| `utils/mpSelection.ts` (or new `utils/siteColors.ts`) | Add pure `assignSiteColors` |
| `utils/*.test.ts` | Tests for `assignSiteColors` |
| `composables/useSkewvoirAnalysis.ts` | Add + expose `siteColorMap` / `siteColor` |
| `components/ebeam/skewvoir/WaferMap.vue` (leaf) | Per-seq identity ring color |
| `components/ebeam/skewvoir/WaferDetailModal.vue` | Pass seq→color to shared leaf |
| `components/ebeam/skewvoir/dashboard/WaferMap.vue` (wrapper) | Derive + pass seq→color |
| `components/ebeam/skewvoir/RadiusChart.vue` (leaf) | Per-seq identity dot color |
| `components/ebeam/skewvoir/dashboard/RadiusPlot.vue` (wrapper) | Derive + pass seq→color |
| `components/ebeam/skewvoir/dashboard/Distribution.vue` (wrapper) | Compute + pass (value,color) pairs |
| `components/ebeam/skewvoir/DistributionChart.vue` (leaf) | Box dots + Violin rug + Hist bin tint |
| `components/ebeam/skewvoir/dashboard/MeasurementPoints.vue` | Swatch per selected row |
