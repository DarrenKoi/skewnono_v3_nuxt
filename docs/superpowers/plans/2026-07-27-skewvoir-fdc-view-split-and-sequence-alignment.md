# Skewvoir FDC 분석 View Split and Sequence Alignment — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split the Skewvoir `time-series` view into a single-MSR **FDC 분석** view and a multi-MSR **Time-Series** view, and scope the FDC sequence axis to the active parameter's own measurement rows instead of the whole MSR.

**Architecture:** The axis defect is fixed at its single source — `analyzeSequence` in `utils/skewvoirAnalysis/sequence.ts` — because every FDC pane and the sparkline matrix read `model.sequences` from it rather than deriving their own axis. A `fdcaxis` URL param opts back into the old whole-MSR axis. The mock is corrected so `sequence` is a global per-row counter, which both satisfies the office invariant and makes the defect reproducible at home.

**Tech Stack:** Nuxt 4 + NuxtUI, Vue 3 `<script setup>`, ECharts 6, `node --test` for frontend pure logic, pytest for the Flask mock backend.

## Global Constraints

- **Invariant:** `len(rows) == len(dynamic_fdc)`, always. One row is one measurement, one measurement has one sequence number, `dynamic_fdc` holds that sequence's tool state. A mismatch is a data fault to report, never to silently absorb.
- `sequence` is a **global running counter** over the whole MSR, unique per row; consecutive sequences belong to different parameters.
- **No time axis.** `sequence.ts` exposes no per-second rate and no time lag — every slope is per sequence step. `sequence.test.ts:135-160` enforces this by walking every key in the model; do not add a key matching `/(?:per)?second|timelag|time_lag|timestamp|elapsed/i`.
- Frontend pure-logic modules run under raw `node --test` — sibling imports carry an explicit `.ts` extension and every framework import is type-only.
- Colors come from `--sk-*` tokens only, never inline hex (`DESIGN.md`).
- Run `npm run lint:md` from the repo root after any Markdown edit.
- Markdown tables use markdownlint `MD060` `compact` style.
- Commit directly to `main`; no feature branch.

---

### Task 1: Scope the sequence axis to the active parameter

**Files:**

- Modify: `front-dev-home/app/utils/skewvoirAnalysis/types.ts`
- Modify: `front-dev-home/app/utils/skewvoirAnalysis/sequence.ts:79-99,146-231`
- Test: `front-dev-home/app/utils/skewvoirAnalysis/sequence.test.ts`

**Interfaces:**

- Consumes: nothing from earlier tasks.
- Produces:
  - `type SequenceAxisMode = 'param' | 'all'` exported from `types.ts`
  - `analyzeSequence(source: SequenceSource, parameter: string, unit: string, axisMode?: SequenceAxisMode): SequenceModel` — fourth argument defaults to `'param'`
  - `SequenceModel` gains `axisMode: SequenceAxisMode`, `excludedFdc: number`, `integrity: { rows: number, fdc: number, matched: boolean }`

- [ ] **Step 1: Write the failing tests**

Append to `front-dev-home/app/utils/skewvoirAnalysis/sequence.test.ts`. Note `SequenceSource` must be added to the existing import on line 6: `import { analyzeSequence, type SequenceSource } from './sequence.ts'`.

```ts
// ---------------------------------------------------------------------------
// Parameter-scoped axis
//
// `sequence` is a GLOBAL running counter over the whole MSR — one number per
// row, consecutive numbers belonging to DIFFERENT parameters. So selecting a
// parameter yields an interleaved subset, while dynamic_fdc holds an entry for
// every sequence. CD_TOP owns 1/3/5; SPACE owns 2/4/6.
// ---------------------------------------------------------------------------

const interleaved = (): SequenceSource => ({
  rows: [
    row({ sequence: 1, parameter: 'CD_TOP', cd_value: 100, chip_number: '0, 0' }),
    row({ sequence: 2, parameter: 'SPACE', cd_value: 50, chip_number: '0, 0' }),
    row({ sequence: 3, parameter: 'CD_TOP', cd_value: 104, chip_number: '1, 0' }),
    row({ sequence: 4, parameter: 'SPACE', cd_value: 52, chip_number: '1, 0' }),
    row({ sequence: 5, parameter: 'CD_TOP', cd_value: 108, chip_number: '2, 0' }),
    row({ sequence: 6, parameter: 'SPACE', cd_value: 54, chip_number: '2, 0' })
  ],
  dynamic_fdc: {
    1: { StigmaX: 10 }, 2: { StigmaX: 11 }, 3: { StigmaX: 12 },
    4: { StigmaX: 13 }, 5: { StigmaX: 14 }, 6: { StigmaX: 15 }
  },
  fdc_params: [fdcParam({})]
})

test('the axis is the ACTIVE PARAMETER rows only — not the union with dynamic_fdc', () => {
  const m = analyzeSequence(interleaved(), 'CD_TOP', 'nm')
  assert.deepEqual(m.sequences, [1, 3, 5])
  assert.equal(m.axisMode, 'param')
})

test('FDC is sampled at the active parameter sequences, dropping other parameters points', () => {
  const m = analyzeSequence(interleaved(), 'CD_TOP', 'nm')
  const s = m.fdc[0]!
  assert.deepEqual(s.points.map(p => p.sequence), [1, 3, 5])
  assert.deepEqual(s.points.map(p => p.value), [10, 12, 14])
  assert.equal(m.excludedFdc, 3)
})

test('FDC stats are computed over the SCOPED sample, not the whole MSR', () => {
  const m = analyzeSequence(interleaved(), 'CD_TOP', 'nm')
  const s = m.fdc[0]!.stats
  assert.equal(s.start, 10)
  assert.equal(s.end, 14)
  assert.equal(s.range, 4)
  assert.equal(s.n, 3)
  // OLS of (1,10)(3,12)(5,14) = +1 per sequence step. What actually differs
  // from the unscoped axis here is start/end/range/n (10..15, n=6) — this
  // fixture's dynamic_fdc values are a perfect arithmetic progression across
  // all six sequences, so an evenly-spaced subsample preserves the same slope;
  // it does NOT preserve n, end, or range, which is the contamination this
  // task exists to correct.
  assert.ok(Math.abs(s.slope - 1) < 1e-9)
})

test('the SPACE parameter gets its own disjoint axis from the same source', () => {
  const m = analyzeSequence(interleaved(), 'SPACE', 'nm')
  assert.deepEqual(m.sequences, [2, 4, 6])
  assert.deepEqual(m.fdc[0]!.points.map(p => p.value), [11, 13, 15])
})

test('axisMode "all" restores the whole-MSR union axis', () => {
  const m = analyzeSequence(interleaved(), 'CD_TOP', 'nm', 'all')
  assert.deepEqual(m.sequences, [1, 2, 3, 4, 5, 6])
  assert.deepEqual(m.fdc[0]!.points.map(p => p.value), [10, 11, 12, 13, 14, 15])
  assert.equal(m.axisMode, 'all')
  assert.equal(m.excludedFdc, 0)
  // CD still only exists where the parameter was measured — honest gaps.
  assert.deepEqual(m.cd.points.map(p => p.sequence), [1, 3, 5])
})

test('a failure row keeps its place on the axis so its FDC stays readable', () => {
  const src = interleaved()
  src.rows.push(row({
    sequence: 7, parameter: 'CD_TOP', cd_value: null, mp_number: -1,
    no_of_mp_image: 0, mp_image_name_01: '', addressing1_score: null, addressing2_score: null
  }))
  src.dynamic_fdc[7] = { StigmaX: 99 }
  const m = analyzeSequence(src, 'CD_TOP', 'nm')
  assert.deepEqual(m.sequences, [1, 3, 5, 7])
  assert.deepEqual(m.cd.points.map(p => p.value), [100, 104, 108, null])
  assert.deepEqual(m.fdc[0]!.points.map(p => p.value), [10, 12, 14, 99])
})

// ---------------------------------------------------------------------------
// Data integrity: len(rows) === len(dynamic_fdc), always.
// ---------------------------------------------------------------------------

test('integrity reports rows and dynamic_fdc counts as matched when they agree', () => {
  const m = analyzeSequence(interleaved(), 'CD_TOP', 'nm')
  assert.deepEqual(m.integrity, { rows: 6, fdc: 6, matched: true })
})

test('integrity reports a mismatch when dynamic_fdc is short of the rows', () => {
  const src = interleaved()
  delete src.dynamic_fdc[4]
  const m = analyzeSequence(src, 'CD_TOP', 'nm')
  assert.deepEqual(m.integrity, { rows: 6, fdc: 5, matched: false })
  // The scoped axis is unaffected — the missing entry belonged to SPACE.
  assert.deepEqual(m.sequences, [1, 3, 5])
})
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd front-dev-home && npx tsx --test app/utils/skewvoirAnalysis/sequence.test.ts 2>&1 | tail -30`

Expected: FAIL. The first failure is `m.sequences` being `[1,2,3,4,5,6]` instead of `[1,3,5]`; `m.axisMode`, `m.excludedFdc` and `m.integrity` are `undefined`.

If `npx tsx` is unavailable, use the repo's own runner: `cd front-dev-home && npm test 2>&1 | tail -30` (runs `node --test` over `app/**/*.test.ts`).

- [ ] **Step 3: Add the axis-mode type**

In `front-dev-home/app/utils/skewvoirAnalysis/types.ts`, append:

```ts
/** Which rule produced the sequence axis of a single-MSR FDC model.
 *
 * `param` — the ACTIVE PARAMETER's own measurement rows. `sequence` is a global
 * running counter over the whole MSR, so a parameter owns an interleaved subset
 * of it; scoping to that subset is what keeps a CD point and the FDC point
 * beside it describing the SAME measurement.
 *
 * `all` — every sequence in the MSR, including other parameters' measurements.
 * Answers "what did the tool do BETWEEN my points", at the cost of a CD line
 * that is mostly gaps. */
export type SequenceAxisMode = 'param' | 'all'
```

- [ ] **Step 4: Scope the axis in `sequence.ts`**

In `front-dev-home/app/utils/skewvoirAnalysis/sequence.ts`:

Add to the imports (after line 32):

```ts
import type { SequenceAxisMode } from './types.ts'
```

Re-export it so consumers have one import surface, directly below that import:

```ts
export type { SequenceAxisMode } from './types.ts'
```

Add to the public types, above `SequenceModel`:

```ts
/** The §Invariant check: one row is one measurement and `dynamic_fdc` holds
 * that measurement's tool state, so the two counts must agree. Reported rather
 * than absorbed — a mismatch means the data is wrong, not that the axis should
 * quietly cope. */
export interface SequenceIntegrity {
  rows: number
  fdc: number
  matched: boolean
}
```

Add these three fields to the `SequenceModel` interface (after `siteBySequence`):

```ts
  /** Which rule produced `sequences`. */
  axisMode: SequenceAxisMode
  /** dynamic_fdc sequences that fell OFF the axis — other parameters'
   * measurements. Always 0 when axisMode is 'all'. */
  excludedFdc: number
  /** len(rows) vs len(dynamic_fdc). See SequenceIntegrity. */
  integrity: SequenceIntegrity
```

Change the signature (line 146-150) to:

```ts
export const analyzeSequence = (
  source: SequenceSource,
  parameter: string,
  unit: string,
  axisMode: SequenceAxisMode = 'param'
): SequenceModel => {
```

Replace the axis block (lines 171-175) with:

```ts
  // The shared cursor axis.
  //
  // 'param' — the ACTIVE PARAMETER's own rows, and nothing else. `sequence` is a
  // global counter over the whole MSR with consecutive numbers belonging to
  // DIFFERENT parameters, so the old union-with-dynamic_fdc axis plotted other
  // parameters' measurements in every FDC pane and computed each pane's stats
  // over the whole MSR under a parameter-scoped heading.
  // 'all' — the union, kept verbatim so the opt-out is a real comparison.
  const axis = new Set<number>()
  for (const r of cdRows) axis.add(r.sequence)
  if (axisMode === 'all') {
    for (const [seq] of fdcSeqEntries) axis.add(seq)
  }
  const sequences = [...axis].sort((a, b) => a - b)

  // FDC entries that fall off the axis belong to other parameters' measurements.
  const onAxis = fdcSeqEntries.filter(([seq]) => axis.has(seq))
  const excludedFdc = fdcSeqEntries.length - onAxis.length
```

Replace the `fdcKeys` block (lines 177-181) so a param present ONLY on off-axis sequences does not produce an all-null pane:

```ts
  // Which dynamic FDC params appear ON THE AXIS. Deriving this from every
  // sequence instead would render an all-null pane for a param that was only
  // sampled during another parameter's measurements.
  const fdcKeys = new Set<string>()
  for (const [, params] of onAxis) {
    for (const k of Object.keys(params)) fdcKeys.add(k)
  }
```

Change `fdcBySeq` (line 183) to build from the on-axis entries:

```ts
  const fdcBySeq = new Map(onAxis)
```

Add the integrity check immediately before the `return` (line 220):

```ts
  const fdcCount = Object.keys(source.dynamic_fdc).length
  const integrity: SequenceIntegrity = {
    rows: source.rows.length,
    fdc: fdcCount,
    matched: source.rows.length === fdcCount
  }
```

Add the three fields to the returned object (after `siteBySequence`):

```ts
    axisMode,
    excludedFdc,
    integrity
```

- [ ] **Step 5: Update the module doc**

Replace lines 14-17 of `sequence.ts` (the CD↔FDC coupling paragraph) with:

```ts
// AXIS: by default the sequence axis is the ACTIVE PARAMETER's own measurement
// rows. `sequence` is a global running counter over the whole MSR — one number
// per row, consecutive numbers belonging to DIFFERENT parameters — so a
// parameter owns an interleaved subset and `dynamic_fdc` always holds strictly
// more entries than the CD axis. Pass axisMode 'all' for the whole-MSR union.
//
// CD ↔ dynamic-FDC coupling is DEMO-ONLY: the home mock biases both by a single
// per-MSR `health` scalar (useMsrFileApi.ts), so any apparent correlation is not
// method-validated. That caveat is surfaced by the component (pane meta), not
// invented here; this module just aligns the two on a shared sequence axis.
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `cd front-dev-home && npm test 2>&1 | tail -20`

Expected: PASS, including the eight pre-existing `sequence.test.ts` cases. Those pass unchanged because their fixture has every row on one parameter with `dynamic_fdc` covering exactly those sequences — so the scoped axis and the old union axis coincide.

- [ ] **Step 7: Typecheck**

Run: `cd front-dev-home && npm run typecheck`
Expected: no errors.

- [ ] **Step 8: Commit**

```bash
git add front-dev-home/app/utils/skewvoirAnalysis/sequence.ts \
        front-dev-home/app/utils/skewvoirAnalysis/types.ts \
        front-dev-home/app/utils/skewvoirAnalysis/sequence.test.ts
git commit -m "fix(skewvoir): scope the FDC sequence axis to the active parameter

analyzeSequence built its axis as the union of the active parameter's CD
sequences and every sequence in dynamic_fdc. Since sequence is a global counter
with one number per row and consecutive numbers belonging to different
parameters, that union is always the whole MSR: every FDC pane plotted other
parameters' measurements, and each pane's start/end/range/slope were computed
over the whole MSR beneath a parameter-scoped heading.

The axis is now the active parameter's own rows. Failure rows keep their place —
the tool was at that point and dynamic_fdc recorded its state, so the CD gap
beside live FDC data is often the most diagnostic sequence on the chart.
axisMode 'all' restores the union verbatim.

Also reports integrity: len(rows) vs len(dynamic_fdc), which the office
guarantees to be equal."
```

---

### Task 2: Pin the sparkline matrix to the scoped axis

**Files:**

- Test: `front-dev-home/app/utils/skewvoirAnalysis/paramMatrix.test.ts`

**Interfaces:**

- Consumes: `analyzeSequence(source, parameter, unit, axisMode?)` and `SequenceModel.sequences` from Task 1.
- Produces: nothing — regression coverage only.

`paramMatrix.ts` needs **no source change**: `buildParamMatrix` takes `model.sequences` verbatim (`paramMatrix.ts:104`) and reads each FDC cell's values straight off `series.points` (`paramMatrix.ts:134`), so it inherits Task 1's axis. This task proves that rather than assuming it.

- [ ] **Step 1: Write the failing test**

Append to `front-dev-home/app/utils/skewvoirAnalysis/paramMatrix.test.ts`:

```ts
// ---------------------------------------------------------------------------
// The matrix inherits the scoped axis (Task 1). Before that fix the CD row was
// mostly null while every FDC row was dense, so the picture and the r badge
// printed beside it were computed on different samples.
// ---------------------------------------------------------------------------

const interleavedSource = (): SequenceSource => ({
  rows: [
    row({ sequence: 1, parameter: 'CD_TOP', cd_value: 100 }),
    row({ sequence: 2, parameter: 'SPACE', cd_value: 50 }),
    row({ sequence: 3, parameter: 'CD_TOP', cd_value: 104 }),
    row({ sequence: 4, parameter: 'SPACE', cd_value: 52 }),
    row({ sequence: 5, parameter: 'CD_TOP', cd_value: 108 }),
    row({ sequence: 6, parameter: 'SPACE', cd_value: 54 })
  ],
  dynamic_fdc: {
    1: { StigmaX: 10 }, 2: { StigmaX: 11 }, 3: { StigmaX: 12 },
    4: { StigmaX: 13 }, 5: { StigmaX: 14 }, 6: { StigmaX: 15 }
  },
  fdc_params: [fdcParam({})]
})

test('matrix cells span the active parameter axis, not the whole MSR', () => {
  const src = interleavedSource()
  const matrix = buildParamMatrix(analyzeSequence(src, 'CD_TOP', 'nm'), src)
  assert.deepEqual(matrix.sequences, [1, 3, 5])
  for (const r of matrix.rows) {
    for (const c of r.cells) {
      assert.equal(c.values.length, 3, `${c.param} has ${c.values.length} values for a 3-sequence axis`)
    }
  }
})

test('the CD row has no manufactured gaps once the axis is scoped', () => {
  const src = interleavedSource()
  const matrix = buildParamMatrix(analyzeSequence(src, 'CD_TOP', 'nm'), src)
  const cd = matrix.rows.find(r => r.kind === 'cd')!.cells[0]!
  assert.deepEqual(cd.values, [100, 104, 108])
})
```

- [ ] **Step 2: Run the tests**

Run: `cd front-dev-home && npm test 2>&1 | tail -20`
Expected: PASS (Task 1 already supplies the behavior). If the second test fails with nulls interleaved, Task 1's axis change did not land — go back and fix it there, not here.

- [ ] **Step 3: Commit**

```bash
git add front-dev-home/app/utils/skewvoirAnalysis/paramMatrix.test.ts
git commit -m "test(skewvoir): pin the sparkline matrix to the parameter-scoped axis

buildParamMatrix takes model.sequences verbatim, so it inherits the scoped axis
with no source change. These cases prove that rather than leaving it implied —
they fail loudly if the axis regresses to the whole-MSR union."
```

---

### Task 3: Make the mock emit one sequence per row

**Files:**

- Modify: `back_dev_home/msr_file/providers/mock.py:498-616`
- Test: `back_dev_home/msr_file/tests/test_contract.py`

**Interfaces:**

- Consumes: nothing from earlier tasks.
- Produces: mock responses satisfying `len(rows) == len(dynamic_fdc)`, with unique per-row `sequence` values.

The mock currently reuses one sequence number across every parameter row (`mock.py:528`, `mock.py:580`), which violates the invariant and makes Task 1's fix invisible at home.

- [ ] **Step 1: Write the failing tests**

Append to `back_dev_home/msr_file/tests/test_contract.py`:

```python
def test_sequence_is_unique_per_row():
    """`sequence` is a global running counter: one number per measurement."""
    result = mock.get_msr_file(_MSR, _CLASS, _TOTAL_IMAGES)
    assert result is not None
    sequences = [row["sequence"] for row in result["rows"]]
    assert len(sequences) == len(set(sequences)), "a sequence number is reused across rows"
    assert sequences == sorted(sequences), "rows are not in measurement order"


def test_row_count_matches_dynamic_fdc_count():
    """The office invariant: one row, one measurement, one dynamic_fdc entry."""
    result = mock.get_msr_file(_MSR, _CLASS, _TOTAL_IMAGES)
    assert result is not None
    assert len(result["rows"]) == len(result["dynamic_fdc"])


def test_dynamic_fdc_keys_are_exactly_the_row_sequences():
    result = mock.get_msr_file(_MSR, _CLASS, _TOTAL_IMAGES)
    assert result is not None
    assert {str(row["sequence"]) for row in result["rows"]} == set(result["dynamic_fdc"])


def test_parameters_measured_at_one_point_share_its_die():
    """Consecutive sequences at the same measurement point keep that point's
    chip/stage coordinates — only the parameter differs."""
    result = mock.get_msr_file(_MSR, _CLASS, _TOTAL_IMAGES)
    assert result is not None
    params = {row["parameter"] for row in result["rows"]}
    if len(params) < 2:
        return  # single-parameter MSR — nothing to pair up
    by_chip: dict[str, set[str]] = {}
    for row in result["rows"]:
        by_chip.setdefault(row["chip_number"], set()).add(row["parameter"])
    assert any(len(v) > 1 for v in by_chip.values()), \
        "no die carries more than one parameter — points are not shared"
```

Confirm the module already binds `mock`, `_MSR`, `_CLASS` and `_TOTAL_IMAGES`; if any is missing, mirror the existing `test_contract.py` call site (`mock.get_msr_file(_MSR, _CLASS, _TOTAL_IMAGES)`).

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest back_dev_home/msr_file/tests/test_contract.py -q 2>&1 | tail -20`

Expected: FAIL — `test_sequence_is_unique_per_row` reports reused numbers, and `test_row_count_matches_dynamic_fdc_count` reports `len(rows)` as a multiple of `len(dynamic_fdc)`.

- [ ] **Step 3: Clarify what `num_measurements` bounds**

`num_measurements` keeps its current formula. Only the comment changes — replace
lines 504-506 of `back_dev_home/msr_file/providers/mock.py`:

```python
    # STEP count, not measurement-point count: each step now emits one row (one
    # sequence) PER PARAMETER, so points are num_measurements * num_params.
    # Deliberately still bounded by total_images // 2 rather than that product —
    # dividing by num_params drops low-image MSRs (min total_images is 42) below
    # 20 steps, and the every-20th-step failure rule would then never fire, so
    # those MSRs would carry no null-cd_value rows at all.
    num_measurements = min(rng.randint(20, 80), max(1, total_images // 2))
```

Do **not** reorder `num_params` above `num_measurements` and do not divide by it.
The guard was already loose in the same direction — each row declares
`no_of_mp_image` of 1-5, so the images the rows claim already exceed
`total_images` today — and tightening it here costs failure-row coverage across
the app for no gain.

- [ ] **Step 4: Key the per-point fields on the step, and give each row its own sequence**

Still in `_build_rows`, replace the outlier pool at lines 518-526:

```python
    measured_steps = [s for s in range(1, num_measurements + 1) if s % 20 != 0]
    outliers_by_param: dict[str, dict[int, float]] = {}
    for p in selected_params:
        prng = random.Random(_seed(f"{msr}:{p}:outliers", 733))
        picks = prng.sample(measured_steps, min(prng.choice((0, 0, 1, 1, 2)), len(measured_steps)))
        outliers_by_param[p] = {
            s: (1.0 if prng.random() < 0.5 else -1.0) * abs(fields[p].mean) * prng.uniform(0.24, 0.40)
            for s in picks
        }
```

Replace the loop header at line 528-534 with a step loop plus a running sequence counter:

```python
    # A STEP is one measurement point (one die). Each parameter measured there is
    # its own measurement and takes the next global sequence number — so two
    # parameters at one point share chip/stage but never share a sequence.
    sequence = 0
    for step in range(1, num_measurements + 1):
        seq_frac = (step - 1) / span

        chip_x, chip_y = dies[(step - 1) % len(dies)]
```

Then, within the loop body, rename every remaining per-point use of `sequence` to `step`:

| Line (before) | Change |
| --- | --- |
| `empty = sequence % 20 == 0` | `empty = step % 20 == 0` |
| `mp_number = (sequence - 1) % 30` | `mp_number = (step - 1) % 30` |
| `meas_mag = _MAGNIFICATIONS[(sequence + seed) % len(_MAGNIFICATIONS)]` | `(step + seed)` |
| `meas_vac = _VOLTAGES[(sequence + seed) % len(_VOLTAGES)]` | `(step + seed)` |
| `meas_pixel = _PIXELS[(sequence + seed) % len(_PIXELS)]` | `(step + seed)` |
| `meas_kind = _MEAS_KINDS[(sequence + seed) % len(_MEAS_KINDS)]` | `(step + seed)` |
| `meas_method = _MEAS_METHODS[(sequence + seed) % len(_MEAS_METHODS)]` | `(step + seed)` |
| `object_type = _OBJECT_TYPES[(sequence + seed) % len(_OBJECT_TYPES)]` | `(step + seed)` |

Then in the parameter loop, allocate the sequence and switch the outlier lookup to `step`:

```python
        for parameter in selected_params:
            sequence += 1
            rows.append(MsrFileRow(
                msr=msr,
                sequence=sequence,
                ...
                cd_value=None if empty else _cd_value(
                    fields[parameter], radius_norm, health, seq_frac, rng,
                    outliers_by_param[parameter].get(step, 0.0),
                ),
```

Leave `mp_image_name_01`'s `{sequence:03d}` as-is — it now interpolates the per-row sequence, which makes image names unique per measurement rather than per step.

Also update the comment on the `empty` rule (line 550-552) to say the step fails as a whole:

```python
        # Every 20th STEP carries point METADATA but no point DATA (spec rule 9).
        # The whole point failed, so every parameter measured there fails with it.
```

- [ ] **Step 5: Update the collapse comment in `get_msr_file`**

Replace the comment at `mock.py:729-731`:

```python
    # One row is one measurement and each carries its own sequence, so this set
    # is simply every row — the office invariant len(rows) == len(dynamic_fdc).
    sequences = sorted({row["sequence"] for row in rows})
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest back_dev_home/msr_file -q 2>&1 | tail -20`
Expected: PASS.

- [ ] **Step 7: Run the full backend suite for regressions**

Run: `.venv/bin/python -m pytest -q 2>&1 | tail -20`
Expected: PASS (~1320 tests). Any failure here is a real dependency on the old cartesian shape — fix the dependant, not the invariant.

- [ ] **Step 8: Commit**

```bash
git add back_dev_home/msr_file/providers/mock.py back_dev_home/msr_file/tests/test_contract.py
git commit -m "fix(msr_file): give every mock row its own sequence number

The mock emitted a cartesian product — one sequence number reused across every
parameter row — so every parameter covered every sequence and a parameter-scoped
FDC axis was indistinguishable from the whole-MSR one. That both violated the
office invariant len(rows) == len(dynamic_fdc) and made the axis defect
unreproducible at home.

sequence is now a global counter incremented per row. A measurement point still
walks one die per step and parameters measured there keep that point's
chip/stage, but each takes the next sequence number. With 2-3 parameters
selected a parameter's CD axis becomes every 2nd or 3rd sequence, reproducing
the office interleave.

The total_images ceiling now bounds steps * num_params rather than steps, since
that product is the measurement-point count."
```

---

### Task 4: Warn on the invariant office-side

**Files:**

- Modify: `back_dev_home/msr_file/providers/office_example.py:361-407`
- Test: `back_dev_home/msr_file/tests/test_office_template.py`

**Interfaces:**

- Consumes: nothing from earlier tasks.
- Produces: a `logging.warning` from `build_response` when `len(rows) != len(dynamic_fdc)`.

- [ ] **Step 1: Write the failing test**

Append to `back_dev_home/msr_file/tests/test_office_template.py`:

```python
def test_mismatched_row_and_fdc_counts_warn_without_raising(caplog):
    """The office guarantees len(rows) == len(dynamic_fdc). A mismatch is a data
    fault worth naming in the log — but serving flagged data beats serving
    nothing, so it must not raise."""
    payload = {
        "df_result_data": [
            {"sequence": 1, "parameter": "CD_TOP", "cd_value": 10.0},
            {"sequence": 2, "parameter": "SPACE", "cd_value": 20.0},
        ],
        "dynamic_fdc": {"1": {"StigmaX": 0.1}},
        "exe_detail_info": {},
    }
    with caplog.at_level(logging.WARNING):
        response = office.build_response("MSR-X", {}, payload)
    assert response["total"] == 2
    assert len(response["dynamic_fdc"]) == 1
    assert any("2 rows" in r.message and "1 dynamic_fdc" in r.message for r in caplog.records)
```

Add `import logging` to the test module's imports if it is not already present.

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/bin/python -m pytest back_dev_home/msr_file/tests/test_office_template.py -q 2>&1 | tail -20`
Expected: FAIL — no warning record is emitted.

- [ ] **Step 3: Emit the warning**

In `back_dev_home/msr_file/providers/office_example.py`, ensure the module has a logger near its imports:

```python
import logging

_log = logging.getLogger(__name__)
```

Then in `build_response`, directly after `fixed_fdc, dynamic_fdc, fdc_params = _fdc(payload)` (line 382), insert:

```python
    # One row is one measurement and dynamic_fdc holds that measurement's tool
    # state, so the counts must agree. Warn rather than raise: a diagnosable data
    # fault should be named in the log, not turned into a 500 for the whole page.
    # The frontend surfaces the same mismatch as a badge (SequenceModel.integrity).
    if len(rows) != len(dynamic_fdc):
        _log.warning(
            "msr_file %s: %d rows but %d dynamic_fdc entries — "
            "expected one FDC entry per measurement row",
            msr, len(rows), len(dynamic_fdc),
        )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest back_dev_home/msr_file -q 2>&1 | tail -20`
Expected: PASS.

- [ ] **Step 5: Document the invariant in MIGRATION.md**

Append to `back_dev_home/msr_file/MIGRATION.md`, under the response-shape section:

```markdown
### Invariant: `len(rows) == len(dynamic_fdc)`

`sequence` is a global running counter over the whole MSR — one number per
measurement row — and `dynamic_fdc` is keyed by that sequence, holding the tool
state captured for it. The two counts must therefore agree.

`build_response` logs a warning when they do not; it does not raise, because
serving flagged data beats serving nothing. The frontend reports the same
mismatch as a badge on the FDC 분석 view (`SequenceModel.integrity`).

A mismatch means the pickle's `df_result_data` and `dynamic_fdc` disagree about
what was measured — investigate the post-processing pipeline, not the adapter.
```

Run `npm run lint:md` from the repo root.

- [ ] **Step 6: Commit**

```bash
git add back_dev_home/msr_file/providers/office_example.py \
        back_dev_home/msr_file/tests/test_office_template.py \
        back_dev_home/msr_file/MIGRATION.md
git commit -m "feat(msr_file): warn when rows and dynamic_fdc counts disagree

One row is one measurement and dynamic_fdc holds that measurement's tool state,
so the office guarantees the two counts are equal. build_response now names a
mismatch in the log instead of letting it pass silently into the UI, where it
would show up as unexplained gaps.

It warns rather than raises — a diagnosable data fault should be reported, not
turned into a 500 for the whole page. The frontend surfaces the same mismatch as
a badge via SequenceModel.integrity."
```

---

### Task 5: Carry the axis mode in the URL

**Files:**

- Modify: `front-dev-home/app/utils/skewvoirAnalysis/routeQuery.ts`
- Modify: `front-dev-home/app/composables/useSkewvoirRoute.ts:44-57,96-103,110-139`
- Modify: `front-dev-home/app/composables/useSkewvoirWorkspace.ts:59-96`
- Modify: `front-dev-home/app/composables/useSkewvoirAnalysis.ts` (return block)
- Test: `front-dev-home/app/utils/skewvoirAnalysis/routeQuery.test.ts`

**Interfaces:**

- Consumes: `SequenceAxisMode` from Task 1 (`utils/skewvoirAnalysis/types.ts`).
- Produces:
  - `parseFdcAxis(raw: unknown): SequenceAxisMode` in `routeQuery.ts`
  - `fdcAxis: ComputedRef<SequenceAxisMode>` and `setFdcAxis(mode: SequenceAxisMode): void` on `useSkewvoirRoute`, `useSkewvoirWorkspace`, and `useSkewvoirAnalysis`

- [ ] **Step 1: Write the failing test**

Append to `front-dev-home/app/utils/skewvoirAnalysis/routeQuery.test.ts`:

```ts
test('fdcaxis defaults to the parameter-scoped axis and accepts only known modes', () => {
  assert.equal(parseFdcAxis(undefined), 'param')
  assert.equal(parseFdcAxis(''), 'param')
  assert.equal(parseFdcAxis('param'), 'param')
  assert.equal(parseFdcAxis('all'), 'all')
  // A hand-edited link must not render an axis nobody implemented.
  assert.equal(parseFdcAxis('whole-msr'), 'param')
})

test('clearing fdcaxis drops it from the query rather than writing the default', () => {
  const next = applyQueryPatch({ view: 'fdc', fdcaxis: 'all' }, { fdcaxis: null })
  assert.deepEqual(next, { view: 'fdc' })
})
```

Add `parseFdcAxis` to the existing `routeQuery.ts` import in that test file.

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd front-dev-home && npm test 2>&1 | tail -20`
Expected: FAIL — `parseFdcAxis is not a function`.

- [ ] **Step 3: Add the parser**

In `front-dev-home/app/utils/skewvoirAnalysis/routeQuery.ts`, add to the type imports:

```ts
import type { AnalysisScope, SequenceAxisMode } from './types.ts'
```

(The file currently imports `AnalysisScope` alone — extend that line rather than adding a second import.)

Then add, directly below `parseScope`:

```ts
/** Which sequence axis the FDC 분석 panes use. Absent means the default
 *  parameter-scoped axis, so a plain analysis link stays free of the param;
 *  `all` opts into the whole-MSR union. An unrecognised value falls back to the
 *  default rather than rendering an axis nobody implemented. */
export const parseFdcAxis = (raw: unknown): SequenceAxisMode =>
  qstr(raw) === 'all' ? 'all' : 'param'
```

- [ ] **Step 4: Bind it to the router**

In `front-dev-home/app/composables/useSkewvoirRoute.ts`:

Extend the `routeQuery` import block with `parseFdcAxis`, and add the type import:

```ts
import type { AnalysisScope, SequenceAxisMode } from '~/utils/skewvoirAnalysis/types'
```

Add the computed after `grainParam` (line 51):

```ts
  // FDC 분석 sequence axis: 'param' (default, the active parameter's own rows)
  // or 'all' (the whole-MSR union). In the URL so the axis a screenshot was
  // taken on travels with the link.
  const fdcAxis = computed<SequenceAxisMode>(() => parseFdcAxis(route.query.fdcaxis))
```

Add the setter beside `setGrain` (line 101). Writing `null` for the default keeps a default screen's URL clean:

```ts
  const setFdcAxis = (mode: SequenceAxisMode) =>
    patchQuery({ fdcaxis: mode === 'all' ? 'all' : null })
```

Add `fdcAxis` and `setFdcAxis` to the returned object.

- [ ] **Step 5: Re-export through the workspace and analysis composables**

In `front-dev-home/app/composables/useSkewvoirWorkspace.ts`, add to the returned object beside `grainParam` / `setGrain`:

```ts
    fdcAxis: skRoute.fdcAxis,
    setFdcAxis: skRoute.setFdcAxis,
```

In `front-dev-home/app/composables/useSkewvoirAnalysis.ts`, add to the returned object beside `xParam` / `setXY`:

```ts
    // FDC 분석 axis mode — same opaque URL-passthrough treatment as xParam/setXY
    // above; SequenceWorkbench reads it and writes back on toggle.
    fdcAxis: ws.fdcAxis,
    setFdcAxis: ws.setFdcAxis,
```

- [ ] **Step 6: Run the tests and typecheck**

Run: `cd front-dev-home && npm test 2>&1 | tail -20 && npm run typecheck`
Expected: PASS, no type errors.

- [ ] **Step 7: Commit**

```bash
git add front-dev-home/app/utils/skewvoirAnalysis/routeQuery.ts \
        front-dev-home/app/utils/skewvoirAnalysis/routeQuery.test.ts \
        front-dev-home/app/composables/useSkewvoirRoute.ts \
        front-dev-home/app/composables/useSkewvoirWorkspace.ts \
        front-dev-home/app/composables/useSkewvoirAnalysis.ts
git commit -m "feat(skewvoir): carry the FDC axis mode in the URL

routeQuery.ts makes the URL the single source of truth for what an analysis
screen is showing, which is what makes it shareable by link. The FDC axis
changes which measurements are plotted, so it belongs there rather than in local
component state — otherwise a shared link reopens on a different axis than the
one the finding was made on.

Absent means the default parameter-scoped axis, so a plain analysis link stays
free of the param."
```

---

### Task 6: Register the `fdc` view kind

**Files:**

- Modify: `front-dev-home/app/composables/useSkewvoirWorkspace.ts:7-12,35-41`
- Modify: `front-dev-home/app/utils/skewvoirAnalysis/routeQuery.ts:21-27`
- Test: `front-dev-home/app/utils/skewvoirAnalysis/routeQuery.test.ts`

**Interfaces:**

- Consumes: nothing from earlier tasks.
- Produces: `SkewvoirViewKind` including `'fdc'`; `SKEWVOIR_VIEW_MODES` with six entries whose `index` values are 1-6.

- [ ] **Step 1: Write the failing test**

Append to `front-dev-home/app/utils/skewvoirAnalysis/routeQuery.test.ts`:

```ts
test('the fdc view kind parses and survives a round trip', () => {
  assert.equal(parseView('fdc'), 'fdc')
  assert.equal(parseView('time-series'), 'time-series')
  // Still whitelisted — a hand-edited link falls back to the Dashboard.
  assert.equal(parseView('fdc-analysis'), 'dashboard')
})
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd front-dev-home && npm test 2>&1 | tail -20`
Expected: FAIL — `parseView('fdc')` returns `'dashboard'` because `'fdc'` is not in `VIEW_KINDS`.

- [ ] **Step 3: Whitelist the kind**

In `front-dev-home/app/utils/skewvoirAnalysis/routeQuery.ts`, add `'fdc'` to `VIEW_KINDS` between `'position-stack'` and `'time-series'`:

```ts
const VIEW_KINDS: readonly SkewvoirViewKind[] = [
  'dashboard',
  'position-stack',
  'fdc',
  'time-series',
  'correlation',
  'gallery'
]
```

- [ ] **Step 4: Add the kind and the rail entry**

In `front-dev-home/app/composables/useSkewvoirWorkspace.ts`, extend the union:

```ts
export type SkewvoirViewKind
  = | 'dashboard'
    | 'position-stack'
    | 'fdc'
    | 'time-series'
    | 'correlation'
    | 'gallery'
```

Replace `SKEWVOIR_VIEW_MODES` with six entries. `fdc` and `time-series` are separate kinds because only the latter has a time axis at all — the single-MSR workbench plots measurement ORDER, and `sequence.ts` exposes no per-second rate:

```ts
export const SKEWVOIR_VIEW_MODES: readonly SkewvoirViewMode[] = [
  { kind: 'dashboard', index: 1, label: '측정 개요', sub: 'Measurement Overview', icon: 'i-lucide-clipboard-check' },
  { kind: 'position-stack', index: 2, label: '위치 비교', sub: 'Position Stack', icon: 'i-lucide-layers' },
  { kind: 'fdc', index: 3, label: 'FDC 분석', sub: 'Sequence & Dynamic FDC', icon: 'i-lucide-waves' },
  { kind: 'time-series', index: 4, label: 'Time-Series', sub: 'Multi-measurement Trend', icon: 'i-lucide-trending-up' },
  { kind: 'correlation', index: 5, label: '상관 / 분포', sub: 'Correlation & Distribution', icon: 'i-lucide-scatter-chart' },
  { kind: 'gallery', index: 6, label: '이미지 갤러리', sub: 'SEM Gallery', icon: 'i-lucide-images' }
] as const
```

- [ ] **Step 5: Run the tests and typecheck**

Run: `cd front-dev-home && npm test 2>&1 | tail -20 && npm run typecheck`

Expected: tests PASS. Typecheck FAILS in `Workspace.vue` because no branch renders `'fdc'` — Task 7 adds it. If typecheck passes here, the exhaustiveness you expected is not being enforced; proceed anyway.

- [ ] **Step 6: Commit**

```bash
git add front-dev-home/app/composables/useSkewvoirWorkspace.ts \
        front-dev-home/app/utils/skewvoirAnalysis/routeQuery.ts \
        front-dev-home/app/utils/skewvoirAnalysis/routeQuery.test.ts
git commit -m "feat(skewvoir): register the FDC 분석 view kind

The time-series view branched on scope and only its set half was a time series;
the single half is the sequence + dynamic-FDC workbench, which has no time axis
at all — the MSR file carries no per-sequence timestamp, so every slope there is
per sequence step. One rail entry named Time-Series described half of what it
opened.

Adds fdc as its own kind at rail slot 3. Keyboard shortcuts need no change:
Workspace.vue derives them from viewModes[].index, so 1-6 wire themselves."
```

---

### Task 7: Split the views

**Files:**

- Create: `front-dev-home/app/components/ebeam/skewvoir/views/Fdc.vue`
- Modify: `front-dev-home/app/components/ebeam/skewvoir/views/TimeSeries.vue:1-14,125-126`
- Modify: `front-dev-home/app/components/ebeam/skewvoir/Workspace.vue:44-64,163`

**Interfaces:**

- Consumes: `'fdc'` from `SkewvoirViewKind` (Task 6); `analysis.scope` from `useSkewvoirAnalysis`.
- Produces: the `EbeamSkewvoirViewsFdc` auto-imported component.

- [ ] **Step 1: Create the FDC view**

Create `front-dev-home/app/components/ebeam/skewvoir/views/Fdc.vue`:

```vue
<template>
  <!-- Single-MSR only. The workbench plots MEASUREMENT ORDER, not time — the MSR
       file carries no per-sequence timestamp — so it has nothing to say about a
       multi-measurement set. That comparison is the Time-Series view. -->
  <EbeamSkewvoirTimeseriesSequenceWorkbench
    v-if="analysis.scope.value === 'single'"
    :analysis="analysis"
  />

  <div
    v-else
    class="dashboard-surface flex h-72 flex-col items-center justify-center gap-1 rounded-(--sk-r-card) px-4 text-center"
  >
    <p class="sk-title">
      FDC 분석
    </p>
    <p class="sk-body">
      측정 하나를 선택하면 sequence별 CD와 dynamic FDC를 함께 볼 수 있습니다.
    </p>
  </div>
</template>

<script setup lang="ts">
import type { SkewvoirAnalysis } from '~/composables/useSkewvoirAnalysis'

defineProps<{
  analysis: SkewvoirAnalysis
}>()
</script>
```

- [ ] **Step 2: Trim the Time-Series view to the set scope**

In `front-dev-home/app/components/ebeam/skewvoir/views/TimeSeries.vue`, replace lines 1-14 (the comment, the `SequenceWorkbench` element, and the opening `<div v-else>`) with:

```vue
<template>
  <!-- Multi-measurement comparison only. The single-MSR sequence workbench moved
       to the FDC 분석 view: it plots measurement ORDER, which is a different
       axis from this view's across-measurement trend, not a narrower one. -->
  <div
    v-if="analysis.scope.value === 'set'"
    class="space-y-3"
  >
```

Then replace the closing of that block (lines 125-126, `</div>` followed by `</template>`) with:

```vue
  </div>

  <div
    v-else
    class="dashboard-surface flex h-72 flex-col items-center justify-center gap-1 rounded-(--sk-r-card) px-4 text-center"
  >
    <p class="sk-title">
      Time-Series
    </p>
    <p class="sk-body">
      MSR을 2개 이상 선택하면 측정 간 추이를 비교합니다.
    </p>
  </div>
</template>
```

Leave the `<script setup>` block unchanged — `hasFocusData` and `anomalyCfg` are still used by the set branch.

- [ ] **Step 3: Dispatch the new view**

In `front-dev-home/app/components/ebeam/skewvoir/Workspace.vue`, insert before the `EbeamSkewvoirViewsTimeSeries` element (line 53):

```vue
            <EbeamSkewvoirViewsFdc
              v-else-if="ws.activeKind.value === 'fdc'"
              :analysis="analysis"
            />
```

And update the shortcut comment at line 163:

```ts
// Keys 1-6 jump to the matching left-rail view mode.
```

- [ ] **Step 4: Typecheck and lint**

Run: `cd front-dev-home && npm run typecheck && npm run lint`
Expected: no errors.

- [ ] **Step 5: Commit**

```bash
git add front-dev-home/app/components/ebeam/skewvoir/views/Fdc.vue \
        front-dev-home/app/components/ebeam/skewvoir/views/TimeSeries.vue \
        front-dev-home/app/components/ebeam/skewvoir/Workspace.vue
git commit -m "feat(skewvoir): split FDC 분석 out of the Time-Series view

Each view now owns one scope and says so when it is off-scope, rather than one
rail entry silently swapping its whole body on the scope param.

Both entries stay in the rail in both scopes: hiding the off-scope one would
reshuffle the rail (and its number shortcuts) under the user whenever the
selection size changed."
```

---

### Task 8: Wire the axis toggle and the integrity badge

**Files:**

- Modify: `front-dev-home/app/components/ebeam/skewvoir/timeseries/SequenceWorkbench.vue:39-58,160-175`

**Interfaces:**

- Consumes: `analyzeSequence(..., axisMode)`, `model.excludedFdc`, `model.integrity` (Task 1); `analysis.fdcAxis` / `analysis.setFdcAxis` (Task 5).
- Produces: nothing.

- [ ] **Step 1: Pass the axis mode into the model**

In `front-dev-home/app/components/ebeam/skewvoir/timeseries/SequenceWorkbench.vue`, replace the `model` computed (lines 170-173):

```ts
// The shared-cursor sequence model for the FOCUS file + active parameter, on the
// axis the URL asks for.
const model = computed(() =>
  analyzeSequence(
    source.value,
    props.analysis.activeParam.value,
    props.analysis.activeUnit.value,
    props.analysis.fdcAxis.value
  )
)

const axisItems = [
  { label: '파라미터 정렬', value: 'param' },
  { label: '전체 sequence', value: 'all' }
]

// v-model on a computed with an explicit setter, so the URL stays the single
// source of truth rather than a local ref shadowing it.
const axisMode = computed({
  get: () => props.analysis.fdcAxis.value,
  set: (v: SequenceAxisMode) => props.analysis.setFdcAxis(v)
})
```

Add the type import beside the existing `sequence.ts` import (line 149):

```ts
import { analyzeSequence, type FdcSeqSeries, type SequenceAxisMode, type SequenceSource } from '~/utils/skewvoirAnalysis/sequence'
```

- [ ] **Step 2: Add the control and the counts to the sequence panel**

Replace the `#actions` block of the 측정 순서 panel (lines 47-51):

```vue
        <template #actions>
          <div class="flex items-center gap-2">
            <span
              v-if="!model.integrity.matched && model.integrity.fdc > 0"
              class="rounded-(--sk-r-chip) bg-(--sk-warn-soft) px-2 py-0.5 font-mono text-[10px] text-(--sk-warn)"
              :title="`측정 row ${model.integrity.rows}개 · dynamic FDC ${model.integrity.fdc}개 — 측정마다 FDC 1건이 있어야 합니다.`"
            >
              데이터 불일치 · row {{ model.integrity.rows }} / FDC {{ model.integrity.fdc }}
            </span>
            <USelect
              v-model="axisMode"
              size="xs"
              :items="axisItems"
              class="min-w-[8.5rem]"
            />
            <span class="sk-meta tabular-nums">
              cursor: {{ analysis.focusedSequence.value ?? '—' }}
            </span>
          </div>
        </template>
```

Replace the panel's `:meta` binding (line 44) so a scoped axis says what it left out:

```vue
        :meta="sequenceMeta"
```

And add the computed beside the other meta builders (after `cdMeta`, around line 203):

```ts
// A scoped axis is a SUBSET of the MSR, so it says so — otherwise a subset
// reads as the whole run.
const sequenceMeta = computed(() => {
  const base = `${model.value.sequences.length} points · ${props.analysis.activeParam.value}`
  return model.value.excludedFdc > 0
    ? `${base} · 타 parameter ${model.value.excludedFdc} 제외`
    : base
})
```

- [ ] **Step 3: Typecheck and lint**

Run: `cd front-dev-home && npm run typecheck && npm run lint`
Expected: no errors.

Note: `Workspace.vue:155-162`'s `selectorFocused()` guard already stops a `USelect` from swallowing the 1-6 view shortcuts, so no shortcut work is needed for this control.

- [ ] **Step 4: Commit**

```bash
git add front-dev-home/app/components/ebeam/skewvoir/timeseries/SequenceWorkbench.vue
git commit -m "feat(skewvoir): expose the FDC axis toggle and the integrity badge

The axis control lives on the 측정 순서 panel because that panel IS the axis. A
scoped axis now reports what it excluded in the panel meta, so a subset cannot
read as the whole run.

The integrity badge fires only when dynamic_fdc is non-empty but disagrees with
the row count — an MSR with no dynamic FDC at all already has its own empty
state, and flagging it here would be noise rather than a fault."
```

---

### Task 9: Verify end to end

**Files:** none modified.

**Interfaces:**

- Consumes: everything above.
- Produces: nothing.

- [ ] **Step 1: Run every suite**

```bash
.venv/bin/python -m pytest -q 2>&1 | tail -5
cd front-dev-home && npm test 2>&1 | tail -5 && npm run typecheck && npm run lint
cd .. && npm run lint:md
```

Expected: all pass. Report actual counts — do not claim a pass without the output.

- [ ] **Step 2: Launch the app**

Follow the `verify` skill. In short: `.venv/bin/python index.py` (Flask on :5050) and `cd front-dev-home && npm run dev` (Nuxt on :3000). A blank SPA with no console errors means Flask is down, not a broken component.

- [ ] **Step 3: Check the rail and both empty states**

Open a single-MSR analysis link. Confirm:

- The rail lists six entries, `FDC 분석` at 3 and `Time-Series` at 4.
- Keys `1`-`6` switch views.
- `FDC 분석` renders the workbench; `Time-Series` renders `MSR을 2개 이상 선택하면…`.
- With two or more MSRs selected the two swap which one shows its empty state.

- [ ] **Step 4: Check the axis fix**

On the `FDC 분석` view of a multi-parameter MSR:

- The 측정 순서 panel meta reads `… · 타 parameter N 제외` with `N > 0`.
- Switching the select to `전체 sequence` lengthens every chart's x-axis and drops the exclusion note; the CD line gains gaps where other parameters were measured.
- The URL gains `fdcaxis=all` on the whole-MSR axis and loses the param when switched back.
- Switching the active parameter changes which sequences appear.

If `타 parameter N 제외` never shows, the MSR drew a single parameter — open another. Confirm with:

```bash
curl -s --cookie 'LASTUSER=local-dev' 'http://localhost:5050/api/msr-file?msr=<MSR>&class_name=<CLASS>&total_images=<N>' \
  | python3 -c "import json,sys;d=json.load(sys.stdin);print('rows',d['total'],'fdc',len(d['dynamic_fdc']),'params',[p['parameter'] for p in d['parameters']])"
```

`rows` and `fdc` must be equal. Mind the 20 req / 5 s rate limit.

- [ ] **Step 5: Screenshot both axis modes**

Save under `.playwright-mcp/screenshots/` with relative filenames (the MCP server resolves them from the project cwd; omitting the prefix dumps PNGs at the repo root):

- `.playwright-mcp/screenshots/skewvoir-fdc-axis-param.png`
- `.playwright-mcp/screenshots/skewvoir-fdc-axis-all.png`

- [ ] **Step 6: Commit any fixes found**

If verification surfaces a defect, fix it, re-run the affected suite, and commit with a message naming what verification caught.

---

## Self-Review

**Spec coverage:**

| Spec section | Task |
| --- | --- |
| §Invariant | 1 (`integrity`), 3 (mock satisfies it), 4 (office warning + MIGRATION.md) |
| §Design 1 — sequence axis | 1 |
| §Design 1 — matrix inherits axis | 2 |
| §Design 2 — `fdcaxis` param | 5 |
| §Design 2 — toggle placement, exclusion meta, integrity badge | 8 |
| §Design 3 — view split | 6 (kind + rail), 7 (components) |
| §Design 4 — mock | 3 |
| §Testing | 1, 2, 3, 4, 5, 6 (unit); 9 (browser) |
| §Deferred — `features.ts`, `fdc_params` | untouched by every task, as specified |

**Type consistency:** `SequenceAxisMode` is declared once in `types.ts` (Task 1), re-exported from `sequence.ts`, and imported by `routeQuery.ts` (Task 5) and `SequenceWorkbench.vue` (Task 8). `parseFdcAxis` / `fdcAxis` / `setFdcAxis` keep those exact names across Tasks 5 and 8. `SequenceIntegrity`'s three fields (`rows`, `fdc`, `matched`) are consumed with those names in Task 8's badge and Task 1's tests.

**Known cross-task break:** Task 6 makes `'fdc'` a valid `SkewvoirViewKind` before Task 7 renders it, so `npm run typecheck` may fail between the two. Task 6 Step 5 says so explicitly. Do not reorder them — the reverse (a component branch on a kind that does not exist) fails harder.
