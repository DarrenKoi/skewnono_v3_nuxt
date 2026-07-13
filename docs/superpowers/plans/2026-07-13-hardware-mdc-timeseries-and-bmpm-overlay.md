# Hardware MDC Time-Series + BM/PM Overlay Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Part A — rebuild the MDC hardware tab around a per-tool timestamped history (시계열 sub-tab: 0°/90° x-y trajectory + per-axis trends; 비교 sub-tab: fleet boxplot replacing the matrix table). Part B — overlay BM/PM maintenance events as colored vertical markLines on every time-axis hardware chart, behind one page-level toggle (default ON).

**Architecture:** The Phase-1 Flask mock gains `build_mdc_history()` (long-format `{timestamp, beam_condition, mdc_value}` records riding in the existing `docs` payload field) and re-anchors `bm_pm_mock` to the requested window `end` so markers land inside chart ranges. The frontend adds three pure utils (`mdcHistory.ts`, `boxplotStats.ts`, `bmPmMarkers.ts`), rebuilds `MdcPanel.vue` with 시계열/비교 sub-tabs, and threads a `maintenance-events` prop from `HardwareView` into the five chart panels. Response contracts keep the `docs`/`settings` shapes, so the office provider swap stays confined to the provider layer.

**Tech Stack:** Flask mock (`back_dev_home`, deterministic seed-from-eqp_id generators, pandas), Nuxt 4 + NuxtUI (`USwitch`, `SkChip`), ECharts 6.1.0 (`markLine`, `boxplot`), pure TS utils tested with `node --test`.

**Spec:** `docs/superpowers/specs/2026-07-13-hardware-mdc-timeseries-and-bmpm-overlay-design.md`

## Global Constraints

- Work directly on `main`. Commit per task (the commit steps below are the authorization); do **not** push unless the user asks.
- Frontend unit tests: `npm --prefix front-dev-home test` (node --test, colocated `app/utils/*.test.ts`). Baseline before this plan: 127 pass, 0 fail.
- Typecheck: `npm --prefix front-dev-home run typecheck` (expect exit 0; the pre-existing warning noise is fine, errors are not).
- Backend verification: `.venv/bin/python` from the repo root (no pytest infra — use inline `python -c` assertion scripts exactly as written).
- Backend mocks must stay deterministic: same inputs → same output, no wall-clock reads inside generators.
- Markdown edits: run `npm run lint:md` and keep tables MD060-compact.
- UI copy in Korean matches existing tone (e.g. "MDC 이력 데이터가 없습니다.").
- All file paths below are relative to the repo root `/Users/daeyoung/Codes/skewnono_v3_nuxt`.

---

## Context for the implementer

- The hardware page is `front-dev-home/app/components/ebeam/HardwareView.vue`; it fetches one service payload per active tab via `useHardwareApi().fetchService()` and renders one panel component per service.
- `HardwarePayload` (both the TS interface in `front-dev-home/app/composables/useHardwareApi.ts` and the Python TypedDict in `back_dev_home/ebeam/hitachi/hardware/contracts.py`) already has optional `docs` (time-series records) and `settings` (dict-of-dict) — MDC will now carry **both**.
- Chart y-axes: hardware trend charts use `stableYRange` (magnitude-relative floor). **MDC values sit at 1.0 ±0.55%, so `stableYRange` would flatten them — MDC charts use tight scaling (`scale: true`).**
- `BsmTrendChart.vue` is the shared time-axis line chart (used by BSM + Sharpness panels; MDC trends will reuse it too).
- ECharts `markLine` entries of shape `{ xAxis: <epoch ms> }` draw full-height vertical lines on a `type: 'time'` x-axis, are clipped to the grid automatically, and follow dataZoom for free.

---

### Task 1: Backend — MDC history mock + payload wiring

**Files:**
- Modify: `back_dev_home/ebeam/hitachi/hardware/providers/mdc_mock.py`
- Modify: `back_dev_home/ebeam/hitachi/hardware/normalizers.py` (`settings_payload`, lines 277–309)
- Modify: `back_dev_home/ebeam/hitachi/hardware/providers/mock.py` (import + `mdc` branch, lines 16, 123–130)

**Interfaces:**
- Consumes: existing `seed_for`, `_conditions_for`, `build_mdc_settings` in `mdc_mock.py`.
- Produces: `build_mdc_history(eqp_id: str, start: datetime, end: datetime) -> list[dict[str, str | float]]` — ascending long-format records `{"timestamp": "YYYY-MM-DD HH:MM", "beam_condition": str, "mdc_value": float}`; the `mdc` service payload now contains `docs` (history) **and** `settings` (fleet snapshot). Task 4 consumes `payload.docs`.

- [ ] **Step 1: Add `build_mdc_history` to `mdc_mock.py`**

Change the datetime import and `__all__`, then append the generator:

```python
from datetime import datetime, timedelta
```

```python
__all__ = ["build_mdc_history", "build_mdc_settings"]
```

```python
_TS_FMT = "%Y-%m-%d %H:%M"
# Random-walk band: the same envelope the snapshot values use.
_BAND_LO, _BAND_HI = 0.995, 1.006
# Walk origin far enough back to cover any plausible request window.
_WALK_ANCHOR = datetime(2025, 1, 1, 9, 0)


def build_mdc_history(
    eqp_id: str,
    start: datetime,
    end: datetime,
) -> list[dict[str, str | float]]:
    """Timestamped MDC history for one tool across [start, end], ascending.

    Recalibration events land every 3-10 days; each event refreshes every
    beam_condition the tool carries (long format: one record per condition).
    Values drift as a clamped random walk inside the snapshot band. The walk
    always replays from a fixed anchor, so a given eqp_id yields identical
    values for the same dates regardless of the requested window.
    """
    struct_seed = seed_for(eqp_id) ^ 0x4D44_4332          # same tool/condition set as settings
    conds = _conditions_for(random.Random(struct_seed))
    rng = random.Random(struct_seed ^ 0x48495354)         # distinct history value stream
    values = {cond: rng.uniform(_BAND_LO, _BAND_HI) for cond in conds}

    records: list[dict[str, str | float]] = []
    moment = _WALK_ANCHOR
    while moment <= end:
        if moment >= start:
            for cond in conds:
                records.append(
                    {
                        "timestamp": moment.strftime(_TS_FMT),
                        "beam_condition": cond,
                        "mdc_value": round(values[cond], 6),
                    }
                )
        moment += timedelta(days=rng.randint(3, 10), hours=rng.randint(0, 5))
        for cond in conds:
            stepped = values[cond] + rng.gauss(0.0, 0.0012)
            values[cond] = min(_BAND_HI, max(_BAND_LO, stepped))
    return records
```

- [ ] **Step 2: Let `settings_payload` carry optional `docs`**

In `normalizers.py`, add a keyword param and switch the direct `return` literal to a named `payload` so `docs` can be attached conditionally:

```python
def settings_payload(
    service: ServiceKey,
    tool_slug: str,
    eqp_id: str | None,
    fab_name: str | None,
    *,
    settings: dict[str, dict],
    as_of: str,
    summary: str,
    tables: list[HardwareTableSection] | None = None,
    docs: list[dict] | None = None,
) -> HardwarePayload:
    """Wrap a faithful dict-of-dict (mdc / sce): eqp + in-fab siblings.

    Thin cards: as-of date + sibling count. `tables` optional (e.g. the sce
    settings-compare is built frontend-side off `settings`). `docs` optionally
    carries the selected tool's timestamped history (mdc 시계열), ascending.
    """
    sibling_count = max(0, len(settings) - 1)
    cards: list[HardwareMetricCard] = [
        {"key": "as_of", "label": "기준일", "value": as_of, "tone": "neutral"},
        {"key": "sibling_count", "label": "동일 fab 장비", "value": sibling_count, "unit": "대", "tone": "neutral"},
    ]
    payload: HardwarePayload = {
        "tool_slug": tool_slug,
        "service": service,
        "eqp_id": eqp_id,
        "fab_name": fab_name,
        "available": True,
        "fetched_at": now_iso(),
        "summary": summary,
        "cards": cards,
        "tables": tables or [],
        "settings": settings,
    }
    if docs is not None:
        payload["docs"] = docs
    return payload
```

- [ ] **Step 3: Wire the `mdc` branch in `mock.py`**

Update the import:

```python
from back_dev_home.ebeam.hitachi.hardware.providers.mdc_mock import (
    build_mdc_history,
    build_mdc_settings,
)
```

Replace the `if service == "mdc":` block:

```python
    if service == "mdc":
        settings = build_mdc_settings(eqp_id, fab_name, end)
        history = build_mdc_history(eqp_id, start, end)
        return settings_payload(
            service, tool_slug, eqp_id, fab_name,
            settings=settings,
            as_of=end.strftime("%Y-%m-%d"),
            summary="선택 장비의 MDC 보정 이력(시계열)과 동일 fab 장비의 "
                    "스냅샷(as-of) 비교를 제공합니다.",
            docs=history,
        )
```

- [ ] **Step 4: Verify the generator and payload**

Run from the repo root:

```bash
.venv/bin/python -c "
from datetime import datetime
from back_dev_home.ebeam.hitachi.hardware.providers.mdc_mock import build_mdc_history, build_mdc_settings

start, end = datetime(2026, 6, 13), datetime(2026, 7, 13)
a = build_mdc_history('ECX101', start, end)
b = build_mdc_history('ECX101', start, end)
assert a == b, 'not deterministic'
assert len(a) > 0, 'no records in a 30d window'
ts = [r['timestamp'] for r in a]
assert ts == sorted(ts), 'not ascending'
assert all(start.strftime('%Y-%m-%d') <= t[:10] <= end.strftime('%Y-%m-%d') for t in ts), 'outside window'
assert all(0.995 <= r['mdc_value'] <= 1.006 for r in a), 'value outside band'
conds = {r['beam_condition'] for r in a}
snap = set(build_mdc_settings('ECX101', 'M16B', end)['ECX101'].keys())
assert conds == snap, f'condition mismatch: {conds} vs {snap}'
wide = build_mdc_history('ECX101', datetime(2026, 5, 1), end)
overlap = [r for r in wide if r['timestamp'] >= a[0]['timestamp']]
assert overlap == a, 'window change altered values'
print('mdc history mock OK:', len(a), 'records,', sorted(conds))
"
```

Expected: `mdc history mock OK: ...` (no AssertionError).

```bash
.venv/bin/python -c "
from datetime import datetime
from back_dev_home.ebeam.hitachi.hardware.providers.mock import get_hardware_service
p = get_hardware_service('cdsem', 'mdc', 'ECX101', 'M16B', datetime(2026, 6, 13), datetime(2026, 7, 13))
assert 'docs' in p and 'settings' in p, 'payload missing docs/settings'
assert {'timestamp', 'beam_condition', 'mdc_value'} <= set(p['docs'][0].keys())
print('mdc payload OK:', len(p['docs']), 'docs,', len(p['settings']), 'tools')
"
```

Expected: `mdc payload OK: ...`.

- [ ] **Step 5: Commit (include the spec + this plan)**

```bash
git add back_dev_home/ebeam/hitachi/hardware docs/superpowers/specs/2026-07-13-hardware-mdc-timeseries-and-bmpm-overlay-design.md docs/superpowers/plans/2026-07-13-hardware-mdc-timeseries-and-bmpm-overlay.md
git commit -m "feat(ebeam): serve timestamped MDC history in the mdc hardware payload"
```

---

### Task 2: Pure util — `mdcHistory.ts` (docs → family series)

**Files:**
- Create: `front-dev-home/app/utils/mdcHistory.ts`
- Test: `front-dev-home/app/utils/mdcHistory.test.ts`

**Interfaces:**
- Consumes: the `docs` records from Task 1 (as `Record<string, unknown>[]`).
- Produces (Task 4 imports all of these):

```ts
export interface MdcHistoryPoint { ts: string, value: number }
export interface MdcFamily {
  key: string                  // '800V_HR' | '500V_HR' | '3000V_HR' | 'Valley' ...
  zero: MdcHistoryPoint[]      // 0° axis, or the sole series for unpaired families
  ninety: MdcHistoryPoint[]    // 90° axis; empty when the family has no pair
}
export const buildMdcFamilies: (docs: Record<string, unknown>[]) => MdcFamily[]
export const trajectoryPoints: (family: MdcFamily) => { ts: string, x: number, y: number }[]
```

- [ ] **Step 1: Write the failing test**

Create `front-dev-home/app/utils/mdcHistory.test.ts`:

```ts
// Pure-logic tests — run with: npm --prefix front-dev-home test
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { buildMdcFamilies, trajectoryPoints } from './mdcHistory.ts'

const doc = (ts: string, cond: string, value: number) =>
  ({ timestamp: ts, beam_condition: cond, mdc_value: value })

const docs = [
  doc('2026-06-01 09:00', '800V_HR_0Deg', 1.001),
  doc('2026-06-01 09:00', '800V_HR_90Deg', 0.999),
  doc('2026-06-01 09:00', 'Valley', 1.002),
  doc('2026-06-08 10:00', '800V_HR_0Deg', 1.003),
  doc('2026-06-08 10:00', '800V_HR_90Deg', 0.998),
  doc('2026-06-08 10:00', 'Valley', 1.004)
]

test('buildMdcFamilies: groups by family and splits 0/90 axes', () => {
  const fams = buildMdcFamilies(docs)
  assert.deepEqual(fams.map(f => f.key), ['800V_HR', 'Valley'])
  const f800 = fams[0]!
  assert.equal(f800.zero.length, 2)
  assert.equal(f800.ninety.length, 2)
  assert.deepEqual(f800.zero[0], { ts: '2026-06-01 09:00', value: 1.001 })
})

test('buildMdcFamilies: unpaired condition lands in zero with empty ninety', () => {
  const valley = buildMdcFamilies(docs)[1]!
  assert.equal(valley.zero.length, 2)
  assert.equal(valley.ninety.length, 0)
})

test('buildMdcFamilies: points come out ascending even from shuffled docs', () => {
  const fams = buildMdcFamilies([...docs].reverse())
  const ts = fams.find(f => f.key === '800V_HR')!.zero.map(p => p.ts)
  assert.deepEqual(ts, [...ts].sort())
})

test('buildMdcFamilies: non-numeric values and blank conditions are dropped', () => {
  const fams = buildMdcFamilies([
    doc('2026-06-01 09:00', '800V_HR_0Deg', NaN),
    { timestamp: '2026-06-01 09:00', beam_condition: '', mdc_value: 1 },
    doc('2026-06-02 09:00', '800V_HR_0Deg', 1.002)
  ])
  assert.equal(fams.length, 1)
  assert.equal(fams[0]!.zero.length, 1)
})

test('trajectoryPoints: zips 0/90 by timestamp, skipping unmatched events', () => {
  const f800 = buildMdcFamilies(docs)[0]!
  assert.deepEqual(trajectoryPoints(f800), [
    { ts: '2026-06-01 09:00', x: 1.001, y: 0.999 },
    { ts: '2026-06-08 10:00', x: 1.003, y: 0.998 }
  ])
})

test('trajectoryPoints: unpaired family yields no points', () => {
  const valley = buildMdcFamilies(docs)[1]!
  assert.deepEqual(trajectoryPoints(valley), [])
})
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
npm --prefix front-dev-home test 2>&1 | tail -5
```

Expected: FAIL — `Cannot find module ... mdcHistory.ts`.

- [ ] **Step 3: Implement**

Create `front-dev-home/app/utils/mdcHistory.ts`:

```ts
// Pure: shape the mdc `docs` history (long-format {timestamp, beam_condition,
// mdc_value} records) into per-family 0°/90° series for the MDC 시계열 view.
// Families pair `<family>_0Deg` / `<family>_90Deg`; a condition without a
// degree suffix (e.g. "Valley") is its own single-axis family.

export interface MdcHistoryPoint {
  ts: string
  value: number
}

export interface MdcFamily {
  key: string
  zero: MdcHistoryPoint[]
  ninety: MdcHistoryPoint[]
}

const DEG_RE = /_(0|90)Deg$/

const toNum = (v: unknown): number => {
  const n = typeof v === 'number' ? v : Number(v)
  return Number.isFinite(n) ? n : NaN
}

export const buildMdcFamilies = (docs: Record<string, unknown>[]): MdcFamily[] => {
  // Map preserves first-appearance order → the mock's 800V-first ordering
  // becomes the chip order without extra sorting rules.
  const byKey = new Map<string, MdcFamily>()
  for (const d of docs) {
    const cond = String(d.beam_condition ?? '')
    const ts = String(d.timestamp ?? '')
    const value = toNum(d.mdc_value)
    if (!cond || !ts || !Number.isFinite(value)) continue
    const m = cond.match(DEG_RE)
    const key = m ? cond.slice(0, -m[0].length) : cond
    let fam = byKey.get(key)
    if (!fam) {
      fam = { key, zero: [], ninety: [] }
      byKey.set(key, fam)
    }
    ;(m?.[1] === '90' ? fam.ninety : fam.zero).push({ ts, value })
  }
  const byTs = (a: MdcHistoryPoint, b: MdcHistoryPoint) => a.ts.localeCompare(b.ts)
  for (const fam of byKey.values()) {
    fam.zero.sort(byTs)
    fam.ninety.sort(byTs)
  }
  return [...byKey.values()]
}

// (0°, 90°) pairs matched by timestamp — a recalibration event refreshes both
// axes at once, so timestamps align; unmatched events are skipped.
export const trajectoryPoints = (
  family: MdcFamily
): { ts: string, x: number, y: number }[] => {
  const ninetyByTs = new Map(family.ninety.map(p => [p.ts, p.value]))
  const out: { ts: string, x: number, y: number }[] = []
  for (const p of family.zero) {
    const y = ninetyByTs.get(p.ts)
    if (y !== undefined) out.push({ ts: p.ts, x: p.value, y })
  }
  return out
}
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
npm --prefix front-dev-home test 2>&1 | tail -5
```

Expected: all pass (baseline 127 + 6 new).

- [ ] **Step 5: Commit**

```bash
git add front-dev-home/app/utils/mdcHistory.ts front-dev-home/app/utils/mdcHistory.test.ts
git commit -m "feat(ebeam): add mdcHistory util shaping MDC docs into 0°/90° family series"
```

---

### Task 3: Pure util — `boxplotStats.ts` (five-number summary)

**Files:**
- Create: `front-dev-home/app/utils/boxplotStats.ts`
- Test: `front-dev-home/app/utils/boxplotStats.test.ts`

**Interfaces:**
- Produces (Task 5 imports these):

```ts
export interface BoxStats { min: number, q1: number, median: number, q3: number, max: number }
export const boxStats: (values: number[]) => BoxStats | null
```

- [ ] **Step 1: Write the failing test**

Create `front-dev-home/app/utils/boxplotStats.test.ts`:

```ts
// Pure-logic tests — run with: npm --prefix front-dev-home test
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { boxStats } from './boxplotStats.ts'

test('odd-length sample: exact median and R-7 interpolated quartiles', () => {
  assert.deepEqual(boxStats([1, 2, 3, 4, 5]), { min: 1, q1: 2, median: 3, q3: 4, max: 5 })
})

test('even-length sample: interpolated median and quartiles', () => {
  const s = boxStats([1, 2, 3, 4])!
  assert.equal(s.median, 2.5)
  assert.equal(s.q1, 1.75)
  assert.equal(s.q3, 3.25)
})

test('unsorted input is handled', () => {
  assert.equal(boxStats([5, 1, 4, 2, 3])!.median, 3)
})

test('single value collapses the box', () => {
  assert.deepEqual(
    boxStats([1.003]),
    { min: 1.003, q1: 1.003, median: 1.003, q3: 1.003, max: 1.003 }
  )
})

test('identical values collapse the box', () => {
  assert.deepEqual(boxStats([2, 2, 2]), { min: 2, q1: 2, median: 2, q3: 2, max: 2 })
})

test('non-finite values are dropped; empty input → null', () => {
  assert.equal(boxStats([]), null)
  assert.equal(boxStats([NaN, Infinity]), null)
  assert.equal(boxStats([NaN, 1, 3])!.median, 2)
})
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
npm --prefix front-dev-home test 2>&1 | tail -5
```

Expected: FAIL — `Cannot find module ... boxplotStats.ts`.

- [ ] **Step 3: Implement**

Create `front-dev-home/app/utils/boxplotStats.ts`:

```ts
// Pure: five-number summary for the MDC fleet boxplot. Quartiles use R-7
// linear interpolation (numpy/Excel default). min/max are the true extremes —
// hardware fleets are 4-6 tools, so whisker fencing would hide real tools.

export interface BoxStats {
  min: number
  q1: number
  median: number
  q3: number
  max: number
}

const quantileSorted = (sorted: number[], p: number): number => {
  const pos = (sorted.length - 1) * p
  const lo = Math.floor(pos)
  const hi = Math.ceil(pos)
  return sorted[lo]! + (pos - lo) * (sorted[hi]! - sorted[lo]!)
}

export const boxStats = (values: number[]): BoxStats | null => {
  const sorted = values.filter(v => Number.isFinite(v)).sort((a, b) => a - b)
  if (sorted.length === 0) return null
  return {
    min: sorted[0]!,
    q1: quantileSorted(sorted, 0.25),
    median: quantileSorted(sorted, 0.5),
    q3: quantileSorted(sorted, 0.75),
    max: sorted[sorted.length - 1]!
  }
}
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
npm --prefix front-dev-home test 2>&1 | tail -5
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add front-dev-home/app/utils/boxplotStats.ts front-dev-home/app/utils/boxplotStats.test.ts
git commit -m "feat(ebeam): add boxplotStats util (R-7 five-number summary)"
```

---

### Task 4: MdcPanel 시계열 sub-tab (trajectory + per-axis trends)

**Files:**
- Modify: `front-dev-home/app/components/ebeam/hardware/MdcPanel.vue` (full rewrite below)
- Modify: `front-dev-home/app/components/ebeam/hardware/BsmTrendChart.vue` (add `yMode` prop)
- Modify: `front-dev-home/app/components/ebeam/HardwareView.vue` (pass `:docs` to MdcPanel, ~line 489)

**Interfaces:**
- Consumes: `buildMdcFamilies`, `trajectoryPoints`, `MdcFamily`, `MdcHistoryPoint` (Task 2); `payload.docs` (Task 1).
- Produces: `MdcPanel` props become `{ settings, docs, selectedEqp }`; `BsmTrendChart` gains optional `yMode?: 'stable' | 'tight'` (default `'stable'`, existing callers unchanged). Task 5 edits this same `MdcPanel.vue`; Task 8 adds `events`/`maintenanceEvents` props on top.

- [ ] **Step 1: Add the `yMode` prop to `BsmTrendChart.vue`**

In the props block:

```ts
const props = defineProps<{
  label: string
  points: { ts: string, key: string, value: number }[]
  selected: string
  // MDC corrections drift ±0.55% around 1.0 — the drift IS the signal, so
  // 'tight' skips stableYRange's magnitude-relative floor (which would
  // flatten the series) and lets the axis hug the data.
  yMode?: 'stable' | 'tight'
}>()
```

And the `yAxis` inside `chartOption`:

```ts
  yAxis: {
    type: 'value',
    ...(props.yMode === 'tight'
      ? { scale: true }
      : (stableYRange(props.points.map(p => p.value)) ?? { scale: true })),
    axisLabel: { fontSize: 10 }
  },
```

- [ ] **Step 2: Rewrite `MdcPanel.vue`**

Replace the whole file with (the 비교 branch keeps the existing matrix table for now — Task 5 swaps it):

```vue
<template>
  <div class="mt-3 space-y-3">
    <!-- 시계열 | 비교 sub-tabs (same pattern as the FDC fdc_key tabs) -->
    <div class="flex w-fit overflow-hidden rounded-[10px] border border-(--sk-border)">
      <button
        v-for="tab in TABS"
        :key="tab"
        type="button"
        class="px-3.5 py-1.5 text-xs font-semibold transition-colors"
        :class="tab === activeTab
          ? 'bg-(--sk-ink) text-white dark:text-zinc-900'
          : 'text-(--sk-ink-muted) hover:bg-(--sk-muted-surface)'"
        @click="activeTab = tab"
      >
        {{ tab }}
      </button>
    </div>

    <!-- ===== 시계열: family chips + trajectory + per-axis trends ===== -->
    <template v-if="activeTab === '시계열'">
      <div
        v-if="families.length === 0"
        class="rounded-xl bg-(--sk-surface) px-4 py-8 text-center text-sm text-(--sk-ink-muted) ring-1 ring-(--sk-border-soft)"
      >
        MDC 이력 데이터가 없습니다.
      </div>
      <template v-else>
        <div class="flex flex-wrap items-center gap-1.5">
          <SkChip
            v-for="fam in families"
            :key="fam.key"
            size="sm"
            :active="fam.key === activeFamilyKey"
            :count="fam.zero.length"
            @click="activeFamilyKey = fam.key"
          >
            {{ fam.key }}
          </SkChip>
        </div>

        <div
          v-if="activeFamily"
          class="grid gap-3"
          :class="isPaired ? 'lg:grid-cols-[minmax(0,26rem)_minmax(0,1fr)]' : ''"
        >
          <!-- x/y trajectory (paired 0°/90° families only) -->
          <div
            v-if="isPaired"
            class="rounded-xl bg-(--sk-surface) p-2 ring-1 ring-(--sk-border-soft)"
          >
            <div class="mb-1 px-1 text-xs font-bold text-(--sk-ink)">
              0° · 90° Trajectory
            </div>
            <div
              ref="xyEl"
              class="aspect-square w-full"
            />
          </div>

          <!-- per-axis trends -->
          <div class="flex min-w-0 flex-col gap-3">
            <div class="rounded-xl bg-(--sk-surface) p-2 ring-1 ring-(--sk-border-soft)">
              <EbeamHardwareBsmTrendChart
                :label="isPaired ? `${activeFamily.key} · 0°` : activeFamily.key"
                :points="axisPoints(activeFamily.zero)"
                selected=""
                y-mode="tight"
              />
            </div>
            <div
              v-if="isPaired"
              class="rounded-xl bg-(--sk-surface) p-2 ring-1 ring-(--sk-border-soft)"
            >
              <EbeamHardwareBsmTrendChart
                :label="`${activeFamily.key} · 90°`"
                :points="axisPoints(activeFamily.ninety)"
                selected=""
                y-mode="tight"
              />
            </div>
          </div>
        </div>
      </template>
    </template>

    <!-- ===== 비교: fleet snapshot (matrix table — boxplot lands in the next task) ===== -->
    <template v-else>
      <div
        v-if="matrix.tools.length === 0"
        class="rounded-xl bg-(--sk-surface) px-4 py-8 text-center text-sm text-(--sk-ink-muted) ring-1 ring-(--sk-border-soft)"
      >
        MDC 설정 데이터가 없습니다.
      </div>
      <div
        v-else
        class="overflow-x-auto rounded-xl bg-(--sk-surface) ring-1 ring-(--sk-border-soft)"
      >
        <table class="min-w-full text-left text-xs">
          <thead class="bg-(--sk-muted-surface) text-(--sk-ink-muted)">
            <tr>
              <th class="whitespace-nowrap px-3 py-2 font-mono text-[10px] uppercase tracking-[0.05em]">
                EQP
              </th>
              <th
                v-for="cond in matrix.conditions"
                :key="cond"
                class="whitespace-nowrap px-3 py-2 text-right font-mono text-[10px] uppercase tracking-[0.05em]"
              >
                {{ cond }}
              </th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="(tool, row) in matrix.tools"
              :key="tool"
              class="border-t border-(--sk-border-soft)"
              :class="row === 0 ? 'bg-(--sk-muted-surface)' : ''"
            >
              <td class="whitespace-nowrap px-3 py-2 font-mono font-bold text-(--sk-ink)">
                {{ tool }}
                <span
                  v-if="row === 0"
                  class="ml-1 rounded bg-(--sk-ink) px-1 text-[9px] text-white dark:text-zinc-900"
                >선택</span>
              </td>
              <td
                v-for="(cond, col) in matrix.conditions"
                :key="cond"
                class="whitespace-nowrap px-3 py-2 text-right font-mono tabular-nums text-(--sk-ink)"
                :style="cellStyle(row, col)"
              >
                {{ formatCell(matrix.values[row]?.[col]) }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import type { EChartsOption } from 'echarts'
import { buildMdcMatrix, cellDeviation } from '~/utils/mdcMatrix'
import { buildMdcFamilies, trajectoryPoints, type MdcHistoryPoint } from '~/utils/mdcHistory'

const props = defineProps<{
  settings: Record<string, Record<string, unknown>>
  docs: Record<string, unknown>[]
  selectedEqp: string
}>()

const TABS = ['시계열', '비교'] as const
const activeTab = ref<(typeof TABS)[number]>('시계열')

// --- 시계열 ---
const families = computed(() => buildMdcFamilies(props.docs))
const activeFamilyKey = ref('')
watch(families, (fams) => {
  if (!fams.some(f => f.key === activeFamilyKey.value)) {
    activeFamilyKey.value = (fams.find(f => f.key === '800V_HR') ?? fams[0])?.key ?? ''
  }
}, { immediate: true })
const activeFamily = computed(() => families.value.find(f => f.key === activeFamilyKey.value))
const isPaired = computed(() => (activeFamily.value?.ninety.length ?? 0) > 0)

// BsmTrendChart wants {ts, key, value}; MDC has no per-point selection, so
// the timestamp doubles as the key.
const axisPoints = (pts: MdcHistoryPoint[]) => pts.map(p => ({ ts: p.ts, key: p.ts, value: p.value }))

const { palette } = useEchartsTheme()
const c0 = computed(() => palette.value[0] ?? '#C75A3C')
const c1 = computed(() => palette.value[1] ?? '#3F5D52')

const xyEl = ref<HTMLDivElement | null>(null)
const xyOption = computed<EChartsOption>(() => {
  const pts = activeFamily.value ? trajectoryPoints(activeFamily.value) : []
  const n = pts.length
  const latest = pts[n - 1]
  return {
    grid: { left: 56, right: 16, top: 16, bottom: 36 },
    tooltip: {
      trigger: 'item',
      formatter: (params) => {
        const raw = (Array.isArray(params) ? params[0] : params)?.data as unknown
        const v = (raw as { value?: unknown })?.value ?? raw
        return Array.isArray(v) ? `${v[2]}<br/>0° ${v[0]} · 90° ${v[1]}` : ''
      }
    },
    xAxis: { type: 'value', name: '0°', scale: true, axisLabel: { fontSize: 10 } },
    yAxis: { type: 'value', name: '90°', scale: true, axisLabel: { fontSize: 10 } },
    series: [
      {
        type: 'scatter',
        symbolSize: 8,
        // (1.0, 1.0) = no-correction reference crosshair.
        markLine: {
          silent: true,
          symbol: 'none',
          animation: false,
          lineStyle: { type: 'dashed', width: 1, color: '#9ca3af', opacity: 0.6 },
          label: { show: false },
          data: [{ xAxis: 1 }, { yAxis: 1 }]
        },
        data: pts.map((p, i) => ({
          value: [p.x, p.y, p.ts],
          // Older → more transparent, so the path reads oldest→newest.
          itemStyle: { color: c0.value, opacity: n <= 1 ? 1 : 0.2 + 0.7 * (i / (n - 1)) }
        }))
      },
      ...(latest
        ? [{
            type: 'scatter' as const,
            symbolSize: 14,
            itemStyle: { color: c1.value, borderColor: '#fff', borderWidth: 1 },
            data: [{ value: [latest.x, latest.y, `${latest.ts} (latest)`] }]
          }]
        : [])
    ]
  }
})
useEchart(xyEl, xyOption)

// --- 비교 (matrix table — replaced by the fleet boxplot in the next task) ---
const matrix = computed(() => buildMdcMatrix(props.settings, props.selectedEqp))

const formatCell = (v: number | null | undefined) =>
  v === null || v === undefined ? '-' : v.toFixed(4)

// Warm (rose) for above-baseline, cool (sky) for below; alpha = magnitude.
const cellStyle = (row: number, col: number) => {
  if (row === 0) return {}
  const dev = cellDeviation(matrix.value, row, col)
  if (dev === 0) return {}
  const alpha = Math.min(Math.abs(dev) * 0.6, 0.6).toFixed(3)
  const rgb = dev > 0 ? '244, 63, 94' : '56, 189, 248'
  return { backgroundColor: `rgba(${rgb}, ${alpha})` }
}
</script>
```

- [ ] **Step 3: Pass `docs` from `HardwareView.vue`**

Update the MdcPanel usage (~line 489):

```vue
                <!-- MDC: 시계열 (trajectory + per-axis trends) / 비교 sub-tabs -->
                <EbeamHardwareMdcPanel
                  v-else-if="activeService === 'mdc'"
                  :settings="servicePayload.settings ?? {}"
                  :docs="servicePayload.docs ?? []"
                  :selected-eqp="selectedTool?.eqp_id ?? ''"
                />
```

- [ ] **Step 4: Verify**

```bash
npm --prefix front-dev-home test 2>&1 | tail -3
npm --prefix front-dev-home run typecheck
```

Expected: tests all pass; typecheck exit 0.

- [ ] **Step 5: Commit**

```bash
git add front-dev-home/app/components/ebeam/hardware/MdcPanel.vue front-dev-home/app/components/ebeam/hardware/BsmTrendChart.vue front-dev-home/app/components/ebeam/HardwareView.vue
git commit -m "feat(ebeam): add MDC 시계열 sub-tab with 0°/90° trajectory and per-axis trends"
```

---

### Task 5: MdcPanel 비교 sub-tab → fleet boxplot (drop the matrix table)

**Files:**
- Modify: `front-dev-home/app/components/ebeam/hardware/MdcPanel.vue`
- Delete: `front-dev-home/app/utils/mdcMatrix.ts`, `front-dev-home/app/utils/mdcMatrix.test.ts`

**Interfaces:**
- Consumes: `boxStats` (Task 3); `props.settings` (unchanged shape).
- Produces: nothing new for later tasks; `buildMdcMatrix`/`cellDeviation` cease to exist.

- [ ] **Step 1: Replace the 비교 template branch in `MdcPanel.vue`**

Swap the whole `<template v-else>` block (matrix table) for:

```vue
    <!-- ===== 비교: fleet distribution boxplot per beam condition ===== -->
    <template v-else>
      <div
        v-if="conditions.length === 0"
        class="rounded-xl bg-(--sk-surface) px-4 py-8 text-center text-sm text-(--sk-ink-muted) ring-1 ring-(--sk-border-soft)"
      >
        MDC 설정 데이터가 없습니다.
      </div>
      <div
        v-else
        class="rounded-xl bg-(--sk-surface) p-2 ring-1 ring-(--sk-border-soft)"
      >
        <div class="mb-1 flex items-center justify-between px-1">
          <span class="text-xs font-bold text-(--sk-ink)">Fleet 분포 · 조건별</span>
          <span class="font-mono text-[11px] text-(--sk-ink-muted)">
            ◆ {{ selectedEqp || '—' }} · {{ fleetSize }}대
          </span>
        </div>
        <div
          ref="boxEl"
          class="h-80 w-full"
        />
      </div>
    </template>
```

- [ ] **Step 2: Replace the matrix script section with the boxplot option**

Remove the `import { buildMdcMatrix, cellDeviation } from '~/utils/mdcMatrix'` line and the entire `--- 비교 ---` block (`matrix`, `formatCell`, `cellStyle`); add:

```ts
import { boxStats } from '~/utils/boxplotStats'
```

```ts
// --- 비교: per-condition fleet distribution + selected-tool marker ---
const toNum = (v: unknown): number | null => {
  const n = typeof v === 'number' ? v : Number(v)
  return Number.isFinite(n) ? n : null
}

const fleetSize = computed(() => Object.keys(props.settings).length)

const conditions = computed(() => {
  const set = new Set<string>()
  for (const tool of Object.keys(props.settings)) {
    for (const cond of Object.keys(props.settings[tool] ?? {})) set.add(cond)
  }
  return [...set].sort()
})

const boxRows = computed(() => conditions.value.map((cond) => {
  const fleet = Object.keys(props.settings)
    .map(tool => toNum(props.settings[tool]?.[cond]))
    .filter((v): v is number => v !== null)
  return { cond, stats: boxStats(fleet), mine: toNum(props.settings[props.selectedEqp]?.[cond]) }
}))

const boxEl = ref<HTMLDivElement | null>(null)
const fmtVal = (v: number) => v.toFixed(4)
const boxOption = computed<EChartsOption>(() => ({
  grid: { left: 64, right: 16, top: 24, bottom: 48 },
  tooltip: {
    trigger: 'item',
    formatter: (params) => {
      const p = Array.isArray(params) ? params[0] : params
      if (!p) return ''
      const cond = conditions.value[p.dataIndex ?? 0] ?? ''
      if (p.seriesType === 'boxplot') {
        // ECharts prepends the category index → normalize to the 5 stats.
        const arr = (p.value ?? p.data) as number[]
        const v = arr.length === 6 ? arr.slice(1) : arr
        return `${cond}<br/>max ${fmtVal(v[4]!)}<br/>Q3 ${fmtVal(v[3]!)}`
          + `<br/>median ${fmtVal(v[2]!)}<br/>Q1 ${fmtVal(v[1]!)}<br/>min ${fmtVal(v[0]!)}`
      }
      const v = p.data as [number, number]
      return `<b>${props.selectedEqp}</b> · ${cond}<br/>${fmtVal(v[1]!)}`
    }
  },
  xAxis: { type: 'category', data: conditions.value, axisLabel: { fontSize: 10, rotate: 20 } },
  yAxis: { type: 'value', scale: true, axisLabel: { fontSize: 10 } },
  series: [
    {
      name: 'fleet',
      type: 'boxplot',
      itemStyle: { color: 'transparent', borderColor: c0.value },
      boxWidth: ['18%', '42%'],
      data: boxRows.value.map(r => r.stats
        ? [r.stats.min, r.stats.q1, r.stats.median, r.stats.q3, r.stats.max]
        : [NaN, NaN, NaN, NaN, NaN])
    },
    {
      name: 'selected',
      type: 'scatter',
      symbol: 'diamond',
      symbolSize: 12,
      itemStyle: { color: c1.value, borderColor: '#fff', borderWidth: 1 },
      data: boxRows.value
        .map((r, i) => (r.mine !== null ? [i, r.mine] as [number, number] : null))
        .filter((d): d is [number, number] => d !== null)
    }
  ]
}))
useEchart(boxEl, boxOption)
```

- [ ] **Step 3: Delete the dead matrix util**

```bash
git rm front-dev-home/app/utils/mdcMatrix.ts front-dev-home/app/utils/mdcMatrix.test.ts
grep -rn "mdcMatrix" front-dev-home/app || echo "no references left"
```

Expected: `no references left`.

- [ ] **Step 4: Verify**

```bash
npm --prefix front-dev-home test 2>&1 | tail -3
npm --prefix front-dev-home run typecheck
```

Expected: tests all pass (mdcMatrix tests gone, new util tests remain); typecheck exit 0. Note: if `nuxt typecheck` complains about the boxplot tooltip `params` narrowing, cast the callback param once: `formatter: (params: any) => { ... }` is NOT acceptable — instead type the locals (`const p = Array.isArray(params) ? params[0] : params`) and index defensively as shown.

- [ ] **Step 5: Commit**

```bash
git add front-dev-home/app/components/ebeam/hardware/MdcPanel.vue
git commit -m "feat(ebeam): replace MDC comparison matrix with fleet boxplot per condition"
```

---

### Task 6: Backend — anchor BM/PM mock to the requested window end

**Files:**
- Modify: `back_dev_home/ebeam/hitachi/hardware/providers/bm_pm_mock.py`
- Modify: `back_dev_home/ebeam/hitachi/hardware/providers/mock.py` (`bm-pm` branch, line 80)

**Interfaces:**
- Produces: `build_bm_pm_data(eqp_id: str, anchor: datetime) -> dict[str, object]` (signature change). Response shape unchanged. Rationale: the trend mocks generate inside the requested `[start, end]`, but BM/PM dates hang off a fixed `NOW = 2026-05-24` — with the page's default real-now window every overlay marker would fall outside the charts.

- [ ] **Step 1: Thread the anchor through `bm_pm_mock.py`**

Remove the module-level `NOW = datetime(2026, 5, 24, 9, 0)` and its comment. Update the three functions to take the anchor (every former `NOW` reference becomes `anchor`):

```python
def build_past_frame(eqp_id: str, rng: random.Random, anchor: datetime) -> pd.DataFrame:
    """Completed BM/PM jobs in the ~150 days before `anchor`, ts-desc."""
```

with `starts = anchor - timedelta(...)` (rest of the body unchanged), and:

```python
def build_future_frame(eqp_id: str, rng: random.Random, anchor: datetime) -> pd.DataFrame:
    """Planned BM/PM after `anchor` — few rows (plans change), ts-desc."""
```

with `starts = anchor + timedelta(...)` and `timestamp = anchor - timedelta(...)`, and:

```python
def build_bm_pm_data(eqp_id: str, anchor: datetime) -> dict[str, object]:
    """Deterministic past/future BM/PM records + summary cards for one tool.

    `anchor` is the requested window end — the same clock the trend-chart
    mocks generate against, so BM/PM overlay markers land inside chart
    ranges. Same (eqp_id, anchor) → same data.
    """
    rng = random.Random(_seed_for(eqp_id))
    past = build_past_frame(eqp_id, rng, anchor)
    future = build_future_frame(eqp_id, rng, anchor)
    return {
        "past": past.to_dict(orient="records"),
        "future": future.to_dict(orient="records"),
        "cards": _derive_cards(past, future),
    }
```

Also update the module docstring's anchor sentence: dates are deterministic per `(eqp_id, anchor)` rather than per fixed clock.

- [ ] **Step 2: Pass `end` in `mock.py`**

```python
    if service == "bm-pm":
        data = build_bm_pm_data(eqp_id, end)
```

- [ ] **Step 3: Verify**

```bash
.venv/bin/python -c "
from datetime import datetime, timedelta
from back_dev_home.ebeam.hitachi.hardware.providers.bm_pm_mock import build_bm_pm_data
end = datetime(2026, 7, 13, 9, 0)
a = build_bm_pm_data('ECX101', end)
b = build_bm_pm_data('ECX101', end)
assert a == b, 'not deterministic'
past = a['past']
assert len(past) >= 4, 'too few past rows'
for row in past:
    js = datetime.strptime(row['job_starts'], '%Y-%m-%d %H:%M')
    assert end - timedelta(days=151) <= js <= end, row
fut = a['future']
for row in fut:
    js = datetime.strptime(row['job_starts'], '%Y-%m-%d %H:%M')
    assert js > end, row
print('bm-pm anchor OK:', len(past), 'past /', len(fut), 'future rows')
"
```

Expected: `bm-pm anchor OK: ...`.

```bash
.venv/bin/python -c "
from datetime import datetime, timedelta
from back_dev_home.ebeam.hitachi.hardware.providers.mock import get_hardware_service
end = datetime(2026, 7, 13, 9, 0)
p = get_hardware_service('cdsem', 'bm-pm', 'ECX101', 'M16B', end - timedelta(days=30), end)
assert p['tables'][0]['key'] == 'past_work'
print('bm-pm payload OK:', len(p['tables'][0]['rows']), 'past rows')
"
```

Expected: `bm-pm payload OK: ...`.

- [ ] **Step 4: Commit**

```bash
git add back_dev_home/ebeam/hitachi/hardware
git commit -m "fix(ebeam): anchor BM/PM mock dates to the requested window end"
```

---

### Task 7: Pure util — `bmPmMarkers.ts` (events → markLine fragment)

**Files:**
- Create: `front-dev-home/app/utils/bmPmMarkers.ts`
- Test: `front-dev-home/app/utils/bmPmMarkers.test.ts`

**Interfaces:**
- Consumes: `HardwarePayload.tables` rows from the `bm-pm` service (Task 6 shape).
- Produces (Tasks 8–9 import these):

```ts
export interface BmPmEvent { ts: string, category: 'BM' | 'PM', jobEnd: string, note: string }
export const parseBmPmEvents: (tables: { key: string, rows: Record<string, unknown>[] }[]) => BmPmEvent[]
export const bmPmMarkLine: (events: BmPmEvent[], opts?: { dark?: boolean }) => BmPmMarkLine | undefined
```

- [ ] **Step 1: Write the failing test**

Create `front-dev-home/app/utils/bmPmMarkers.test.ts`:

```ts
// Pure-logic tests — run with: npm --prefix front-dev-home test
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { parseBmPmEvents, bmPmMarkLine } from './bmPmMarkers.ts'

const tables = [
  {
    key: 'past_work',
    rows: [
      { timestamp: '2026-07-01 12:30', eqp_id: 'ECX101', category: 'PM', job_starts: '2026-07-01 08:00', job_end: '2026-07-01 12:00', engr_note: '정기 점검.' },
      { timestamp: '2026-06-20 10:00', eqp_id: 'ECX101', category: 'BM', job_starts: '2026-06-20 07:00', job_end: '2026-06-20 09:30', engr_note: '<스테이지> 교체.' }
    ]
  },
  {
    key: 'future_work',
    rows: [
      { category: 'PM', job_starts: '2026-08-01 08:00', job_end: '2026-08-01 16:00', timestamp: '2026-07-10 09:00' }
    ]
  }
]

test('parseBmPmEvents: maps past_work rows only', () => {
  const events = parseBmPmEvents(tables)
  assert.equal(events.length, 2)
  assert.deepEqual(events[0], {
    ts: '2026-07-01 08:00',
    category: 'PM',
    jobEnd: '2026-07-01 12:00',
    note: '정기 점검.'
  })
})

test('parseBmPmEvents: unknown category or missing start → dropped', () => {
  const events = parseBmPmEvents([
    {
      key: 'past_work',
      rows: [
        { category: 'ETC', job_starts: '2026-07-01 08:00' },
        { category: 'BM', job_starts: '' },
        { category: 'BM', job_starts: '2026-07-02 08:00', job_end: '2026-07-02 10:00', engr_note: 'ok' }
      ]
    }
  ])
  assert.equal(events.length, 1)
  assert.equal(events[0]!.category, 'BM')
})

test('parseBmPmEvents: no past_work table → empty', () => {
  assert.deepEqual(parseBmPmEvents([]), [])
  assert.deepEqual(parseBmPmEvents([{ key: 'future_work', rows: [] }]), [])
})

test('bmPmMarkLine: one dashed vertical line per event at the job-start epoch', () => {
  const mk = bmPmMarkLine(parseBmPmEvents(tables))!
  assert.equal(mk.data.length, 2)
  assert.equal(mk.data[0]!.xAxis, new Date('2026-07-01T08:00').getTime())
  assert.equal(mk.data[0]!.label.formatter, 'PM')
  assert.equal(mk.lineStyle.type, 'dashed')
  assert.equal(mk.symbol, 'none')
})

test('bmPmMarkLine: BM/PM colors differ, and light/dark pairs differ', () => {
  const events = parseBmPmEvents(tables)
  const light = bmPmMarkLine(events)!
  const dark = bmPmMarkLine(events, { dark: true })!
  assert.notEqual(light.data[0]!.lineStyle.color, light.data[1]!.lineStyle.color)
  assert.notEqual(light.data[0]!.lineStyle.color, dark.data[0]!.lineStyle.color)
})

test('bmPmMarkLine: tooltip carries the job window and HTML-escaped note', () => {
  const mk = bmPmMarkLine(parseBmPmEvents(tables))!
  const bm = mk.data.find(d => d.label.formatter === 'BM')!
  assert.ok(bm.tooltip.formatter.includes('2026-06-20 07:00'))
  assert.ok(bm.tooltip.formatter.includes('&lt;스테이지&gt;'))
})

test('bmPmMarkLine: empty events → undefined', () => {
  assert.equal(bmPmMarkLine([]), undefined)
})
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
npm --prefix front-dev-home test 2>&1 | tail -5
```

Expected: FAIL — `Cannot find module ... bmPmMarkers.ts`.

- [ ] **Step 3: Implement**

Create `front-dev-home/app/utils/bmPmMarkers.ts`:

```ts
// Pure: turn BM/PM history rows into an ECharts markLine fragment — vertical
// dashed lines at each job start on any time-x-axis trend chart. BM/PM colors
// mirror the category chips on the BM/PM tab (rose = BM, emerald = PM).

export interface BmPmEvent {
  ts: string
  category: 'BM' | 'PM'
  jobEnd: string
  note: string
}

// The concrete fragment shape (structurally assignable to a line/scatter
// series `markLine` option) — concrete so tests can assert on fields.
export interface BmPmMarkLineData {
  xAxis: number
  name: 'BM' | 'PM'
  lineStyle: { color: string }
  label: { formatter: 'BM' | 'PM', color: string }
  tooltip: { formatter: string }
}

export interface BmPmMarkLine {
  silent: boolean
  symbol: 'none'
  animation: boolean
  lineStyle: { type: 'dashed', width: number }
  label: { show: boolean, position: 'end', fontSize: number, distance: number }
  data: BmPmMarkLineData[]
}

// rose-600 / emerald-600 on light, rose-400 / emerald-400 on dark.
const LINE_COLORS = {
  light: { BM: '#e11d48', PM: '#059669' },
  dark: { BM: '#fb7185', PM: '#34d399' }
} as const

interface TableSectionLike {
  key: string
  rows: Record<string, unknown>[]
}

export const parseBmPmEvents = (tables: TableSectionLike[]): BmPmEvent[] => {
  const past = tables.find(t => t.key === 'past_work')
  if (!past) return []
  const events: BmPmEvent[] = []
  for (const row of past.rows) {
    const category = row.category
    const ts = String(row.job_starts ?? '')
    if ((category !== 'BM' && category !== 'PM') || !ts) continue
    events.push({
      ts,
      category,
      jobEnd: String(row.job_end ?? ''),
      note: String(row.engr_note ?? '')
    })
  }
  return events
}

const toEpoch = (ts: string) => new Date(ts.replace(' ', 'T')).getTime()

const escapeHtml = (s: string) =>
  s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')

export const bmPmMarkLine = (
  events: BmPmEvent[],
  { dark = false }: { dark?: boolean } = {}
): BmPmMarkLine | undefined => {
  const colors = dark ? LINE_COLORS.dark : LINE_COLORS.light
  const data: BmPmMarkLineData[] = events
    .filter(e => Number.isFinite(toEpoch(e.ts)))
    .map(e => ({
      xAxis: toEpoch(e.ts),
      name: e.category,
      lineStyle: { color: colors[e.category] },
      label: { formatter: e.category, color: colors[e.category] },
      tooltip: {
        formatter: `<b>${e.category}</b> ${escapeHtml(e.ts)} ~ ${escapeHtml(e.jobEnd)}`
          + `<br/>${escapeHtml(e.note)}`
      }
    }))
  if (data.length === 0) return undefined
  return {
    silent: false,
    symbol: 'none',
    animation: false,
    lineStyle: { type: 'dashed', width: 1.2 },
    label: { show: true, position: 'end', fontSize: 9, distance: 2 },
    data
  }
}
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
npm --prefix front-dev-home test 2>&1 | tail -5
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add front-dev-home/app/utils/bmPmMarkers.ts front-dev-home/app/utils/bmPmMarkers.test.ts
git commit -m "feat(ebeam): add bmPmMarkers util building BM/PM markLine fragments"
```

---

### Task 8: Overlay wiring — HardwareView toggle/fetch + BSM · Sharpness · MDC charts

**Files:**
- Modify: `front-dev-home/app/components/ebeam/HardwareView.vue`
- Modify: `front-dev-home/app/components/ebeam/hardware/BsmTrendChart.vue`
- Modify: `front-dev-home/app/components/ebeam/hardware/BsmPanel.vue`
- Modify: `front-dev-home/app/components/ebeam/hardware/SharpnessPanel.vue`
- Modify: `front-dev-home/app/components/ebeam/hardware/MdcPanel.vue`

**Interfaces:**
- Consumes: `parseBmPmEvents`, `bmPmMarkLine`, `BmPmEvent` (Task 7); the anchored `bm-pm` payload (Task 6).
- Produces: `BsmTrendChart` gains `events?: BmPmEvent[]`; panels gain `maintenanceEvents?: BmPmEvent[]`; `HardwareView` exposes `overlayEvents` (empty array when the toggle is OFF). Task 9 reuses the same pattern for Reso/FDC.

- [ ] **Step 1: `BsmTrendChart.vue` — accept events, render markLine**

Add to the imports and props:

```ts
import { bmPmMarkLine, type BmPmEvent } from '~/utils/bmPmMarkers'
```

```ts
  // BM/PM maintenance timestamps drawn as vertical markLines (empty → none).
  events?: BmPmEvent[]
```

In the script body (after `const { palette } = ...`):

```ts
const colorMode = useColorMode()
```

In the single series inside `chartOption`, after `emphasis: { scale: 1.6 },` add:

```ts
      markLine: bmPmMarkLine(props.events ?? [], { dark: colorMode.value === 'dark' }),
```

Note: if `nuxt typecheck` rejects the fragment's structural type, coerce at this one site with `as LineSeriesOption['markLine']` (add `import type { LineSeriesOption } from 'echarts'`) — do not weaken the util's return type.

- [ ] **Step 2: `BsmPanel.vue` and `SharpnessPanel.vue` — pass-through prop**

In both files add to imports / props:

```ts
import type { BmPmEvent } from '~/utils/bmPmMarkers'
```

```ts
  maintenanceEvents?: BmPmEvent[]
```

And on every `<EbeamHardwareBsmTrendChart` usage in both templates add:

```vue
          :events="maintenanceEvents"
```

- [ ] **Step 3: `MdcPanel.vue` — same pass-through**

Add the same import + `maintenanceEvents?: BmPmEvent[]` prop, and `:events="maintenanceEvents"` on both `<EbeamHardwareBsmTrendChart` usages (0° and 90°).

- [ ] **Step 4: `HardwareView.vue` — fetch, toggle state, switch UI, plumbing**

Script additions (after the existing `useAsyncData` block):

```ts
import { parseBmPmEvents, type BmPmEvent } from '~/utils/bmPmMarkers'
```

```ts
// ---- BM/PM overlay (spec Part B) ----
// Tabs whose charts have a time x-axis; the toggle only shows there.
const OVERLAY_SERVICES: HardwareServiceKey[] = ['bsm', 'reso-center', 'mdc', 'fdc', 'sharpness']
// Page-scoped like `hw-section`: keeps its state across tab switches/visits.
const showBmPmOverlay = useState('hw-bmpm-overlay', () => true)
const overlayToggleVisible = computed(() => OVERLAY_SERVICES.includes(activeService.value))

// Second cached fetch of the existing bm-pm endpoint — events for whatever
// tab is active. Failure/empty just means no markers; charts are unaffected.
const { data: bmPmPayload } = await useAsyncData<HardwarePayload | null>(
  `hardware:bmpm-events:${props.toolType}:${props.fab}`,
  () => {
    const eqpId = selectedTool.value?.eqp_id
    if (!eqpId) return Promise.resolve(null)
    return fetchService({
      toolType: props.toolType,
      service: 'bm-pm',
      eqpId,
      fabName: selectedTool.value?.fab_name,
      start: windowStart.value,
      end: windowEnd.value
    })
  },
  { watch: [() => props.toolType, () => props.fab, () => selectedTool.value?.eqp_id] }
)

const overlayEvents = computed<BmPmEvent[]>(() =>
  showBmPmOverlay.value ? parseBmPmEvents(bmPmPayload.value?.tables ?? []) : []
)
```

Template — wrap the service-detail heading in a flex row and add the switch. Replace:

```vue
          <div class="min-w-0">
            <p class="font-mono text-[11px] font-semibold uppercase tracking-[0.08em] text-(--sk-ink-muted)">
              {{ activeServiceDetail.label }}
            </p>
            <h2 class="mt-1 text-lg font-bold text-(--sk-ink)">
              {{ activeServiceDetail.title }}
            </h2>
            <p class="mt-1 max-w-2xl text-sm text-(--sk-ink-muted)">
              {{ activeServiceDetail.description }}
            </p>
          </div>
```

with:

```vue
          <div class="flex items-start justify-between gap-3">
            <div class="min-w-0">
              <p class="font-mono text-[11px] font-semibold uppercase tracking-[0.08em] text-(--sk-ink-muted)">
                {{ activeServiceDetail.label }}
              </p>
              <h2 class="mt-1 text-lg font-bold text-(--sk-ink)">
                {{ activeServiceDetail.title }}
              </h2>
              <p class="mt-1 max-w-2xl text-sm text-(--sk-ink-muted)">
                {{ activeServiceDetail.description }}
              </p>
            </div>
            <!-- BM/PM 수직 마커 오버레이 on/off — 시간축 차트가 있는 탭에서만 -->
            <USwitch
              v-if="overlayToggleVisible"
              v-model="showBmPmOverlay"
              size="sm"
              label="BM/PM 표시"
              class="shrink-0"
            />
          </div>
```

Then pass events to the three panels that now accept them:

```vue
                <EbeamHardwareBsmPanel
                  v-if="activeService === 'bsm'"
                  :docs="servicePayload.docs ?? []"
                  :maintenance-events="overlayEvents"
                />
```

```vue
                <EbeamHardwareSharpnessPanel
                  v-else-if="activeService === 'sharpness'"
                  :docs="servicePayload.docs ?? []"
                  :maintenance-events="overlayEvents"
                />
```

```vue
                <EbeamHardwareMdcPanel
                  v-else-if="activeService === 'mdc'"
                  :settings="servicePayload.settings ?? {}"
                  :docs="servicePayload.docs ?? []"
                  :selected-eqp="selectedTool?.eqp_id ?? ''"
                  :maintenance-events="overlayEvents"
                />
```

- [ ] **Step 5: Verify**

```bash
npm --prefix front-dev-home test 2>&1 | tail -3
npm --prefix front-dev-home run typecheck
```

Expected: tests pass; typecheck exit 0.

- [ ] **Step 6: Commit**

```bash
git add front-dev-home/app/components/ebeam/HardwareView.vue front-dev-home/app/components/ebeam/hardware/BsmTrendChart.vue front-dev-home/app/components/ebeam/hardware/BsmPanel.vue front-dev-home/app/components/ebeam/hardware/SharpnessPanel.vue front-dev-home/app/components/ebeam/hardware/MdcPanel.vue
git commit -m "feat(ebeam): BM/PM overlay toggle + markers on BSM/Sharpness/MDC trend charts"
```

---

### Task 9: Overlay wiring — Reso Center + FDC time charts

**Files:**
- Modify: `front-dev-home/app/components/ebeam/hardware/ResoCenterPanel.vue`
- Modify: `front-dev-home/app/components/ebeam/hardware/FdcPanel.vue`
- Modify: `front-dev-home/app/components/ebeam/HardwareView.vue` (pass the prop)

**Interfaces:**
- Consumes: `bmPmMarkLine`, `BmPmEvent` (Task 7); `overlayEvents` (Task 8).
- Produces: both panels accept `maintenanceEvents?: BmPmEvent[]`. Time-axis charts only: Reso best-reso trend; FDC LaserPower + TemperatureEchuck. The Reso drift scatter / focus sweep and FDC SPMVoltages / ContactpinConductionInfo have no time axis — leave untouched.

- [ ] **Step 1: `ResoCenterPanel.vue`**

Imports + props:

```ts
import { bmPmMarkLine, type BmPmEvent } from '~/utils/bmPmMarkers'
```

```ts
const props = defineProps<{
  docs: Record<string, unknown>[]
  maintenanceEvents?: BmPmEvent[]
}>()
```

Script body (near the palette setup):

```ts
const colorMode = useColorMode()
const maintenanceMarkLine = computed(() =>
  bmPmMarkLine(props.maintenanceEvents ?? [], { dark: colorMode.value === 'dark' })
)
```

In `trendOption`, add to the **first** series (BestReso) after its `data:` line:

```ts
        markLine: maintenanceMarkLine.value
```

- [ ] **Step 2: `FdcPanel.vue`**

Same import; props become:

```ts
const props = defineProps<{
  docs: Record<string, unknown>[]
  maintenanceEvents?: BmPmEvent[]
}>()
```

Same `colorMode` + `maintenanceMarkLine` computed as Step 1.

LaserPower branch — add to the first series (`name: 'pair 1 (x)'`):

```ts
        { name: 'pair 1 (x)', type: 'line', yAxisIndex: 0, lineStyle: { color: c0.value }, itemStyle: { color: c0.value }, data: pair(0), markLine: maintenanceMarkLine.value },
```

TemperatureEchuck branch — attach to the first position series only:

```ts
    series: Object.keys(byPos).sort().map((pos, i) => ({
      name: `pos ${pos}`, type: 'line', showSymbol: true,
      lineStyle: { color: colors[i % colors.length] }, itemStyle: { color: colors[i % colors.length] },
      data: byPos[pos]!.map(r => ({ name: r.ts, value: [toEpoch(r.ts), r.temp] })),
      ...(i === 0 ? { markLine: maintenanceMarkLine.value } : {})
    }))
```

The SPMVoltages branch is category-axis — no change.

- [ ] **Step 3: Pass the prop from `HardwareView.vue`**

```vue
                <EbeamHardwareResoCenterPanel
                  v-else-if="activeService === 'reso-center'"
                  :docs="servicePayload.docs ?? []"
                  :maintenance-events="overlayEvents"
                />
```

```vue
                <EbeamHardwareFdcPanel
                  v-else-if="activeService === 'fdc'"
                  :docs="servicePayload.docs ?? []"
                  :maintenance-events="overlayEvents"
                />
```

- [ ] **Step 4: Verify**

```bash
npm --prefix front-dev-home test 2>&1 | tail -3
npm --prefix front-dev-home run typecheck
```

Expected: tests pass; typecheck exit 0.

- [ ] **Step 5: Commit**

```bash
git add front-dev-home/app/components/ebeam/hardware/ResoCenterPanel.vue front-dev-home/app/components/ebeam/hardware/FdcPanel.vue front-dev-home/app/components/ebeam/HardwareView.vue
git commit -m "feat(ebeam): BM/PM overlay markers on Reso Center and FDC time charts"
```

---

### Task 10: End-to-end verification (browser)

**Files:**
- No code changes expected; fix-forward anything found (small fixes fold into this task's commit).

- [ ] **Step 1: Full test + typecheck + markdown lint**

```bash
npm --prefix front-dev-home test 2>&1 | tail -3
npm --prefix front-dev-home run typecheck
npm run lint:md
```

Expected: tests all pass (baseline 127 − 5 mdcMatrix + 19 new ≈ 141), typecheck exit 0, no new lint errors on the two new docs.

- [ ] **Step 2: Start both dev servers (skip any already running)**

```bash
PORT=5000 .venv/bin/python index.py   # Flask mock, background
npm --prefix front-dev-home run dev   # Nuxt on :3000, background
```

- [ ] **Step 3: Browser checklist — MDC tab** (`http://localhost:3000/ebeam/cd-sem/M16/hardware`, then the MDC pill)

- 시계열 sub-tab is the default; family chips show (800V_HR, 500V_HR, extras per tool).
- Paired family: square trajectory chart with fading older points, emphasized latest point, gray crosshair at (1.0, 1.0); two per-axis trend charts with **visible** drift (tight y-axis, not a flat line).
- Unpaired family (pick a tool with `Valley`): single trend, no trajectory.
- 비교 sub-tab: one box per condition, diamond marker for the selected tool, tooltip shows the five stats; no matrix table anywhere.

- [ ] **Step 4: Browser checklist — BM/PM overlay**

- Toggle "BM/PM 표시" appears on BSM / Reso Center / MDC / FDC / Sharpness, and NOT on BM/PM or SCE.
- With the toggle ON: dashed vertical lines with `BM`(rose)/`PM`(emerald) top labels on — BSM trends, Sharpness trends, Reso BestReso·ResoDelta trend, FDC LaserPower + TemperatureEchuck trends, MDC 0°/90° trends. Line dates match the BM/PM tab's past-work table for the same tool.
- Hovering a line shows category, `job_starts ~ job_end`, and the engineer note.
- dataZoom drag: lines stay pinned to their dates.
- Toggle OFF: all lines disappear on every tab; switch tabs and back — the OFF state persists.
- Dark mode: line colors switch to the lighter rose/emerald pair and stay legible.

- [ ] **Step 5: Commit any verification fixes**

```bash
git status --short   # if fixes were needed:
git add -A front-dev-home back_dev_home && git commit -m "fix(ebeam): polish from MDC/BM-PM overlay browser verification"
```

---

## Self-review notes (already applied)

- Spec A3/A4/A5 → Tasks 1/4/5; B2–B4 → Tasks 7/8/9; the bm-pm anchor fix (spec B3) → Task 6; spec B6 tests → Tasks 2/3/7 + Task 10.
- `stableYRange` deliberately bypassed for MDC (`yMode="tight"`, `scale: true`) — see Global Constraints and the spec's A4 note.
- `maintenanceEvents` prop name is identical across all five panels; the chart-level prop is `events`.
- `mdcMatrix.ts` deletion happens only after the boxplot replaces its last consumer (Task 5), keeping every task green.
