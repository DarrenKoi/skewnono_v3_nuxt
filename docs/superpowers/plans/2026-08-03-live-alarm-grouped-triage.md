# Live Alarm Grouped Triage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a three-way kind filter to the 라이브 알람 board and, in the
측정 실패 mode, group alarms by `(eqp_id, ppid)` sorted by 건수 so a PPID that
is failing repeatedly on one tool is the first thing on screen.

**Architecture:** Frontend only. The server already ships a complete 10-minute
board on every poll and `applyPoll` replaces rather than merges, so grouping is
a pure derived view over the existing `events` array — no contract change, no
new accumulated state. Logic lives in pure functions in `app/utils/liveAlarm.ts`
(testable under `node --test`); the Vue components only display.

**Tech Stack:** Nuxt 4 SPA (`ssr: false`), NuxtUI 4.10, TypeScript,
`node --test` for pure-function tests, `usePersistedState` for localStorage.

Spec: `docs/superpowers/specs/2026-08-03-live-alarm-grouped-triage-design.md`

## Global Constraints

- **Frontend only.** Do not touch `back_dev_home/`, `contracts.py`, or the
  response payload. The 10-minute horizon (`BOARD_WINDOW_SEC = 600`) stays.
- **Do not modify `app/components/live-alarm/AlarmRow.vue`.** It is reused
  verbatim inside groups.
- **Colors come from `--sk-*` tokens only, never inline hex.** `DESIGN.md` is
  the source of truth for the visual language.
- **No `UButtonGroup`** — it does not exist in NuxtUI 4.10. The repo's
  precedent for a segmented control is a hand-rolled `role="tablist"` with
  roving tabindex; see `app/components/ebeam/skewvoir/views/TimeSeries.vue`
  lines 56-88 and 368-384.
- **Pure functions import with the `.ts` extension and no `~/` alias.**
  `app/utils/liveAlarm.ts` is loaded directly by `node --test`, which has no
  Nuxt build step to resolve `~`. See the comment atop `useLiveAlarmFeed.ts`.
- **Korean UI copy** uses the existing board's register (`최근 10분간 알람이
  없습니다.`). Comments in code are English, matching the surrounding files.
- **Never stage broadly.** Every commit passes explicit pathspecs
  (`git commit -- path/a path/b`). `git add -A` / `git add .` / `git commit -a`
  are banned in this repo.
- Work happens in `front-dev-home/`; all `npm` commands below run from there
  unless stated otherwise.

---

### Task 1: Pure filter and grouping functions

**Files:**

- Modify: `front-dev-home/app/utils/liveAlarm.ts` (append after
  `distinctLotCount`, line 93)
- Test: `front-dev-home/app/utils/liveAlarm.test.ts` (append)

**Interfaces:**

- Consumes: `LiveAlarmEvent` and `distinctLotCount` from the same module;
  `makeAlarmEvent` from `./liveAlarm.fixtures.ts` (test only).
- Produces:
  - `type AlarmFilter = 'all' | 'align' | 'meas'`
  - `interface MeasGroupItem { key: string; eqpId: string; ppidLabel: string;
    count: number; latestEpoch: number; lotCount: number;
    events: LiveAlarmEvent[] }`
  - `filterEvents(events: LiveAlarmEvent[], filter: AlarmFilter):
    LiveAlarmEvent[]`
  - `groupMeasEvents(events: LiveAlarmEvent[]): MeasGroupItem[]`
  - `const NO_PPID_LABEL = '(PPID 없음)'`

- [ ] **Step 1: Write the failing tests**

Append to `front-dev-home/app/utils/liveAlarm.test.ts`:

```ts
describe('filterEvents', () => {
  const events = [event('a', 'align'), event('m', 'meas'), event('b', 'align')]

  it('returns every event unchanged for "all"', () => {
    assert.deepEqual(filterEvents(events, 'all'), events)
  })

  it('keeps only align events for "align"', () => {
    assert.deepEqual(filterEvents(events, 'align').map(e => e.id), ['a', 'b'])
  })

  it('keeps only meas events for "meas"', () => {
    assert.deepEqual(filterEvents(events, 'meas').map(e => e.id), ['m'])
  })

  it('returns an empty array rather than throwing on an empty board', () => {
    assert.deepEqual(filterEvents([], 'meas'), [])
  })
})

describe('groupMeasEvents', () => {
  const meas = (over: Partial<LiveAlarmEvent>) =>
    makeAlarmEvent({ kind: 'meas', alid: '9007', ...over })

  it('ignores align events entirely', () => {
    assert.deepEqual(groupMeasEvents([makeAlarmEvent({ kind: 'align' })]), [])
  })

  it('groups by eqp_id and ppid together, not either alone', () => {
    const groups = groupMeasEvents([
      meas({ id: '1', eqp_id: 'EQ1', ppid: 'R_A' }),
      meas({ id: '2', eqp_id: 'EQ1', ppid: 'R_B' }),
      meas({ id: '3', eqp_id: 'EQ2', ppid: 'R_A' })
    ])
    assert.deepEqual(groups.map(g => g.key), ['EQ1|R_A', 'EQ1|R_B', 'EQ2|R_A'])
  })

  it('sorts by count descending so the worst offender is first', () => {
    const groups = groupMeasEvents([
      meas({ id: '1', eqp_id: 'EQ1', ppid: 'ONCE' }),
      meas({ id: '2', eqp_id: 'EQ2', ppid: 'TWICE' }),
      meas({ id: '3', eqp_id: 'EQ2', ppid: 'TWICE' })
    ])
    assert.deepEqual(groups.map(g => g.count), [2, 1])
    assert.equal(groups[0]?.key, 'EQ2|TWICE')
  })

  it('breaks a count tie by most recent occurrence', () => {
    const groups = groupMeasEvents([
      meas({ id: '1', eqp_id: 'EQ1', ppid: 'OLD', occurred_epoch: 100 }),
      meas({ id: '2', eqp_id: 'EQ2', ppid: 'NEW', occurred_epoch: 500 })
    ])
    assert.deepEqual(groups.map(g => g.key), ['EQ2|NEW', 'EQ1|OLD'])
  })

  it('orders events inside a group newest first', () => {
    const groups = groupMeasEvents([
      meas({ id: 'old', eqp_id: 'EQ1', ppid: 'R', occurred_epoch: 10 }),
      meas({ id: 'new', eqp_id: 'EQ1', ppid: 'R', occurred_epoch: 90 })
    ])
    assert.deepEqual(groups[0]?.events.map(e => e.id), ['new', 'old'])
    assert.equal(groups[0]?.latestEpoch, 90)
  })

  it('buckets a blank ppid under a label instead of dropping it', () => {
    const groups = groupMeasEvents([meas({ id: '1', eqp_id: 'EQ1', ppid: '' })])
    assert.equal(groups[0]?.key, 'EQ1|')
    assert.equal(groups[0]?.ppidLabel, '(PPID 없음)')
    assert.equal(groups[0]?.count, 1)
  })

  it('counts distinct lots, ignoring blanks', () => {
    const groups = groupMeasEvents([
      meas({ id: '1', eqp_id: 'EQ1', ppid: 'R', lot_id: 'L1' }),
      meas({ id: '2', eqp_id: 'EQ1', ppid: 'R', lot_id: 'L1' }),
      meas({ id: '3', eqp_id: 'EQ1', ppid: 'R', lot_id: 'L2' }),
      meas({ id: '4', eqp_id: 'EQ1', ppid: 'R', lot_id: '' })
    ])
    assert.equal(groups[0]?.count, 4)
    assert.equal(groups[0]?.lotCount, 2)
  })
})
```

Extend the existing import line at the top of the file to pull in the new
functions and the type:

```ts
import {
  diffNewIds, formatElapsed, boardCounts, distinctLotCount,
  filterEvents, groupMeasEvents
} from './liveAlarm.ts'
import type { LiveAlarmEvent } from './liveAlarm.ts'
```

- [ ] **Step 2: Run the tests to verify they fail**

Run from `front-dev-home/`:

```bash
npm test
```

Expected: FAIL — `SyntaxError: The requested module './liveAlarm.ts' does not
provide an export named 'filterEvents'`.

- [ ] **Step 3: Write the implementation**

Append to `front-dev-home/app/utils/liveAlarm.ts`:

```ts
// Which kinds the board is showing. 'all' is the default and renders the
// flat chronological list this board has always had; the other two are
// triage modes. Persisted per viewer — see composables/useLiveAlarmFilter.ts.
export type AlarmFilter = 'all' | 'align' | 'meas'

export const filterEvents = (
  events: LiveAlarmEvent[],
  filter: AlarmFilter
): LiveAlarmEvent[] =>
  filter === 'all' ? events : events.filter(e => e.kind === filter)

// Shown in place of a blank ppid. The server sends "" for an absent value
// rather than omitting the key, so a blank is a value we can group on — and
// dropping those alarms would silently shrink the board.
export const NO_PPID_LABEL = '(PPID 없음)'

// One (eqp_id, ppid) pile of measurement failures. `key` is derived from the
// pair rather than from an array index because applyPoll replaces the whole
// events array every 15 seconds: a positional key would reset each group's
// expand/collapse state on every poll.
export interface MeasGroupItem {
  key: string
  eqpId: string
  ppidLabel: string
  count: number
  latestEpoch: number
  lotCount: number
  // Newest first, so an expanded group reads the same direction as the board.
  events: LiveAlarmEvent[]
}

// Groups measurement failures so a PPID failing over and over on one tool
// reads as one loud row instead of scattering across a chronological list.
// Align events are dropped here rather than by the caller: this function is
// only ever correct for meas, so making it total is safer than trusting every
// call site to pre-filter.
export const groupMeasEvents = (events: LiveAlarmEvent[]): MeasGroupItem[] => {
  const buckets = new Map<string, LiveAlarmEvent[]>()
  for (const event of events) {
    if (event.kind !== 'meas') continue
    const key = `${event.eqp_id}|${event.ppid}`
    const bucket = buckets.get(key)
    if (bucket) bucket.push(event)
    else buckets.set(key, [event])
  }

  return [...buckets.entries()]
    .map(([key, bucketEvents]) => {
      const sorted = [...bucketEvents].sort(
        (a, b) => b.occurred_epoch - a.occurred_epoch
      )
      const first = sorted[0]
      return {
        key,
        eqpId: first?.eqp_id ?? '',
        ppidLabel: first?.ppid || NO_PPID_LABEL,
        count: sorted.length,
        latestEpoch: first?.occurred_epoch ?? 0,
        lotCount: distinctLotCount(sorted),
        events: sorted
      }
    })
    // Count first, because the whole point of this view is volume; recency
    // only breaks ties, and the key breaks those, so the order is stable
    // across polls that carry identical data.
    .sort((a, b) =>
      b.count - a.count
      || b.latestEpoch - a.latestEpoch
      || a.key.localeCompare(b.key)
    )
}
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
npm test
```

Expected: PASS, with no regressions in the existing `diffNewIds`,
`formatElapsed`, `boardCounts`, `distinctLotCount` suites.

- [ ] **Step 5: Typecheck and lint**

```bash
npm run typecheck
npm run lint
```

Expected: both clean.

- [ ] **Step 6: Commit**

```bash
git add app/utils/liveAlarm.ts app/utils/liveAlarm.test.ts
git commit -m "feat(live-alarm): add kind filter and meas grouping helpers

groupMeasEvents piles measurement failures by (eqp_id, ppid) and sorts by
count, so a PPID failing repeatedly on one tool becomes one loud row instead
of scattering across the chronological board. Keyed by the pair rather than
by index because applyPoll replaces the array every poll.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Persisted filter composable

**Files:**

- Create: `front-dev-home/app/composables/useLiveAlarmFilter.ts`

**Interfaces:**

- Consumes: `AlarmFilter` from `~/utils/liveAlarm` (Task 1); `usePersistedState`
  from `app/composables/usePersistedState.ts` (auto-imported by Nuxt).
- Produces: `useLiveAlarmFilter(): Ref<AlarmFilter>`

There is no test step here. The repo has no component or composable mounting
harness — `npm test` covers pure functions only, and this file is nine lines of
`usePersistedState` configuration whose behaviour is verified in Task 5's
browser pass (reload keeps the choice). Adding a fake-localStorage harness for
it would be more machinery than the code it guards.

- [ ] **Step 1: Write the composable**

Create `front-dev-home/app/composables/useLiveAlarmFilter.ts`:

```ts
// Which alarm kinds the 라이브 알람 board is showing.
//
// One key across every fab and tool, deliberately: a viewer is doing align
// triage or PPID triage today, not choosing a different lens per fab. Twenty
// per-fab keys would be twenty things to keep in sync for a preference that is
// really about the person, not the fab.
//
// Persisted rather than component-local because the board unmounts on every
// fab switch, and re-picking the mode after each navigation is exactly the
// friction this control is meant to remove.
import type { AlarmFilter } from '~/utils/liveAlarm'

const VALID: AlarmFilter[] = ['all', 'align', 'meas']

export const useLiveAlarmFilter = () =>
  usePersistedState<AlarmFilter>(
    'live-alarm:filter',
    'skewnono:live-alarm.filter',
    {
      default: () => 'all',
      // Anything else in storage — a stale value from a future rename, or a
      // hand-edited key — falls back to the default rather than rendering a
      // board with no matching mode.
      normalize: parsed =>
        VALID.includes(parsed as AlarmFilter) ? (parsed as AlarmFilter) : 'all',
      // 'all' is the default, so storage only ever holds the deviation from
      // it: switching back to 전부 보기 drops the key instead of writing it.
      isEmpty: value => value === 'all'
    }
  )
```

- [ ] **Step 2: Typecheck and lint**

```bash
npm run typecheck
npm run lint
```

Expected: both clean. (Nuxt auto-imports `usePersistedState` and `Ref`; if
typecheck reports `usePersistedState` as undefined, run `npm run postinstall`
to regenerate `.nuxt` types before investigating further.)

- [ ] **Step 3: Commit**

```bash
git add app/composables/useLiveAlarmFilter.ts
git commit -m "feat(live-alarm): persist the board's kind filter

One key across every fab and tool: the choice tracks what the viewer is doing
today, not which fab they are looking at. 'all' is treated as empty so the
default never lingers in localStorage.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: MeasGroup component

**Files:**

- Create: `front-dev-home/app/components/live-alarm/MeasGroup.vue`

**Interfaces:**

- Consumes: `MeasGroupItem`, `formatElapsed` from `~/utils/liveAlarm` (Task 1);
  the existing `LiveAlarmRow` component (`app/components/live-alarm/AlarmRow.vue`,
  unmodified).
- Produces: component auto-imported as `<LiveAlarmMeasGroup>` with props
  `group: MeasGroupItem`, `serverOffsetMs: number`, `highlightIds: string[]`,
  `toolSlug: string`, `fab: string`.

Note the auto-import name: Nuxt prefixes with the directory, so
`components/live-alarm/MeasGroup.vue` is `<LiveAlarmMeasGroup>` — the same rule
that makes `AlarmRow.vue` render as `<LiveAlarmRow>` in `LiveAlarmView.vue`.

The single-event case is handled **inside** this component rather than branched
in the view: a group header wrapping one row is noise, but making the caller
know that is leaking the rule into two places.

- [ ] **Step 1: Write the component**

Create `front-dev-home/app/components/live-alarm/MeasGroup.vue`:

```vue
<script setup lang="ts">
import { formatElapsed } from '~/utils/liveAlarm'
import type { MeasGroupItem } from '~/utils/liveAlarm'

const props = defineProps<{
  group: MeasGroupItem
  serverOffsetMs: number
  highlightIds: string[]
  toolSlug: string
  fab: string
}>()

// Component-local, and it survives polling: the parent keys the v-for by
// group.key, which is derived from (eqp_id, ppid) rather than from an index,
// so Vue reuses this instance instead of remounting it every 15 seconds.
const expanded = ref(false)

const highlightSet = computed(() => new Set(props.highlightIds))

// A one-event group renders as a bare row — a header, a chevron and a "1건"
// badge around a single alarm is furniture, not information.
const isSingleton = computed(() => props.group.count === 1)

// Lifted from the row to the header on purpose. The row-level highlight fires
// into collapsed (invisible) DOM, so without this the arrival of a new alarm
// is silent exactly when the pile-up is worth noticing.
const hasNew = computed(() =>
  props.group.events.some(event => highlightSet.value.has(event.id))
)

const elapsed = computed(() =>
  formatElapsed(Date.now() + props.serverOffsetMs - props.group.latestEpoch * 1000)
)
</script>

<template>
  <LiveAlarmRow
    v-if="isSingleton && group.events[0]"
    :event="group.events[0]"
    :server-offset-ms="serverOffsetMs"
    :is-new="highlightSet.has(group.events[0].id)"
    :tool-slug="toolSlug"
    :fab="fab"
  />

  <div
    v-else
    class="border-b border-default last:border-b-0"
  >
    <button
      type="button"
      class="flex w-full flex-wrap items-center gap-x-4 gap-y-1 px-4 py-3 text-left transition-colors duration-1000"
      :class="hasNew ? 'bg-(--sk-accent-tint)' : 'bg-transparent'"
      :aria-expanded="expanded"
      @click="expanded = !expanded"
    >
      <UIcon
        :name="expanded ? 'i-lucide-chevron-down' : 'i-lucide-chevron-right'"
        class="size-4 shrink-0 text-(--sk-ink-muted)"
      />

      <span class="text-lg font-semibold tracking-tight">{{ group.eqpId }}</span>
      <span class="font-mono text-sm text-(--sk-ink-muted)">{{ group.ppidLabel }}</span>

      <!-- The count is the argument this whole view exists to make, so it is
           the loudest thing in the header. -->
      <span class="text-lg font-semibold text-(--sk-warn)">{{ group.count }}건</span>

      <span class="text-sm text-muted">{{ elapsed }}</span>
      <span class="ml-auto sk-meta">관련 lot {{ group.lotCount }}</span>
    </button>

    <div v-if="expanded">
      <LiveAlarmRow
        v-for="event in group.events"
        :key="event.id"
        :event="event"
        :server-offset-ms="serverOffsetMs"
        :is-new="highlightSet.has(event.id)"
        :tool-slug="toolSlug"
        :fab="fab"
      />
    </div>
  </div>
</template>
```

- [ ] **Step 2: Confirm the icons are bundled**

This project bundles a fixed Lucide subset for offline Windows use rather than
resolving icon names at runtime. Check that both chevrons are present:

```bash
grep -rn "chevron-down\|chevron-right" app.config.ts nuxt.config.ts app/ | head
```

If `i-lucide-chevron-right` is not among the bundled icons, use
`i-lucide-chevron-down` for both states and rotate the collapsed one with
`class="-rotate-90"` rather than adding a new icon to the bundle.

- [ ] **Step 3: Typecheck and lint**

```bash
npm run typecheck
npm run lint
```

Expected: both clean. `npm test` is unaffected (no pure functions changed) but
run it anyway to confirm nothing regressed.

- [ ] **Step 4: Commit**

```bash
git add app/components/live-alarm/MeasGroup.vue
git commit -m "feat(live-alarm): add the meas-fail group row

Header carries eqp_id, ppid, count, recency and lot count; expanding reveals
the existing AlarmRow list unchanged. The new-arrival highlight is lifted from
the row to the header because a collapsed group would otherwise flash into
invisible DOM. A one-event group renders as a bare row — a header around one
alarm is furniture.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Wire the filter into LiveAlarmView

**Files:**

- Modify: `front-dev-home/app/components/ebeam/LiveAlarmView.vue`

**Interfaces:**

- Consumes: `filterEvents`, `groupMeasEvents`, `AlarmFilter` from
  `~/utils/liveAlarm` (Task 1); `useLiveAlarmFilter` (Task 2);
  `<LiveAlarmMeasGroup>` (Task 3).
- Produces: nothing consumed by later tasks.

The header stats stay exactly as they are — `boardCounts(events.value)` over
the **unfiltered** board. Do not switch them to the filtered list: hiding align
counts while someone does PPID triage is the one thing this filter must not do.

- [ ] **Step 1: Extend the script block**

In `front-dev-home/app/components/ebeam/LiveAlarmView.vue`, change the import on
line 5 and add the filter state after `const counts = ...` (line 19):

```ts
import { boardCounts, distinctLotCount, formatElapsed, filterEvents, groupMeasEvents } from '~/utils/liveAlarm'
import type { AlarmFilter } from '~/utils/liveAlarm'
```

Then, after `const counts = computed(() => boardCounts(events.value))`:

```ts
const filter = useLiveAlarmFilter()

const FILTERS: { value: AlarmFilter, label: string }[] = [
  { value: 'all', label: '전부 보기' },
  { value: 'align', label: 'Align Fail만' },
  { value: 'meas', label: '측정 실패만' }
]
const FILTER_ORDER: AlarmFilter[] = FILTERS.map(f => f.value)

// The flat list, used by 'all' and 'align'. 'meas' renders groups instead, so
// this stays empty there rather than carrying a list nothing reads.
const visibleEvents = computed(() =>
  filter.value === 'meas' ? [] : filterEvents(events.value, filter.value)
)
const measGroups = computed(() =>
  filter.value === 'meas' ? groupMeasEvents(events.value) : []
)
const hasRows = computed(() => visibleEvents.value.length > 0 || measGroups.value.length > 0)

// Per-mode, because "이 팹은 조용하다" and "이 필터에 해당하는 것이 없다" are
// different facts and a single sentence can only claim one of them.
const emptyMessage = computed(() => ({
  all: '최근 10분간 알람이 없습니다.',
  align: '최근 10분간 Align 실패가 없습니다.',
  meas: '최근 10분간 측정 실패가 없습니다.'
}[filter.value]))

// Roving tabindex, mirroring TimeSeries.vue's lens switch: arrow keys move the
// selection and take focus with it, so the strip is one tab stop, not three.
const filterTabsEl = ref<HTMLElement | null>(null)
const tabId = (value: AlarmFilter) => `live-alarm-filter-${value}`

const onFilterKeydown = (event: KeyboardEvent): void => {
  const current = FILTER_ORDER.indexOf(filter.value)
  let next = current

  if (event.key === 'ArrowLeft') next = (current - 1 + FILTER_ORDER.length) % FILTER_ORDER.length
  else if (event.key === 'ArrowRight') next = (current + 1) % FILTER_ORDER.length
  else if (event.key === 'Home') next = 0
  else if (event.key === 'End') next = FILTER_ORDER.length - 1
  else return

  event.preventDefault()
  const target = FILTER_ORDER[next] ?? 'all'
  filter.value = target
  nextTick(() => {
    filterTabsEl.value?.querySelector<HTMLButtonElement>(`#${tabId(target)}`)?.focus()
  })
}
```

- [ ] **Step 2: Add the tablist to the template**

Insert between the `<UAlert v-if="error" …/>` block and the
`<div class="dashboard-surface …">` board:

```vue
    <div
      ref="filterTabsEl"
      role="tablist"
      aria-label="알람 종류 필터"
      class="inline-flex w-fit items-center gap-0.5 rounded-(--sk-r-chip) bg-(--sk-chip-bg) p-0.5"
      @keydown="onFilterKeydown"
    >
      <button
        v-for="option in FILTERS"
        :id="tabId(option.value)"
        :key="option.value"
        type="button"
        role="tab"
        :tabindex="filter === option.value ? 0 : -1"
        :aria-selected="filter === option.value"
        class="rounded-[6px] px-3 py-1.5 text-xs font-medium transition-colors"
        :class="filter === option.value
          ? 'bg-(--sk-surface) text-(--sk-ink) shadow-sm'
          : 'text-(--sk-ink-muted) hover:text-(--sk-ink)'"
        @click="filter = option.value"
      >
        {{ option.label }}
      </button>
    </div>
```

There is no `aria-controls` / `role="tabpanel"` pairing here, unlike
`TimeSeries.vue`: the board below is one region that all three tabs share, and
pointing three tabs at one panel misdescribes the relationship. The
`aria-label` on the tablist is what names the control.

- [ ] **Step 3: Replace the board body**

Replace the `<template v-else-if="events.length">` block (lines 101-111) and the
empty-state paragraph (lines 119-124) with:

```vue
      <template v-else-if="hasRows">
        <LiveAlarmRow
          v-for="event in visibleEvents"
          :key="event.id"
          :event="event"
          :server-offset-ms="serverOffsetMs"
          :is-new="highlightSet.has(event.id)"
          :tool-slug="toolType"
          :fab="fabSlug"
        />
        <LiveAlarmMeasGroup
          v-for="group in measGroups"
          :key="group.key"
          :group="group"
          :server-offset-ms="serverOffsetMs"
          :highlight-ids="highlightIds"
          :tool-slug="toolType"
          :fab="fabSlug"
        />
      </template>

      <AppLoadingState
        v-else-if="!hasLoaded"
        variant="inline"
        title="라이브 알람 피드를 불러오는 중입니다."
      />

      <p
        v-else
        class="px-4 py-10 text-center sk-body text-(--sk-ink-muted)"
      >
        {{ emptyMessage }}
      </p>
```

The `v-if="feedStatus === 'not_configured'"` branch above it is untouched and
still wins: a fab that is not collected says so regardless of the filter,
because that is true in all three modes.

- [ ] **Step 4: Check the outer click handler still behaves**

The root `<div @click="markSeen">` acknowledges the unread count on any click.
Clicking a group header therefore both expands the group and marks the board
seen. That is correct — the viewer did look — so no change is needed. Confirm
by reading the template that no `.stop` modifier was introduced in Task 3.

- [ ] **Step 5: Typecheck, lint, test**

```bash
npm test
npm run typecheck
npm run lint
```

Expected: all three clean.

- [ ] **Step 6: Commit**

```bash
git add app/components/ebeam/LiveAlarmView.vue
git commit -m "feat(live-alarm): put the kind filter on the board

전부 보기 keeps today's flat chronological list; Align Fail만 filters it; 측정
실패만 switches to (eqp_id, ppid) groups sorted by count. Header stats stay on
the full board in every mode — a filter that also shrank the counters would
hide align failures from someone doing PPID triage.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: Browser verification

**Files:** none modified. Screenshots land in `.playwright-mcp/screenshots/`
(gitignored).

**Interfaces:**

- Consumes: everything from Tasks 1-4.
- Produces: a verification record in the final response, not a file.

This project has no automated E2E suite — no Playwright config, no component
mounting harness. Browser verification means driving Playwright MCP by hand.
See the `verify` skill for the launch recipe.

- [ ] **Step 1: Start both servers**

From the repo root:

```bash
.venv/bin/python index.py
```

From `front-dev-home/` in a second shell:

```bash
npm run dev
```

Flask listens on `:5050`, Nuxt on `:3000` and proxies `/api/*` to Flask. If
every route renders blank with no console errors, Flask is down — check `:5050`
before suspecting a component.

- [ ] **Step 2: Verify the three modes on cd-sem**

Navigate to `http://localhost:3000/ebeam/cd-sem/M16A/live-alarm` and confirm:

1. `전부 보기` is selected on first visit and renders the flat mixed list.
2. `Align Fail만` shows only rows with the `Align Fail` badge.
3. `측정 실패만` shows group headers, and the top group's 건수 is the largest
   on screen (verify by reading the counts down the list).
4. A group with 건수 1 renders as a bare `AlarmRow` — no chevron, no header.
5. If the mock produces one, a `(PPID 없음)` group is present rather than
   measurement alarms silently going missing. Cross-check by comparing the sum
   of all group 건수 against the `측정 실패` number in the header bar; they must
   be equal.

Screenshot each mode to
`.playwright-mcp/screenshots/live-alarm-filter-<mode>.png`.

- [ ] **Step 3: Verify header stats ignore the filter**

With `측정 실패만` selected, confirm the `Align Fail` stat in `EbeamMetaBar`
still shows the full-board align count (non-zero if any align alarms exist).
This is the spec's §3.3 requirement and the easiest thing to get wrong.

- [ ] **Step 4: Verify expand/collapse survives a poll**

In `측정 실패만`, expand a group and wait **20 seconds** (the poll interval is
15s ± 3s jitter). Confirm the group is still expanded afterwards. If it
collapses, the `v-for` key is not `group.key` — go back to Task 4 Step 3.

- [ ] **Step 5: Verify persistence**

Select `측정 실패만`, hard-reload the page, and confirm it comes back in that
mode. Then select `전부 보기` and confirm
`localStorage.getItem('skewnono:live-alarm.filter')` returns `null` — 'all' is
treated as empty, so the default must not be written.

- [ ] **Step 6: Verify keyboard navigation**

Tab to the filter strip and confirm it is a **single** tab stop. Press
ArrowRight / ArrowLeft and confirm the selection moves, wraps at both ends, and
that focus follows the selection. Press Home and End and confirm they jump to
the first and last option.

- [ ] **Step 7: Verify hv-sem**

Repeat Step 2 on `http://localhost:3000/ebeam/hv-sem/<fab>/live-alarm`. The
view component is shared, so this is a smoke check that the page wrapper passes
the right props — confirm the filter renders and the meas grouping works.

- [ ] **Step 8: Confirm no console errors**

Read the browser console across all of the above. Expected: no errors, no Vue
warnings about missing props or duplicate keys. A duplicate-key warning in the
group list means two groups produced the same `key`, which should be impossible
— report it rather than working around it.

- [ ] **Step 9: Run the full gate and push**

```bash
cd front-dev-home && npm test && npm run typecheck && npm run lint
cd .. && npm run lint:md
git push
```

Nothing is committed in this task — the four preceding commits are what gets
pushed. Report the actual output of each command; if any fails, say so with the
output rather than describing the work as done.

---

## Out of Scope

Stated here so implementation does not drift into them:

- Widening the board's time horizon past 10 minutes.
- A long-run per-PPID aggregation endpoint.
- Redesigning `AlarmRow.vue`.
- Grouping align alarms.
- Per-fab or per-tool filter memory.
- Any change under `back_dev_home/`.
