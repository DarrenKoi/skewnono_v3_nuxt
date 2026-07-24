# Spec 1 — Wafer geometry `map_offset` coherence (foundation)

Date: 2026-07-24
Scope: Skewvoir wafer geometry layer (`utils/waferGeometry.ts`) and its Phase-1 mock,
so `map_offset` places the **die grid** correctly on the wafer map. Foundation for
Spec 2 (paired-scatter Field/Position/Sequence pairing).

## Problem

`exe_detail_info.map_offset` is the die-grid offset (nm, x/y) that shifts the die
array away from the wafer centre. Today it is **parsed nowhere and applied nowhere**:

- `utils/waferGeometry.ts` reads `wafer_size` and `chip_pitch` but not `map_offset`
  or `map_origin`. `dieCenterMm` is `col·pitch` from the wafer centre.
- `utils/waferDieGrid.ts` draws die boundaries at `(k + 0.5)·pitch` from the wafer
  centre, so **grid lines are misaligned from the measured points by exactly
  `map_offset`** — the visible display bug.
- The Phase-1 mock (`back_dev_home/msr_file/providers/mock.py`) emits `map_offset`
  as **random noise** (`rng.randrange(-3_000_000, 3_000_000)`) that is *not* encoded
  in the `stage_coordinate` it generates (`_die_center_nm` = `wafer_center + col·pitch`,
  no offset). The field "works" only because nothing reads it — the same
  Phase-1-artifact trap as the CD↔CD sequence join.

## Placement semantics (confirmed)

A die's physical centre, corner origin, nm:

```text
die_center_nm(col, row) = wafer_center_nm + map_offset_nm + (col, row) · pitch_nm
```

`chip_number` ("col,row") is already expressed relative to the origin die
(`map_origin`), so `map_origin` stays **informational** — parsed and exposed, but not
in the placement formula.

Inverse (physical position → die cell), used by Spec 2's Position key:

```text
col = round((stage_x_nm − wafer_center_nm − map_offset_x_nm) / pitch_x_nm)
```

Within-die measurement offset is < 0.5·pitch, so `round` recovers the exact die.

### What `map_offset` does NOT change

`map_offset` shifts the **die grid**, not the wafer. Centre→edge effects reference
the physical wafer centre, so:

- `stagePosMm` stays **unchanged** — mm from the wafer centre.
- `siteRadiusMm`, sector assignment, the radial trend/residuals, and every point's
  plotted position stay unchanged.

Only die-indexed geometry moves. This keeps the blast radius small: `spatial.ts`,
`features.ts`, `RadiusPlot.vue`, `MeasurementPoints.vue` are untouched.

**Empirically confirmed, not assumed.** The offset's sign and per-axis convention
(whether office `map_offset` adds to or subtracts from the grid origin, and whether
its y agrees with the wafer map's y direction) are settled by trial and error against
the rendered wafer map, not derived on paper. Keep the application in ONE place
(`parseWaferGeometry` → the die-indexed helpers) so flipping a sign is a one-line
change, and verify visually before locking it in. The mock round-trip check
(`snapToDieCell(stage_coordinate) == chip_number`) is the objective test that
whichever convention we pick is self-consistent.

## Design

### `utils/waferGeometry.ts`

- `WaferGeometry` gains `offsetXmm`, `offsetYmm` (from `map_offset`, nm→mm; `0` when
  absent/blank) and `originCol`, `originRow` (from `map_origin`; informational).
- `stagePosMm` — **unchanged**.
- `dieCenterMm(col, row, geo)` → `[offsetXmm + col·pitchXmm, offsetYmm + row·pitchYmm]`.
- `mmToDieIndex(mm, pitchMm, offsetMm = 0)` → `round((mm − offsetMm) / pitchMm)`;
  `null` when pitch ≤ 0. Default `0` keeps existing callers compiling.
- New `snapToDieCell(stage, geo): string | null` → `"col,row"` via the inverse above;
  `null` when pitch ≤ 0 or `stage` unparseable. Exported here so the wafer map and
  Spec 2 share one implementation.

Keep the `sizeToMm` nm-vs-mm heuristic and all existing null contracts unchanged.

### `utils/waferDieGrid.ts`

`boundaries()` gains an `offset` argument; boundary coordinates become
`offset + (k + 0.5)·pitch`, still clipped to the wafer chord and still capped by
`MAX_LINES_PER_AXIS`. `buildDieGridSegments` passes `geo.offsetXmm` / `geo.offsetYmm`.
This is what visually aligns the grid with the points.

### `utils/waferAxis.ts`

Pass the matching axis offset into `mmToDieIndex` so die-index axis labels stay
correct under a shifted grid.

### Mock coherence — `back_dev_home/msr_file/providers/mock.py`

One source of truth so the emitted `map_offset` and the generated `stage_coordinate`
can never disagree:

- `WaferGeom` gains `offset_x_nm`, `offset_y_nm`, computed in `_wafer_geometry(msr)`
  (seeded, within ±0.3·pitch — small and realistic).
- `_die_center_nm` adds them: `wafer_center + offset + col·pitch`.
- `_exe_detail` emits `map_offset=f"{geom.offset_x_nm},{geom.offset_y_nm}"` and drops
  its now-unused local `rng`. `map_origin` stays `cols//2, rows//2`.
- `_measured_dies` edge-exclusion keeps using the centre-relative radius; the offset
  is < 0.3·pitch so no die is pushed off-wafer, and the edge ring is cosmetic.

## Testing

- `utils/waferGeometry.test.ts` (`npm --prefix front-dev-home test`):
  - `parseWaferGeometry` extracts `offsetXmm/offsetYmm/originCol/originRow`; blanks → 0.
  - `stagePosMm` unchanged under a non-zero `map_offset` (regression pin).
  - `dieCenterMm` includes the offset.
  - `mmToDieIndex` with an offset; default arg keeps old behaviour.
  - `snapToDieCell` round-trips `dieCenterMm(col,row)` + sub-half-pitch jitter back to
    `"col,row"`; `null` on pitch 0 / bad input.
- `utils/waferDieGrid.test.ts`: boundaries shift by the offset; zero offset reproduces
  today's values.
- `back_dev_home/msr_file/tests/`: for a sampled MSR, every measured row satisfies
  `snap(stage_coordinate) == chip_number` using the emitted `map_offset` — the
  Phase-1 proof the mock is coherent.

## Out of scope

- Paired-scatter pairing (Spec 2).
- Office adapter changes — `stage_coordinate` and `exe_detail_info` already ship
  office-side; only their interpretation changes.
- Notch orientation, cross-wafer σ.
