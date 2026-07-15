# Skewvoir Analysis — Compact Single-Screen Dashboard

Date: 2026-07-15
Area: `front-dev-home/app/components/ebeam/skewvoir` (Dashboard view)
Status: Approved (brainstorming) → implementing

## Problem

The `skewvoir/analysis` Dashboard view spreads eight full-width/large panels
down a tall page that requires scrolling. The linked-inspection panels
(Wafer Map, Radius Plot, Measurement Points) — which share one
`focusedSequence` so a click in one rings the others — are scattered across
non-adjacent grid cells, so the sync is never visible at once. The Wafer Map
is oversized, draws no actual wafer, and only offers a single dot view. The
stat cards (coverage, 이상 사이트) and the parameter table consume a lot of
vertical space.

## Goals

1. Fit the whole Dashboard in one viewport — **no page scroll**; panels scroll
   internally.
2. Wafer Map: draw the actual **wafer circle**, and offer **two modes** —
   `Sites` (discrete colored dots, today's view) and `Field` (each measured die
   as a filled color tile — the fab wafer-map look).
3. Place the linked cluster (Wafer + Radius + Measurement Points) **adjacent**
   so synced selection is visible.
4. Measurement Points gains a **`전체 | 이상·실패` filter toggle** that folds in
   the standalone 이상/실패 site table.
5. Shrink the coverage/이상 stats and the parameter navigator.
6. **Clicking a parameter syncs and updates every panel — including the SEM
   micrograph fetched from the backend.**

## Non-goals

- No backend or data-model changes. Everything reuses `useSkewvoirAnalysis`.
- No interpolated/synthetic field values (see Field-mode decision below).
- No change to other views (Time-Series, Position Stack, Correlation, Gallery)
  or the shared low-level charts (`DistributionChart`, `WaferHeatChart`,
  `RadiusChart`).

## Layout (`views/Dashboard.vue`)

Full-height flex column filling the workspace body (`h-full`, `min-h-0`):

```
[ StatBar ]  thin row: 측정 성공률 · 이상 사이트 · {param} 평균±3σ · 정렬   (~40px)
[ ParamNav ] chips: [WAFER] [GATE_CD •] [SPACE]  — click = setParam           (~34px)
[ grid xl:grid-cols-12, flex-1, min-h-0 ]
  col-span-4  Wafer Map (square, [Sites|Field])   +  Radius Plot (stacked)
  col-span-4  Measurement Points ([전체|이상·실패], internal scroll)
  col-span-4  Detail tabs [Distribution · SEM · 조건] (internal scroll)
```

Below `xl` the grid stacks and the workspace's own `overflow-auto` handles
small screens gracefully.

## Component changes

### Single reactive source (the sync invariant)

All panels derive from `analysis.activeParam` / `activeOverview` /
`activeSummary` / `focusedSequence` via `computed` — never a local `ref` copy of
param-derived state. `ParamNav` click → `setParam` → URL `mp` → `activeParam`
recomputes → every filter recomputes → SEM `<img :src>` string changes →
browser refetches `/api/msr-image?name=…`. `focusedSequence` is already nulled
on param change by a watch in the composable.

### Wafer Map — `WaferMap.vue` (chart) + `dashboard/WaferMap.vue` (panel)

- New `mode: 'Sites' | 'Field'` prop; `[Sites | Field]` toggle in the panel
  header (existing `PanelFrame` toggle mechanism, `v-model`).
- **Wafer circle** in both modes: a closed silent `line` series of ~120 points
  `[R·cosθ, R·sinθ]`, `R = maxChipRadius + margin`, plus a faint center mark.
  Panel body forced **square** (`aspect-square`) with symmetric grid margins so
  the circle is not an ellipse.
- **Sites mode**: today's behavior (value-colored dots via `visualMap`, ✕
  failures, ◎ outlier rings, focus ring) + circle.
- **Field mode**: ECharts **custom series** — `renderItem` draws a unit rect per
  measured die between two `api.coord()`-converted corners, color via
  `api.visual('color')` off the same `visualMap`; dies outside the circle
  clipped. Failures/outliers/focus overlays still drawn.
- Body height `h-full` (was fixed `h-72`). Compact inline legend
  (낮음/높음/✕/◎) moves into the panel footer; the big legend paragraph in
  `Dashboard.vue` is deleted.
- Field-mode click still emits `focus` (tiles carry the sequence `name`).

### Measurement Points — `dashboard/MeasurementPoints.vue`

- `[전체 | 이상·실패]` toggle in the header.
- `전체`: current table (`# · CHIP XY · DATA · RADIUS · SEQ`).
- `이상·실패`: rows from `analysis.activeOverview.tableRows`
  (`SEQ · CHIP · CD · Δ vs sites · 판정` badge) + the "실패 사이트는 통계 제외"
  note — i.e. the retired `SiteVerdicts` content.
- Row click → `setFocusedSequence` (unchanged). Internal scroll.

### New — `overview/StatBar.vue`

One thin row of stat pills replacing `VerdictStrip`'s four large cards; same
data from `activeOverview` / `activeSummary` / alignment.

### New — `dashboard/ParamNav.vue`

Horizontal chip row replacing the `DataSummary` table: one chip per parameter,
active highlighted, a small red dot when that param has failures or outliers
(from `overviewFor(param)`). Click → `setParam`.

### New — `dashboard/DetailTabs.vue`

One `PanelFrame` with tabs `[Distribution · SEM · 조건]` wrapping the existing
`Distribution`, `SemImage`, and `Acquisition` bodies (only one rendered at a
time). SEM tab keeps focus-driven reorder so a clicked point shows its image.

### Removed (dashboard-only, safe to delete)

- `overview/VerdictStrip.vue`
- `overview/SiteVerdicts.vue`
- `dashboard/DataSummary.vue`

## Field-mode rendering decision

Field mode renders **only real measured dies** as color tiles; unmeasured dies
stay blank. Interpolating values between measured points (IDW/contour) would
invent data in a metrology tool and is rejected. This matches the fab-standard
die-bin wafer map.

## Physical wafer coordinate model (follow-up)

The wafer map was made physically coherent instead of plotting an abstract chip
grid, per `docs/datatables/msr_file_pickle.txt`:

- **`chip_number`** = die index `(col,row)`, centred on the wafer.
- **`stage_coordinate`** = physical position in **nm**, corner origin — the wafer
  centre sits at `(wafer_size/2, wafer_size/2)` nm.
- **`exe_detail_info`** carries `wafer_size` (mm) and `chip_pitch` (nm/die).

Backend (`back_dev_home/msr_file/data.py`): one shared `_wafer_geometry(msr)`
sets `chip_pitch = wafer_diameter / array`, so `chip_array`, `chip_pitch` and
`wafer_size` agree. `_measured_dies(msr)` samples die indices spread across the
disk (edge-excluded, shuffled — no more edge-column marching). `stage_coordinate`
= die centre + a small in-die offset. `_cd_field` / `_cd_value` give each site a
tight value: wafer mean + a smooth radial (centre→edge) trend + ~1% noise, plus a
few injected outliers — so leave-one-out flags a handful, not most of the wafer.

Frontend (`utils/waferGeometry.ts`): `parseWaferGeometry` (wafer_size/chip_pitch),
`stagePosMm` (stage → mm from centre), `dieCenterMm`, `siteRadiusMm`. Exposed as
`analysis.waferGeo`. The wafer map plots **dots at stage-mm**, **Field tiles at
die centres sized by pitch**, and the **circle at `wafer_size/2`**; the radius
plot and Measurement Points radius are physical **mm**. `WaferHeatChart`
auto-scales its axis so Position Stack's wider die grid never clips.

## Acceptance criteria

1. Dashboard fits one viewport with no page scroll at desktop (`xl`) sizes;
   each data panel scrolls internally when its content overflows.
2. Wafer Map draws a wafer circle in both modes; `[Sites | Field]` toggle
   switches between colored dots and color tiles; ✕/◎/focus overlays present in
   both.
3. Wafer + Radius + Measurement Points are visually adjacent; clicking a point
   in any one rings/highlights it in the others (existing `focusedSequence`).
4. Measurement Points `이상·실패` filter shows exactly `activeOverview.tableRows`
   with verdict/Δ columns.
5. Clicking a parameter chip updates StatBar, Wafer Map, Radius, Measurement
   Points, Distribution, and the SEM image (new micrograph fetched) — verified
   live.
6. `npm run build`/typecheck passes; no references to the deleted components
   remain.
