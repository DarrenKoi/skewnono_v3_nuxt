# Spec 1 — Wafer geometry `map_offset` coherence (foundation)

Date: 2026-07-24
Scope: Skewvoir single-MSR wafer geometry layer (`utils/waferGeometry.ts`) and its
mock, so `map_offset` places measurement points correctly on the wafer map. This is
the foundation Spec 2 (paired-scatter Field/Position/Sequence pairing) builds on.

## Problem

`exe_detail_info.map_offset` is the die-grid offset (nm, x/y) that shifts the die
array away from the wafer centre. Today it is **parsed nowhere and applied nowhere**:

- `utils/waferGeometry.ts` reads `wafer_size` and `chip_pitch` but not `map_offset`
  or `map_origin`. `stagePosMm` subtracts only the wafer centre, and `dieCenterMm`
  is `col·pitch` from the centre.
- The Phase-1 mock (`back_dev_home/msr_file/providers/mock.py`) emits `map_offset`
  as **random noise** (`rng.randrange(-3_000_000, 3_000_000)`) that is *not* encoded
  in the `stage_coordinate` it generates (`_die_center_nm` = `wafer_center + col·pitch`,
  no offset). So the field "works" only because nothing reads it — the same
  Phase-1-artifact trap as the CD↔CD sequence join.

Consequence: office data whose die grid is genuinely offset by `map_offset` renders
its wafer map, radius plot, and spatial stats shifted off the true die grid. The
value must be applied to display the wafer map correctly.

## Placement semantics (confirmed)

A die's physical centre, corner origin, nm:

```text
die_center_nm(col, row) = wafer_center_nm + map_offset_nm + (col, row) · pitch_nm
```

`chip_number` ("col,row") is already expressed relative to the origin die
(`map_origin`), so `map_origin` stays **informational** — it is parsed and exposed
but does not enter the placement formula. `wafer_center_nm = wafer_size_nm / 2` on
each axis.

Inverse (physical position → die cell), used by Spec 2's Position key:

```text
col = round((stage_x_nm − wafer_center_nm − map_offset_x_nm) / pitch_x_nm)
row = round((stage_y_nm − wafer_center_nm − map_offset_y_nm) / pitch_y_nm)
```

Within-die measurement offset is < 0.5·pitch, so `round` recovers the exact die.

## Design

### `utils/waferGeometry.ts`

Extend `WaferGeometry` and `parseWaferGeometry`:

- Add `offsetXmm`, `offsetYmm` (parsed from `map_offset`, nm→mm; `0` when absent/blank).
- Add `originCol`, `originRow` (parsed from `map_origin`; informational, `0` when absent).
- `stagePosMm(stage, geo)` → subtract `(centerNm + offsetNm)` on each axis, so a
  point's mm position is measured from the **die-grid origin**, not the bare wafer
  centre. Radius/sector therefore measure from the grid origin consistently.
- `dieCenterMm(col, row, geo)` stays `col·pitch` (already grid-origin-relative — the
  offset now lives in `stagePosMm`, so map tiles and points share one origin).
- New `snapToDieCell(stage, geo): string | null` — `"col,row"` via the inverse
  above; `null` when pitch ≤ 0 or `stage` unparseable. (Exported here so both the
  wafer map and Spec 2 reuse one implementation.)

Keep the `sizeToMm` nm-vs-mm heuristic and all existing null contracts unchanged.

### Mock coherence — `back_dev_home/msr_file/providers/mock.py`

Make the mock a faithful mirror of the confirmed semantics:

- `_die_center_nm(col, row, geom)` adds the MSR's `map_offset`: `wafer_center +
  offset + col·pitch`. So the generated `stage_coordinate` genuinely encodes the
  offset and round-trips through `stagePosMm` / `snapToDieCell`.
- Stop emitting `map_offset` as pure noise: derive it once per MSR (seeded, small,
  e.g. within ±0.3·pitch) and use the **same value** in `_die_center_nm` and in the
  emitted `exe_detail_info.map_offset`. `map_origin` stays `cols//2, rows//2`.
- `_measured_dies` edge-exclusion may keep using the centre-relative radius
  (`hypot(col·pitch, row·pitch)`); the small offset does not push dies past the
  wafer, and the edge ring is cosmetic. (Note in code; revisit only if a die lands
  off-wafer in practice.)

### Ripple consumers (no logic change, re-verify)

`stagePosMm`/`dieCenterMm`/`siteRadiusMm` feed `waferPoints`, `waferDieGrid`,
`spatial`, `features`, `MeasurementPoints.vue`, `RadiusPlot.vue`. Because generation
and display now apply `map_offset` **consistently**, their relative geometry is
unchanged; only absolute positions shift by the offset. Update any test that pins a
literal `stage_coordinate`-derived mm/radius value.

## Testing

- `utils/waferGeometry.test.ts`:
  - `parseWaferGeometry` extracts `offsetXmm/offsetYmm/originCol/originRow`; blanks → 0.
  - `stagePosMm` subtracts centre + offset (table case with non-zero offset).
  - `snapToDieCell` round-trips `dieCenterMm(col,row)` + a sub-half-pitch jitter back
    to `"col,row"`; returns `null` on pitch 0 / bad input.
- Mock: a small Python check (or existing msr_file test) that for a sampled MSR,
  `snapToDieCell(row.stage_coordinate)` equals `row.chip_number` for measured rows —
  i.e. the mock now round-trips. This is the Phase-1 proof the offset is coherent.
- Existing `waferPoints.test.ts` / `spatial.test.ts` updated for shifted absolutes.

## Out of scope

- Paired-scatter pairing (Spec 2).
- Any office adapter change — `stage_coordinate` and the `exe_detail_info` fields
  already ship office-side (`office_example.py`); only their interpretation changes.
- Notch orientation, cross-wafer σ — untouched.
