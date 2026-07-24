# Spec 2 — Skewvoir paired-scatter field-location pairing

Date: 2026-07-24
Depends on: Spec 1 (wafer geometry `map_offset` coherence) — the Position key reuses
`snapToDieCell` from the corrected geometry layer.
Scope: Skewvoir single-scope Correlation/Distribution explorer — how two selected
parameters of ONE MSR are paired for the Paired Scatter (and the panels that follow
its points).

## Problem

`buildCdCdRelationship` (`utils/skewvoirAnalysis/relationships.ts`) pairs two CD
parameters on the key `chip_number#sequence` (`siteKey`). But `sequence` is the
**per-parameter measurement order** — each parameter has its own sequence, so two
parameters measured at the same physical field carry **different** sequence numbers.
The join only works in the Phase-1 mock because the mock emits every parameter inside
one `sequence` loop, coincidentally aligning them. Office data breaks it silently.

The correct join is by **physical field location**, not measurement order.

## Design

Two location keys, both selectable, compared in practice so the weaker can be
retired later. `sequence` is retained as a third, legacy option.

### Keys

- **Field** (default): `fieldKey(row) = row.chip_coordinate.trim() || row.chip_number`.
  `chip_coordinate` is the field X,Y when present; office-side it is `""`
  (contract gap, `office_example.py:198`), so the key falls back to `chip_number`
  (die-level).
- **Position**: `snapToDieCell(row.stage_coordinate, geo)` from Spec 1 — the die cell
  recovered from the physical `stage_coordinate` via `map_offset` + `pitch`.
  Independent of the `chip_coordinate`/`chip_number` strings, so it validates them
  (catches a mislabeled `chip_number`). Rows with no snap (missing pitch/stage) drop
  and count as missing.
- **Sequence** (legacy): today's `chip_number#sequence`, byte-for-byte unchanged.

### Join with aggregation

`buildCdCdRelationship(rows, paramX, paramY, opts)` gains
`opts.pairBy: 'field' | 'position' | 'sequence'` and `opts.geo?: WaferGeometry`
(required for `'position'`).

For `'field'` / `'position'`:

1. Filter to measured rows (`isMeasuredRow`, existing gate).
2. Group each parameter's rows by the chosen key.
3. **Mean-aggregate** `cd_value` per key per parameter — a key holding several
   measured fields (common office-side when the key is die-level `chip_number`)
   collapses to one value. One point per key: unambiguous, loses within-die spread.
4. Pair keys present in **both** parameters. Keys in exactly one → `missingN`
   (symmetric difference), preserving the existing "never index-pair, count the
   drops" contract.

`'sequence'` keeps the current path untouched.

### `PairedPoint` shape

Add `fieldKey: string`. `chip` = the key's `chip_number` (drives `focus(chip)` →
`setFocusedSite`). `sequence` = the **min** sequence among the key's X rows — a
representative so scatter-click focus and spatial grouping keep working after
aggregation. Points sort by `sequence` as today.

CD↔FDC (`buildCdFdcRelationship`) is inherently per-sequence (`dynamic_fdc` is
sequence-keyed) — **unchanged**, and the toggle is hidden for it.

### UI — `factor/QueryBuilder.vue`

- `FactorQuery` gains `pairBy: 'field' | 'position' | 'sequence'` (default `'field'`).
- Add a compact segmented control `Pair by: [ Field | Position | Sequence ]`, shown
  only when `yKind === 'cd'`. Disable `Position` with a tooltip when
  coordinates/pitch are unavailable (`!coordinateReady`), same gating pattern as the
  radius/sector group select.

### Wiring — `views/Correlation.vue`

- Seed `pairBy` from the URL and persist it alongside `xParam`/`yParam` via
  `analysis.setXY` sibling (extend the existing URL round-trip; add a `pairBy` query
  param) so the explorer stays shareable.
- Pass `{ pairBy, geo: analysis.waferGeo.value }` into `buildCdCdRelationship`.
- Group distribution: unchanged mechanism (`groupBySeq` keyed by the paired point's
  representative `sequence`); within-die offset is negligible vs. pitch, so
  radius/sector stays correct.
- Marginal distribution + Paired Evidence table already derive from
  `relationship.points` — they follow the new pairs automatically.

## Testing — `utils/skewvoirAnalysis/relationships.test.ts`

- Field fallback: `chip_coordinate=""` rows pair by `chip_number`; non-empty
  `chip_coordinate` takes precedence.
- Mean aggregation: a key with two measured X and two measured Y values yields one
  pair at the two means.
- Missing-count symmetry: keys in exactly one parameter counted, not paired.
- Position key: on mock rows, `pairBy:'position'` pairs agree with the `chip_number`
  the mock assigned (uses Spec 1's coherent geometry).
- `pairBy:'sequence'` output identical to the pre-change baseline (regression pin).
- CD↔FDC unaffected by `pairBy`.

## Out of scope

- SET-scope legacy X/Y view — left as-is.
- Backend changes — `chip_coordinate`/`chip_number`/`stage_coordinate` already ship.
- Retiring Field or Position — that's a follow-up decision after real comparison.
