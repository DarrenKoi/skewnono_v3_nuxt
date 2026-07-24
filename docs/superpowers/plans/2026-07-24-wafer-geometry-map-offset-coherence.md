# Wafer Geometry `map_offset` Coherence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Apply `exe_detail_info.map_offset` to the die-indexed wafer geometry so the die grid lines up with the measured points, and make the Phase-1 mock encode the same offset it reports.

**Architecture:** `map_offset` shifts the **die grid**, not the wafer. `stagePosMm` (mm from the wafer centre) stays untouched, so radius/sector/spatial analysis are unaffected. Only die-indexed helpers move: `dieCenterMm`, `mmToDieIndex`, the `waferDieGrid` boundaries, plus a new `snapToDieCell` that Spec 2 reuses. The mock gains the offset in its `WaferGeom` so the emitted `map_offset` and the generated `stage_coordinate` come from one source and can never disagree.

**Tech Stack:** Nuxt 4 / TypeScript (frontend, pure utils tested with `node --test`), Python 3 / Flask mock (tested with pytest).

## Global Constraints

- Spec: `docs/superpowers/specs/2026-07-24-wafer-geometry-map-offset-coherence-design.md`.
- Placement formula: `die_center_nm(col,row) = wafer_center_nm + map_offset_nm + (col,row)·pitch_nm`. `chip_number` is already origin-centred, so `map_origin` is **informational only** — parsed and exposed, never in the placement math.
- `stagePosMm` MUST stay unchanged (mm from the wafer centre). Do not make radius/sector measure from the grid origin.
- Do NOT modify `spatial.ts`, `features.ts`, `RadiusPlot.vue`, `MeasurementPoints.vue`.
- Units: `map_offset` and `chip_pitch` arrive in **nm** as strings; `WaferGeometry` stores **mm**. `NM_PER_MM = 1_000_000`.
- Missing/blank geometry fields degrade to `0` — never `NaN`, never a fabricated fallback die.
- Frontend tests: `npm --prefix front-dev-home test` (`node --test "app/**/*.test.ts"`). Pure utils only — no Nuxt, no bundler; sibling imports carry an explicit `.ts` extension.
- Backend tests: `.venv/bin/python -m pytest back_dev_home/msr_file`.
- Markdown edits require `npm run lint:md`.
- Commit directly to `main` (per CLAUDE.md). Commit message style: `type(scope): summary` plus a body when not self-evident.

---

### Task 1: Parse `map_offset` / `map_origin` into `WaferGeometry`

**Files:**

- Modify: `front-dev-home/app/utils/waferGeometry.ts:20-51` (interface + `parseWaferGeometry`)
- Modify: `front-dev-home/app/utils/waferPoints.test.ts:9` (literal fixture)
- Modify: `front-dev-home/app/utils/waferDieGrid.test.ts:6-12` (literal fixture)
- Test: `front-dev-home/app/utils/waferGeometry.test.ts`

**Interfaces:**

- Consumes: nothing (first task).
- Produces: `WaferGeometry` gains `offsetXmm: number`, `offsetYmm: number`, `originCol: number`, `originRow: number`. Every later task reads `geo.offsetXmm` / `geo.offsetYmm`.

- [ ] **Step 1: Write the failing tests**

Append to `front-dev-home/app/utils/waferGeometry.test.ts`:

```ts
test('parseWaferGeometry reads map_offset (nm → mm) and map_origin', () => {
  const g = parseWaferGeometry(info({ map_offset: '0,4610000', map_origin: '12,15' }))
  assert.equal(g.offsetXmm, 0)
  assert.ok(Math.abs(g.offsetYmm - 4.61) < 1e-9)
  assert.equal(g.originCol, 12)
  assert.equal(g.originRow, 15)
})

test('parseWaferGeometry defaults map_offset/map_origin to 0 when blank or absent', () => {
  const g = parseWaferGeometry(info({ map_offset: '', map_origin: '' }))
  assert.equal(g.offsetXmm, 0)
  assert.equal(g.offsetYmm, 0)
  assert.equal(g.originCol, 0)
  assert.equal(g.originRow, 0)
  const none = parseWaferGeometry(null)
  assert.equal(none.offsetXmm, 0)
  assert.equal(none.originCol, 0)
})

// Regression pin: map_offset shifts the DIE GRID, not the wafer. A point's
// position from the wafer centre must not move, or radius/sector would drift.
test('stagePosMm is measured from the wafer centre, unaffected by map_offset', () => {
  const g = parseWaferGeometry(info({ map_offset: '3000000,4610000' }))
  assert.deepEqual(stagePosMm('160000000,170000000', g), [10, 20])
})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npm --prefix front-dev-home test 2>&1 | grep -A3 "map_offset"`
Expected: FAIL — `offsetXmm` is `undefined`, so `assert.equal(g.offsetXmm, 0)` fails on the blank case and `originCol` is `undefined`.

- [ ] **Step 3: Extend the interface and parser**

In `front-dev-home/app/utils/waferGeometry.ts`, replace the `WaferGeometry` interface and `parseWaferGeometry` with:

```ts
export interface WaferGeometry {
  sizeMm: number // wafer diameter (mm)
  radiusMm: number // wafer_size / 2
  centerNm: number // nm coordinate of the wafer centre (corner origin)
  pitchXmm: number // die pitch x (mm); 0 when unknown
  pitchYmm: number // die pitch y (mm); 0 when unknown
  // Die-grid offset (mm) from map_offset: the die array is shifted this far off
  // the wafer centre. Applies to DIE-INDEXED geometry only (die centres, grid
  // boundaries, die-index labels) — never to stagePosMm, whose origin is the
  // physical wafer centre that centre→edge effects reference.
  offsetXmm: number
  offsetYmm: number
  // map_origin — the ARRAY index of the origin die. chip_number is already
  // expressed relative to it, so this is informational and never enters the
  // placement math. Exposed so the office can verify the assumption.
  originCol: number
  originRow: number
}

// "x,y" pair of numbers; each component falls back to 0 when absent/unparseable
// so a missing geometry field degrades to "no offset" rather than NaN.
const pairNm = (raw: string | undefined): [number, number] => {
  const [a, b] = (raw ?? '').split(',')
  const x = num(a)
  const y = num(b)
  return [Number.isFinite(x) ? x : 0, Number.isFinite(y) ? y : 0]
}

export const parseWaferGeometry = (info?: ExeDetailInfo | null): WaferGeometry => {
  const sizeRaw = num(info?.wafer_size)
  const sizeMm = sizeRaw > 0 ? sizeToMm(sizeRaw) : 300
  const [px, py] = (info?.chip_pitch ?? '').split(',')
  const pxNm = num(px)
  const pyNm = num(py)
  const [offXnm, offYnm] = pairNm(info?.map_offset)
  const [originCol, originRow] = pairNm(info?.map_origin)
  return {
    sizeMm,
    radiusMm: sizeMm / 2,
    centerNm: (sizeMm / 2) * NM_PER_MM,
    pitchXmm: pxNm > 0 ? pxNm / NM_PER_MM : 0,
    pitchYmm: pyNm > 0 ? pyNm / NM_PER_MM : 0,
    offsetXmm: offXnm / NM_PER_MM,
    offsetYmm: offYnm / NM_PER_MM,
    originCol,
    originRow
  }
}
```

- [ ] **Step 4: Update the two literal fixtures**

`front-dev-home/app/utils/waferPoints.test.ts` line 9 — replace with:

```ts
const geo: WaferGeometry = {
  sizeMm: 300, radiusMm: 150, centerNm: 150_000_000, pitchXmm: 1, pitchYmm: 1,
  offsetXmm: 0, offsetYmm: 0, originCol: 0, originRow: 0
}
```

`front-dev-home/app/utils/waferDieGrid.test.ts` lines 6-12 — replace with:

```ts
const geo = (pitchXmm: number, pitchYmm: number, offsetXmm = 0, offsetYmm = 0): WaferGeometry => ({
  sizeMm: 300,
  radiusMm: 150,
  centerNm: 150_000_000,
  pitchXmm,
  pitchYmm,
  offsetXmm,
  offsetYmm,
  originCol: 0,
  originRow: 0
})
```

- [ ] **Step 5: Run the full frontend suite**

Run: `npm --prefix front-dev-home test 2>&1 | tail -15`
Expected: PASS — all tests, including the pre-existing `dieCenterMm` / `stagePosMm` / `waferPoints` ones (their fixtures use a zero offset, so behaviour is unchanged).

- [ ] **Step 6: Commit**

```bash
git add front-dev-home/app/utils/waferGeometry.ts front-dev-home/app/utils/waferGeometry.test.ts front-dev-home/app/utils/waferPoints.test.ts front-dev-home/app/utils/waferDieGrid.test.ts
git commit -m "feat(wafer-geometry): parse map_offset and map_origin

map_offset is the die-grid offset (nm) and was parsed nowhere. Expose it as
offsetXmm/offsetYmm plus informational originCol/originRow. stagePosMm is
deliberately unchanged and pinned by a regression test: the offset shifts the
die grid, not the wafer centre that radius/sector reference."
```

---

### Task 2: `dieCenterMm` places die centres on the shifted grid

**Files:**

- Modify: `front-dev-home/app/utils/waferGeometry.ts:65-66` (`dieCenterMm`)
- Test: `front-dev-home/app/utils/waferGeometry.test.ts`

**Interfaces:**

- Consumes: `WaferGeometry.offsetXmm` / `offsetYmm` from Task 1.
- Produces: `dieCenterMm(col, row, geo): [number, number]` — unchanged signature, now offset-aware. `waferPoints.ts:81` (Die-mode tiles) picks this up automatically.

- [ ] **Step 1: Write the failing test**

Append to `front-dev-home/app/utils/waferGeometry.test.ts`:

```ts
test('dieCenterMm shifts die centres by the die-grid offset', () => {
  const g = parseWaferGeometry(info({ map_offset: '0,4610000' }))
  const [x, y] = dieCenterMm(2, -3, g)
  assert.ok(Math.abs(x - 2 * g.pitchXmm) < 1e-9) // offsetXmm is 0 here
  assert.ok(Math.abs(y - (4.61 + -3 * g.pitchYmm)) < 1e-9)
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm --prefix front-dev-home test 2>&1 | grep -A5 "shifts die centres"`
Expected: FAIL — y comes back as `-3 * pitchYmm` (no offset applied), so it differs from expected by 4.61.

- [ ] **Step 3: Apply the offset**

In `front-dev-home/app/utils/waferGeometry.ts`, replace `dieCenterMm`:

```ts
// Die centre (mm, relative to the WAFER centre) from a chip_number "(col,row)".
// The die array is shifted off the wafer centre by map_offset, so a die centre
// is offset + col·pitch — this is what makes die tiles land on the measured
// points instead of sitting map_offset away from them.
export const dieCenterMm = (col: number, row: number, geo: WaferGeometry): [number, number] =>
  [geo.offsetXmm + col * geo.pitchXmm, geo.offsetYmm + row * geo.pitchYmm]
```

- [ ] **Step 4: Run the full frontend suite**

Run: `npm --prefix front-dev-home test 2>&1 | tail -15`
Expected: PASS — the existing `dieCenterMm places die (col,row) on the pitch grid` test uses `map_offset: '0,0'`, so it still holds.

- [ ] **Step 5: Commit**

```bash
git add front-dev-home/app/utils/waferGeometry.ts front-dev-home/app/utils/waferGeometry.test.ts
git commit -m "feat(wafer-geometry): place die centres on the map_offset-shifted grid"
```

---

### Task 3: `mmToDieIndex` offset-aware + `waferAxis` passes it

**Files:**

- Modify: `front-dev-home/app/utils/waferGeometry.ts:76-77` (`mmToDieIndex`)
- Modify: `front-dev-home/app/utils/waferAxis.ts:22-27,49` (signature + call)
- Test: `front-dev-home/app/utils/waferGeometry.test.ts`

**Interfaces:**

- Consumes: `WaferGeometry.offsetXmm` / `offsetYmm` from Task 1.
- Produces: `mmToDieIndex(mm, pitchMm, offsetMm?)` — third parameter defaults to `0`, so existing callers keep compiling. `buildWaferAxis(grid, axisMax, pitchMm, color, offsetMm?)` — fifth parameter defaults to `0`.

- [ ] **Step 1: Write the failing test**

Append to `front-dev-home/app/utils/waferGeometry.test.ts`:

```ts
test('mmToDieIndex accounts for the die-grid offset', () => {
  const pitch = 6.818182
  assert.equal(mmToDieIndex(4.61, pitch, 4.61), 0)
  assert.equal(mmToDieIndex(4.61 + pitch, pitch, 4.61), 1)
  assert.equal(mmToDieIndex(4.61 - 2 * pitch, pitch, 4.61), -2)
})

test('mmToDieIndex offset defaults to zero for existing callers', () => {
  assert.equal(mmToDieIndex(6.9, 6.818182), 1)
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm --prefix front-dev-home test 2>&1 | grep -A5 "accounts for the die-grid offset"`
Expected: FAIL — the third argument is ignored, so `mmToDieIndex(4.61, 6.818182, 4.61)` returns `1`, not `0`.

- [ ] **Step 3: Add the offset parameter**

In `front-dev-home/app/utils/waferGeometry.ts`, replace `mmToDieIndex`:

```ts
// Convert a physical mm coordinate to its die-grid index (col or row). The grid
// is shifted by map_offset, so the offset is removed before dividing by pitch.
// Returns null when the pitch is unknown so callers can fall back to mm labels —
// never guess die 0.
export const mmToDieIndex = (mm: number, pitchMm: number, offsetMm = 0): number | null =>
  pitchMm > 0 ? Math.round((mm - offsetMm) / pitchMm) : null
```

- [ ] **Step 4: Pass the offset from the axis builder**

In `front-dev-home/app/utils/waferAxis.ts`, change the signature (lines 22-27) to add a fifth parameter:

```ts
export const buildWaferAxis = (
  grid: boolean,
  axisMax: number,
  pitchMm: number,
  color: string,
  offsetMm = 0
): WaferAxisConfig => {
```

and the formatter call (line 49):

```ts
        const i = mmToDieIndex(v, pitchMm, offsetMm)
```

- [ ] **Step 5: Run the full frontend suite**

Run: `npm --prefix front-dev-home test 2>&1 | tail -15`
Expected: PASS — `waferAxis.test.ts` calls `buildWaferAxis` with four arguments and the new one defaults to `0`.

- [ ] **Step 6: Commit**

```bash
git add front-dev-home/app/utils/waferGeometry.ts front-dev-home/app/utils/waferGeometry.test.ts front-dev-home/app/utils/waferAxis.ts
git commit -m "feat(wafer-geometry): make die-index conversion map_offset-aware"
```

---

### Task 4: `snapToDieCell` — recover a die cell from a stage coordinate

**Files:**

- Modify: `front-dev-home/app/utils/waferGeometry.ts` (append after `mmToDieIndex`)
- Test: `front-dev-home/app/utils/waferGeometry.test.ts`

**Interfaces:**

- Consumes: `stagePosMm`, `dieCenterMm`, `WaferGeometry` offsets.
- Produces: `snapToDieCell(stage: string, geo: WaferGeometry): string | null` returning `"col,row"` (matching the `chip_number` format) or `null`. **Spec 2's Position pairing key calls this** — keep the name and return shape stable.

- [ ] **Step 1: Write the failing tests**

Append to `front-dev-home/app/utils/waferGeometry.test.ts` (add `snapToDieCell` to the import on line 4):

```ts
// A stage_coordinate string (corner-origin nm) for a point at (xMm, yMm) from
// the wafer centre — the inverse of stagePosMm, used to build round-trip cases.
const stageAt = (xMm: number, yMm: number, g: ReturnType<typeof parseWaferGeometry>): string =>
  `${xMm * 1_000_000 + g.centerNm},${yMm * 1_000_000 + g.centerNm}`

test('snapToDieCell round-trips a die centre plus sub-half-pitch jitter', () => {
  const g = parseWaferGeometry(info({ map_offset: '0,4610000' }))
  const [cx, cy] = dieCenterMm(3, -4, g)
  // Measured points sit within their die: the mock jitters up to 0.3·pitch.
  assert.equal(snapToDieCell(stageAt(cx + 0.3 * g.pitchXmm, cy - 0.3 * g.pitchYmm, g), g), '3,-4')
  assert.equal(snapToDieCell(stageAt(cx, cy, g), g), '3,-4')
})

test('snapToDieCell ignoring the offset would land on the wrong die', () => {
  // Guard the offset actually participates: a die centre one full pitch of
  // offset away must not snap to the unshifted cell.
  const g = parseWaferGeometry(info({ map_offset: '0,5769231' })) // = 1·pitchY
  const [cx, cy] = dieCenterMm(0, 0, g)
  assert.equal(snapToDieCell(stageAt(cx, cy, g), g), '0,0')
})

test('snapToDieCell returns null without a pitch or on a bad coordinate', () => {
  assert.equal(snapToDieCell('160000000,170000000', parseWaferGeometry(info({ chip_pitch: '' }))), null)
  assert.equal(snapToDieCell('nope', parseWaferGeometry(info())), null)
  assert.equal(snapToDieCell('1,2,3', parseWaferGeometry(info())), null)
})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npm --prefix front-dev-home test 2>&1 | grep -A5 "snapToDieCell"`
Expected: FAIL with a `TypeError` / "snapToDieCell is not a function" — it does not exist yet.

- [ ] **Step 3: Implement `snapToDieCell`**

Append to `front-dev-home/app/utils/waferGeometry.ts`:

```ts
// The die cell "(col,row)" a physical stage_coordinate falls in — the inverse of
// dieCenterMm. A measured point sits inside its die (offset < 0.5·pitch), so
// rounding recovers the die exactly. Format matches chip_number so the two are
// directly comparable.
//
// Returns null when the pitch is unknown or the coordinate is unparseable. The
// caller MUST treat null as "cannot place this point" — never as die (0,0),
// which would silently pile unplaceable points onto the wafer centre.
export const snapToDieCell = (stage: string, geo: WaferGeometry): string | null => {
  if (!(geo.pitchXmm > 0) || !(geo.pitchYmm > 0)) return null
  const pos = stagePosMm(stage, geo)
  if (!pos) return null
  const col = Math.round((pos[0] - geo.offsetXmm) / geo.pitchXmm)
  const row = Math.round((pos[1] - geo.offsetYmm) / geo.pitchYmm)
  return `${col},${row}`
}
```

- [ ] **Step 4: Run the full frontend suite**

Run: `npm --prefix front-dev-home test 2>&1 | tail -15`
Expected: PASS — all tests including the three new `snapToDieCell` cases.

- [ ] **Step 5: Commit**

```bash
git add front-dev-home/app/utils/waferGeometry.ts front-dev-home/app/utils/waferGeometry.test.ts
git commit -m "feat(wafer-geometry): add snapToDieCell, the stage→die-cell inverse

Recovers chip_number-formatted (col,row) from a physical stage_coordinate via
map_offset + pitch. Null when unplaceable — callers must never treat that as
die (0,0). Spec 2's Position pairing key builds on this."
```

---

### Task 5: Align the die-grid overlay with the measured points

This is the visible display fix: boundary lines currently sit at `(k+0.5)·pitch` from the wafer centre while points sit at `map_offset + col·pitch`.

**Files:**

- Modify: `front-dev-home/app/utils/waferDieGrid.ts:22-45`
- Test: `front-dev-home/app/utils/waferDieGrid.test.ts`

**Interfaces:**

- Consumes: `WaferGeometry.offsetXmm` / `offsetYmm` from Task 1; the `geo(...)` test factory from Task 1 Step 4 (now accepts optional offsets).
- Produces: `buildDieGridSegments(geo, radiusMm)` and `dieGridLineData(geo, radiusMm)` — signatures unchanged, output shifted by the offset.

- [ ] **Step 1: Write the failing tests**

Append to `front-dev-home/app/utils/waferDieGrid.test.ts`:

```ts
test('die boundaries shift with the die-grid offset', () => {
  // Pitch 10, offset 2 → die centres at 2 + k·10, boundaries at 7, -3, 17, …
  const segments = buildDieGridSegments(geo(10, 10, 2, 0), 150)
  const xs = segments.filter(([a, b]) => a[0] === b[0]).map(([a]) => a[0])
  assert.ok(xs.includes(7))
  assert.ok(xs.includes(-3))
  assert.ok(!xs.includes(5)) // the unshifted boundary must be gone
})

test('a zero offset reproduces the unshifted grid', () => {
  const shifted = buildDieGridSegments(geo(10, 10, 0, 0), 150)
  const xs = shifted.filter(([a, b]) => a[0] === b[0]).map(([a]) => a[0])
  assert.ok(xs.includes(5))
  assert.ok(xs.includes(-5))
})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npm --prefix front-dev-home test 2>&1 | grep -A5 "boundaries shift"`
Expected: FAIL — `xs` still contains `5` and not `7`, because the offset is ignored.

- [ ] **Step 3: Thread the offset through `boundaries`**

In `front-dev-home/app/utils/waferDieGrid.ts`, replace `boundaries` and `buildDieGridSegments`:

```ts
// Boundary coordinates offset + (k + 0.5)·pitch strictly inside (−radius, radius).
// The die array is shifted off the wafer centre by map_offset, so boundaries are
// measured from the shifted grid — otherwise the lines sit map_offset away from
// the points they are supposed to enclose.
const boundaries = (pitch: number, radius: number, offset: number): number[] => {
  if (!(pitch > 0) || !(radius > 0)) return []
  if (radius / pitch > MAX_LINES_PER_AXIS) return []
  const out: number[] = []
  const kMax = Math.ceil(radius / pitch) + 1
  for (let k = -kMax - 1; k <= kMax; k++) {
    const c = offset + (k + 0.5) * pitch
    if (Math.abs(c) < radius) out.push(c)
  }
  return out
}

export const buildDieGridSegments = (geo: WaferGeometry, radiusMm: number): DieGridSegment[] => {
  const segments: DieGridSegment[] = []
  for (const x of boundaries(geo.pitchXmm, radiusMm, geo.offsetXmm)) {
    const chord = Math.sqrt(radiusMm * radiusMm - x * x)
    segments.push([[round3(x), round3(-chord)], [round3(x), round3(chord)]])
  }
  for (const y of boundaries(geo.pitchYmm, radiusMm, geo.offsetYmm)) {
    const chord = Math.sqrt(radiusMm * radiusMm - y * y)
    segments.push([[round3(-chord), round3(y)], [round3(chord), round3(y)]])
  }
  return segments
}
```

Note the `kMax` gains `+ 1` so a positive offset cannot clip the outermost boundary line off the grid.

- [ ] **Step 4: Update the header comment**

In `front-dev-home/app/utils/waferDieGrid.ts`, replace lines 4-6 of the header comment:

```ts
// die centres sit on the offset die grid (chip_number (col,row) ↔
// map_offset + col·pitch from the wafer centre — see waferGeometry.dieCenterMm).
// Die BOUNDARIES therefore run at map_offset + (k + 0.5)·pitch.
```

- [ ] **Step 5: Run the full frontend suite**

Run: `npm --prefix front-dev-home test 2>&1 | tail -15`
Expected: PASS — including the pre-existing `boundaries sit on half-pitch offsets` and `every segment is a chord` tests (zero offset).

- [ ] **Step 6: Commit**

```bash
git add front-dev-home/app/utils/waferDieGrid.ts front-dev-home/app/utils/waferDieGrid.test.ts
git commit -m "fix(wafer-map): align the die grid with the measured points

Boundaries were drawn at (k+0.5)*pitch from the wafer centre while points sit at
map_offset + col*pitch, so the grid was misaligned by exactly map_offset."
```

---

### Task 6: Make the mock's `map_offset` coherent

The mock emits `map_offset` as random noise that its own `stage_coordinate` does not encode. Make one seeded value the single source for both.

**Files:**

- Modify: `back_dev_home/msr_file/providers/mock.py:221-241` (`WaferGeom`, `_wafer_geometry`, `_die_center_nm`)
- Modify: `back_dev_home/msr_file/providers/mock.py:344-374` (`_exe_detail_info`)

**Interfaces:**

- Consumes: nothing from earlier tasks (backend-only).
- Produces: `WaferGeom` gains `offset_x_nm: int`, `offset_y_nm: int`. `exe_detail_info.map_offset` now equals those values, and `stage_coordinate` encodes them. Task 7 asserts the round-trip.

- [ ] **Step 1: Add the offset to `WaferGeom` and `_wafer_geometry`**

In `back_dev_home/msr_file/providers/mock.py`, replace the `WaferGeom` class and `_wafer_geometry`:

```python
class WaferGeom(NamedTuple):
    cols: int
    rows: int
    pitch_x_nm: int
    pitch_y_nm: int
    # Die-grid offset (nm). The SINGLE source for both the stage_coordinate this
    # module generates and the map_offset it reports, so the two can never
    # disagree — the bug this replaces was a random map_offset that nothing
    # encoded, which only looked fine because nothing read it.
    offset_x_nm: int
    offset_y_nm: int


@lru_cache(maxsize=256)
def _wafer_geometry(msr: str) -> WaferGeom:
    """Per-MSR die array, pitch and die-grid offset. Pitch = wafer diameter /
    array count, so the array physically spans the wafer and stage coordinates
    land inside it. The offset is kept under 0.3·pitch: a real, visible shift
    that still never pushes a die off the wafer."""
    rng = random.Random(_seed(msr, 313))
    cols, rows_n = rng.randint(38, 46), rng.randint(52, 62)
    pitch_x, pitch_y = round(_WAFER_NM / cols), round(_WAFER_NM / rows_n)
    offset_x = round(rng.uniform(-0.3, 0.3) * pitch_x)
    offset_y = round(rng.uniform(-0.3, 0.3) * pitch_y)
    return WaferGeom(cols, rows_n, pitch_x, pitch_y, offset_x, offset_y)


def _die_center_nm(col: int, row: int, geom: WaferGeom) -> tuple[float, float]:
    """Physical centre (nm, corner origin) of die (col, row), on the die grid
    shifted off the wafer centre by the map_offset this MSR reports."""
    return (
        _WAFER_CENTER_NM + geom.offset_x_nm + col * geom.pitch_x_nm,
        _WAFER_CENTER_NM + geom.offset_y_nm + row * geom.pitch_y_nm,
    )
```

- [ ] **Step 2: Emit the same offset from `_exe_detail_info`**

In `_exe_detail_info` (line 344), delete the now-unused `rng` line — after this change `map_offset` was its only consumer (`recipe_name`, `lot_id` and `wafer_id` all come from `parent` or `_seed`):

```python
    rng = random.Random(_seed(msr, 313))
```

and replace the `map_offset` field:

```python
        # map_offset is the die-grid offset actually encoded in stage_coordinate
        # (see _die_center_nm) — read from the shared geometry so the reported
        # value and the generated coordinates cannot drift apart.
        map_offset=f"{geom.offset_x_nm},{geom.offset_y_nm}",
```

- [ ] **Step 3: Verify the mock still builds a payload**

Run:

```bash
.venv/bin/python -c "
from back_dev_home.msr_file.providers import mock
d = mock.get_msr_file('MSR-CONTRACT-0001', 'ADI', 40)
e = d['exe_detail_info']
print('map_offset', e['map_offset'], 'pitch', e['chip_pitch'])
r = [x for x in d['rows'] if x['cd_value'] is not None][0]
print('chip_number', r['chip_number'], 'stage', r['stage_coordinate'])
"
```

Expected: `map_offset` prints two non-zero integers whose magnitudes are below 0.3 × the corresponding `chip_pitch` component, and a sample row prints a `chip_number` / `stage_coordinate` pair.

`get_msr_file(msr, class_name=None, total_images=None)` returns an `MsrFileResponse` TypedDict (plain dict access) or `None` when the MSR is unknown.

- [ ] **Step 4: Run the backend suite**

Run: `.venv/bin/python -m pytest back_dev_home/msr_file -q 2>&1 | tail -15`
Expected: PASS. If a test pins a literal `stage_coordinate` or `map_offset`, update it to derive the value from `mock._wafer_geometry(msr)` rather than hard-coding.

- [ ] **Step 5: Commit**

```bash
git add back_dev_home/msr_file/providers/mock.py
git commit -m "fix(msr_file/mock): make map_offset coherent with stage_coordinate

map_offset was random noise that _die_center_nm never applied, so the field only
looked correct because nothing read it. Move the offset into WaferGeom so the
generated stage_coordinate and the reported map_offset come from one seeded
source, and the geometry round-trips."
```

---

### Task 7: Pin the mock round-trip and verify visually

**Files:**

- Create: `back_dev_home/msr_file/tests/test_wafer_geometry_roundtrip.py`

**Interfaces:**

- Consumes: `mock._wafer_geometry`, `mock.get_msr_file` (Task 6); mirrors the `snapToDieCell` math from Task 4.
- Produces: the Phase-1 proof that `snap(stage_coordinate) == chip_number`.

- [ ] **Step 1: Write the failing test**

Create `back_dev_home/msr_file/tests/test_wafer_geometry_roundtrip.py`:

```python
"""Phase-1 proof that the mock's wafer geometry is self-consistent.

Every measured row's stage_coordinate must snap back to the chip_number the mock
assigned it, using ONLY the geometry the payload reports (chip_pitch, wafer_size,
map_offset). This is the mock-side mirror of waferGeometry.snapToDieCell, and it
is what makes Spec 2's Position pairing key trustworthy offline: if map_offset
were reported but not encoded (the bug this pins), the snap would land on the
wrong die for points near a die edge.

Run from repo root:  .venv/bin/python -m pytest back_dev_home/msr_file
"""

from back_dev_home.msr_file.providers import mock

_MSR = "MSR-CONTRACT-0001"
_CLASS = "ADI"
_TOTAL_IMAGES = 40


def _snap(stage: str, center_nm: float, pitch: tuple[int, int], offset: tuple[int, int]) -> str:
    """Mirror of utils/waferGeometry.ts snapToDieCell, in nm."""
    sx, sy = (float(v) for v in stage.split(","))
    col = round((sx - center_nm - offset[0]) / pitch[0])
    row = round((sy - center_nm - offset[1]) / pitch[1])
    return f"{col},{row}"


def test_stage_coordinate_snaps_back_to_chip_number():
    payload = mock.get_msr_file(_MSR, _CLASS, _TOTAL_IMAGES)
    info = payload["exe_detail_info"]

    wafer_nm = float(info["wafer_size"])
    center_nm = wafer_nm / 2
    pitch = tuple(int(v) for v in info["chip_pitch"].split(","))
    offset = tuple(int(v) for v in info["map_offset"].split(","))

    measured = [r for r in payload["rows"] if r["cd_value"] is not None]
    assert measured, "fixture must contain measured rows"

    for row in measured:
        assert _snap(row["stage_coordinate"], center_nm, pitch, offset) == row["chip_number"]


def test_map_offset_is_the_offset_actually_encoded():
    """The reported map_offset must equal the shared geometry's offset — the
    regression guard against reintroducing a decorative random value."""
    payload = mock.get_msr_file(_MSR, _CLASS, _TOTAL_IMAGES)
    geom = mock._wafer_geometry(_MSR)
    assert payload["exe_detail_info"]["map_offset"] == f"{geom.offset_x_nm},{geom.offset_y_nm}"
```

- [ ] **Step 2: Run it against the pre-Task-6 behaviour to confirm it would have caught the bug**

Run:

```bash
git stash push back_dev_home/msr_file/providers/mock.py 2>/dev/null || true
.venv/bin/python -m pytest back_dev_home/msr_file/tests/test_wafer_geometry_roundtrip.py -q 2>&1 | tail -8
git stash pop 2>/dev/null || true
```

Expected: FAIL while the old mock is restored (the reported offset is not encoded, so `_snap` lands on the wrong die for points near a die edge, and the second test fails outright). If the stash is empty because Task 6 is already committed, skip this step — it is a confidence check, not a gate.

- [ ] **Step 3: Run the test against the fixed mock**

Run: `.venv/bin/python -m pytest back_dev_home/msr_file -q 2>&1 | tail -10`
Expected: PASS — all msr_file tests including both new ones.

- [ ] **Step 4: Verify the sign convention visually**

The spec requires the offset's sign/axis convention be confirmed against the rendered map, not derived on paper.

Start the app (see the `verify` skill for the project recipe — Flask mock on `:5050`, Nuxt with `NUXT_API_TARGET=http://localhost:5050`), open a Skewvoir measurement, and on the wafer map turn the **die grid** on.

Confirm: **every measured point sits inside a die cell**, not straddling a boundary line, and the grid as a whole is visibly shifted off-centre by a fraction of a die.

If points straddle boundaries, the sign is inverted — flip it in ONE place, `parseWaferGeometry` (negate `offsetXmm`/`offsetYmm`), re-run `npm --prefix front-dev-home test` and the pytest round-trip, and re-check. Do not patch the sign in individual consumers.

Screenshot to `.playwright-mcp/screenshots/wafer-die-grid-map-offset.png`.

- [ ] **Step 5: Commit**

```bash
git add back_dev_home/msr_file/tests/test_wafer_geometry_roundtrip.py
git commit -m "test(msr_file): pin the stage_coordinate → chip_number round-trip

Proves the mock's reported map_offset is the one actually encoded in
stage_coordinate, which is what makes Spec 2's Position pairing key trustworthy
in Phase 1."
```

---

## Done criteria

- `npm --prefix front-dev-home test` passes.
- `.venv/bin/python -m pytest back_dev_home/msr_file` passes.
- The wafer map's die grid visually encloses the measured points, with the sign convention confirmed on screen.
- `snapToDieCell` is exported from `utils/waferGeometry.ts` and ready for Spec 2.
- `stagePosMm` is unchanged, pinned by the Task 1 regression test.
