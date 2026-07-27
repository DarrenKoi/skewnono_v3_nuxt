# Recipe 검색 OpenSearch Fallback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redis Recipe catalog가 실패하거나 현재 검색어에 결과를 제공하지 못할 때 기존 OpenSearch 측정 이력 검색 결과를 선택 가능한 Recipe row로 표시하고, 지원되는 `횡전개`와 `측정 이력`만 안전하게 제공합니다.

**Architecture:** Redis catalog를 내려받은 뒤 브라우저에서 즉시 검색하는 현재 fast path는 유지합니다. Redis 요청 실패·빈 catalog·검색어 0건일 때만 기존 `/meas-hist/search`를 호출하고, result/selection/route에 `redis | opensearch` provenance를 전달하여 action capability를 계산합니다. 비동기 failover 판단과 selection migration은 pure TypeScript helper로 분리하여 Node test runner로 검증하고, Vue component는 그 결정을 렌더링하고 연결하는 역할만 맡습니다.

**Tech Stack:** Nuxt 4, Vue 3 Composition API, TypeScript 5.9, `@nuxt/ui`, Nuxt `useAsyncData`/`useState`, Node built-in test runner.

## Global Constraints

- Redis 결과가 한 건이라도 있으면 OpenSearch 결과를 merge하거나 OpenSearch를 호출하지 않습니다.
- OpenSearch는 Redis 요청 실패, 빈 Redis catalog, 현재 query의 Redis 0건일 때만 동작합니다.
- OpenSearch 조회는 기존 `useMeasHistApi().searchMeasHist()`와 `/meas-hist/search` contract를 재사용하며 새 Flask endpoint를 만들지 않습니다.
- OpenSearch 조회는 `toolType`, `fab`, AND-token으로 재검증한 Recipe query, `limit: 200`을 유지합니다.
- Redis와 OpenSearch row는 모두 선택할 수 있습니다.
- Redis selection은 `열어보기`, `횡전개`, `측정 이력`, `비교하기`를 지원합니다.
- OpenSearch selection은 `횡전개`, `측정 이력`만 지원합니다.
- mixed working set은 모든 selection이 공통으로 지원하는 `횡전개`, `측정 이력`만 제공합니다.
- 기존 `string[]` localStorage selection은 Redis selection으로 migration합니다.
- OpenSearch selection이 이후 Redis catalog에 나타나면 Redis로 승격하며 Redis selection을 강등하지 않습니다.
- OpenSearch source는 route query에 `source=opensearch`로 보존합니다. Redis URL은 기존 모양을 유지합니다.
- 기존 600ms debounce와 sequence 기반 stale-response 폐기를 유지합니다.
- 기존 exact → prefix → substring → token-only ranking, 결과 내 filter, page size, pagination을 유지합니다.
- office `recipe-detail`의 실제 IDP 연결, OpenSearch Recipe의 `열어보기`/`비교하기`, distinct Recipe aggregation은 범위 밖입니다.
- frontend test는 `front-dev-home/`에서 Node 24 runtime으로 실행합니다. Homebrew Node 25가 `libllhttp.9.3.dylib` 오류를 내면 `/Users/daeyoung/.nvm/versions/node/v24.13.0/bin`을 `PATH` 앞에 둡니다.
- 현재 worktree의 Skewvoir, `msr_file`, OpenWiki, datatable 변경은 사용자 소유입니다. 각 commit은 명시된 파일만 `git commit --only`로 포함합니다.
- 구현 중 backend file과 `back_dev_home/ebeam/hitachi/recipe_search/providers/office.py`는 수정하지 않습니다.

---

## File Map

### 새 파일

- `front-dev-home/app/utils/recipeSelection.ts`
  - search source, persisted selection shape, migration, promotion, capability intersection의 pure domain module입니다.
- `front-dev-home/app/utils/recipeSelection.test.ts`
  - legacy migration, malformed input, deduplication, promotion, capability를 검증합니다.

### 수정 파일

- `front-dev-home/app/composables/useRecipeSelectionSet.ts`
  - pure selection module을 Nuxt persisted state에 연결하고 기존 name 기반 consumer를 위한 computed view를 제공합니다.
- `front-dev-home/app/utils/recipeSearchMatch.ts`
  - source-aware result 작성, Redis→OpenSearch probe 판단, active result/view state 결정을 추가합니다.
- `front-dev-home/app/utils/recipeSearchMatch.test.ts`
  - Redis precedence, fallback 조건, source-aware result, view state를 검증합니다.
- `front-dev-home/app/utils/recipeView.ts`
  - source-preserving detail route와 source별 detail navigation을 제공합니다.
- `front-dev-home/app/utils/recipeView.test.ts`
  - Redis URL 회귀 방지와 OpenSearch route/navigation capability를 검증합니다.
- `front-dev-home/app/components/ebeam/RecipeSearchView.vue`
  - failover lifecycle, active result table, source별 row action, source-aware selection을 연결합니다.
- `front-dev-home/app/components/ebeam/recipeCompare/SearchSelectTray.vue`
  - selection capability 교집합에 따라 unsupported action을 숨깁니다.
- `front-dev-home/app/components/ebeam/RecipeDetailNav.vue`
  - route의 source를 읽어 지원되는 detail hop만 표시합니다.
- `front-dev-home/app/components/ebeam/RecipeSwitcher.vue`
  - selection source를 query에 보존하고 `open` 화면에서는 Redis selection만 표시합니다.
- `front-dev-home/app/components/ebeam/RecipeOpenView.vue`
  - switcher에 `active-screen="open"`을 전달합니다.
- `front-dev-home/app/components/ebeam/RecipeLateralView.vue`
  - switcher에 `active-screen="lateral"`을 전달합니다.
- `front-dev-home/app/components/ebeam/RecipeMeasHistView.vue`
  - switcher에 `active-screen="meas-hist"`를 전달합니다.
- `front-dev-home/app/components/ebeam/RecipeCompareView.vue`
  - OpenSearch를 포함한 selection에 compare request를 보내지 않는 defensive guard를 추가합니다.

---

### Task 1: Source-aware persisted Recipe selection

**Files:**

- Create: `front-dev-home/app/utils/recipeSelection.ts`
- Create: `front-dev-home/app/utils/recipeSelection.test.ts`
- Modify: `front-dev-home/app/composables/useRecipeSelectionSet.ts:1-42`

**Interfaces:**

- Produces:
  - `RecipeSearchSource = 'redis' | 'opensearch'`
  - `RecipeSelectionEntry { name: string, source: RecipeSearchSource }`
  - `RecipeSelectionCapabilities { open, lateral, measHist, compare }`
  - `normalizeRecipeSelectionEntries(parsed)`
  - `upsertRecipeSelection(entries, name, source)`
  - `removeRecipeSelection(entries, name)`
  - `promoteRecipeSelectionsToRedis(entries, redisNames)`
  - `capabilitiesForRecipeSelection(entries)`
  - `canCompareRecipeSelection(entries)`
  - composable members `entries`, `selected`, `capabilities`, `sourceOf`, `promoteRedis`
- Consumes: existing `usePersistedState()` and the unchanged storage key.

- [ ] **Step 1: Write failing selection-domain tests**

Create `app/utils/recipeSelection.test.ts`:

```ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  canCompareRecipeSelection,
  capabilitiesForRecipeSelection,
  normalizeRecipeSelectionEntries,
  promoteRecipeSelectionsToRedis,
  upsertRecipeSelection
} from './recipeSelection.ts'

test('legacy string selections migrate to Redis entries and discard blanks', () => {
  assert.deepEqual(
    normalizeRecipeSelectionEntries([' A ', '', 3, 'B']),
    [
      { name: 'A', source: 'redis' },
      { name: 'B', source: 'redis' }
    ]
  )
})

test('normalization rejects malformed entries and keeps one strongest source per name', () => {
  assert.deepEqual(
    normalizeRecipeSelectionEntries([
      { name: 'A', source: 'opensearch' },
      { name: 'A', source: 'redis' },
      { name: 'B', source: 'wrong' },
      { name: '', source: 'redis' },
      null
    ]),
    [{ name: 'A', source: 'redis' }]
  )
})

test('upsert promotes OpenSearch to Redis and never downgrades Redis', () => {
  const fallback = [{ name: 'A', source: 'opensearch' }] as const
  assert.deepEqual(upsertRecipeSelection([...fallback], 'A', 'redis'), [
    { name: 'A', source: 'redis' }
  ])
  assert.deepEqual(
    upsertRecipeSelection([{ name: 'A', source: 'redis' }], 'A', 'opensearch'),
    [{ name: 'A', source: 'redis' }]
  )
})

test('catalog reconciliation promotes only selected names Redis now contains', () => {
  const selected = [
    { name: 'A', source: 'opensearch' as const },
    { name: 'B', source: 'opensearch' as const }
  ]
  assert.deepEqual(promoteRecipeSelectionsToRedis(selected, ['A', 'C']), [
    { name: 'A', source: 'redis' },
    { name: 'B', source: 'opensearch' }
  ])
})

test('selection capabilities are the intersection across all entries', () => {
  assert.deepEqual(capabilitiesForRecipeSelection([]), {
    open: false,
    lateral: false,
    measHist: false,
    compare: false
  })
  assert.deepEqual(
    capabilitiesForRecipeSelection([{ name: 'A', source: 'redis' }]),
    { open: true, lateral: true, measHist: true, compare: true }
  )
  assert.deepEqual(
    capabilitiesForRecipeSelection([
      { name: 'A', source: 'redis' },
      { name: 'B', source: 'opensearch' }
    ]),
    { open: false, lateral: true, measHist: true, compare: false }
  )
})

test('compare requires at least two selections and every source to be Redis', () => {
  assert.equal(canCompareRecipeSelection([{ name: 'A', source: 'redis' }]), false)
  assert.equal(canCompareRecipeSelection([
    { name: 'A', source: 'redis' },
    { name: 'B', source: 'redis' }
  ]), true)
  assert.equal(canCompareRecipeSelection([
    { name: 'A', source: 'redis' },
    { name: 'B', source: 'opensearch' }
  ]), false)
})
```

The production mutation each test catches is respectively: legacy entries disappearing, invalid provenance being trusted, a Redis-confirmed selection being downgraded, stale OpenSearch provenance surviving catalog refresh, mixed sets exposing unsupported actions, and compare calling synthetic detail.

- [ ] **Step 2: Run the new test and verify RED**

Run from `front-dev-home/`:

```bash
node --test app/utils/recipeSelection.test.ts
```

Expected: FAIL with `ERR_MODULE_NOT_FOUND` for `recipeSelection.ts`.

- [ ] **Step 3: Implement the pure selection module**

Create `app/utils/recipeSelection.ts`:

```ts
export type RecipeSearchSource = 'redis' | 'opensearch'

export interface RecipeSelectionEntry {
  name: string
  source: RecipeSearchSource
}

export interface RecipeSelectionCapabilities {
  open: boolean
  lateral: boolean
  measHist: boolean
  compare: boolean
}

const isSource = (value: unknown): value is RecipeSearchSource =>
  value === 'redis' || value === 'opensearch'

const toEntry = (value: unknown): RecipeSelectionEntry | null => {
  if (typeof value === 'string') {
    const name = value.trim()
    return name ? { name, source: 'redis' } : null
  }
  if (!value || typeof value !== 'object') return null

  const candidate = value as Record<string, unknown>
  const name = typeof candidate.name === 'string' ? candidate.name.trim() : ''
  return name && isSource(candidate.source)
    ? { name, source: candidate.source }
    : null
}

export const normalizeRecipeSelectionEntries = (
  parsed: unknown
): RecipeSelectionEntry[] => {
  if (!Array.isArray(parsed)) return []
  const byName = new Map<string, RecipeSelectionEntry>()
  for (const value of parsed) {
    const entry = toEntry(value)
    if (!entry) continue
    const existing = byName.get(entry.name)
    if (!existing || entry.source === 'redis') byName.set(entry.name, entry)
  }
  return [...byName.values()]
}

export const upsertRecipeSelection = (
  entries: RecipeSelectionEntry[],
  rawName: string,
  source: RecipeSearchSource
): RecipeSelectionEntry[] => {
  const name = rawName.trim()
  if (!name) return entries
  const index = entries.findIndex(entry => entry.name === name)
  if (index < 0) return [...entries, { name, source }]
  if (entries[index]!.source === 'redis' || source === 'opensearch') return entries
  return entries.map((entry, at) => at === index ? { name, source: 'redis' } : entry)
}

export const removeRecipeSelection = (
  entries: RecipeSelectionEntry[],
  name: string
): RecipeSelectionEntry[] => entries.filter(entry => entry.name !== name)

export const promoteRecipeSelectionsToRedis = (
  entries: RecipeSelectionEntry[],
  redisNames: string[]
): RecipeSelectionEntry[] => {
  const catalog = new Set(redisNames)
  let changed = false
  const next = entries.map((entry) => {
    if (entry.source === 'opensearch' && catalog.has(entry.name)) {
      changed = true
      return { ...entry, source: 'redis' as const }
    }
    return entry
  })
  return changed ? next : entries
}

export const capabilitiesForRecipeSelection = (
  entries: RecipeSelectionEntry[]
): RecipeSelectionCapabilities => {
  if (!entries.length) {
    return { open: false, lateral: false, measHist: false, compare: false }
  }
  const redisOnly = entries.every(entry => entry.source === 'redis')
  return { open: redisOnly, lateral: true, measHist: true, compare: redisOnly }
}

export const canCompareRecipeSelection = (
  entries: RecipeSelectionEntry[]
): boolean => entries.length >= 2 && capabilitiesForRecipeSelection(entries).compare
```

- [ ] **Step 4: Run the selection tests and verify GREEN**

Run:

```bash
node --test app/utils/recipeSelection.test.ts
```

Expected: 6 tests PASS.

- [ ] **Step 5: Connect the pure model to `useRecipeSelectionSet`**

Replace the string-array state in `app/composables/useRecipeSelectionSet.ts` with:

```ts
import type { RecipeSearchToolType } from '~/composables/useRecipeSearchApi'
import {
  capabilitiesForRecipeSelection,
  normalizeRecipeSelectionEntries,
  promoteRecipeSelectionsToRedis,
  removeRecipeSelection,
  upsertRecipeSelection,
  type RecipeSearchSource,
  type RecipeSelectionEntry
} from '~/utils/recipeSelection'

const storageKey = (toolType: string, fab: string) =>
  `skewnono:recipe-search.selection.${toolType}.${fab || 'ALL'}`

export const useRecipeSelectionSet = (toolType: RecipeSearchToolType, fab: string) => {
  const scope = `${toolType}:${fab || 'ALL'}`
  const entries = usePersistedState<RecipeSelectionEntry[]>(
    `recipe-search:selection:${scope}`,
    storageKey(toolType, fab),
    { default: () => [], normalize: normalizeRecipeSelectionEntries }
  )

  const selected = computed(() => entries.value.map(entry => entry.name))
  const capabilities = computed(() => capabilitiesForRecipeSelection(entries.value))
  const has = (name: string) => entries.value.some(entry => entry.name === name)
  const sourceOf = (name: string): RecipeSearchSource =>
    entries.value.find(entry => entry.name === name)?.source ?? 'redis'

  const add = (name: string, source: RecipeSearchSource = 'redis') => {
    entries.value = upsertRecipeSelection(entries.value, name, source)
  }
  const remove = (name: string) => {
    entries.value = removeRecipeSelection(entries.value, name)
  }
  const toggle = (name: string, source: RecipeSearchSource = 'redis') => {
    if (has(name)) remove(name)
    else add(name, source)
  }
  const clear = () => {
    entries.value = []
  }
  const promoteRedis = (names: string[]) => {
    entries.value = promoteRecipeSelectionsToRedis(entries.value, names)
  }
  const count = computed(() => entries.value.length)

  return {
    entries,
    selected,
    capabilities,
    count,
    has,
    sourceOf,
    add,
    remove,
    toggle,
    clear,
    promoteRedis
  }
}
```

- [ ] **Step 6: Run focused tests, typecheck, and lint**

Run:

```bash
node --test app/utils/recipeSelection.test.ts
npm run typecheck
npm run lint -- app/utils/recipeSelection.ts app/utils/recipeSelection.test.ts app/composables/useRecipeSelectionSet.ts
```

Expected: selection tests PASS; typecheck exits 0; focused ESLint exits 0.

- [ ] **Step 7: Commit only the selection files**

```bash
git add front-dev-home/app/utils/recipeSelection.ts front-dev-home/app/utils/recipeSelection.test.ts front-dev-home/app/composables/useRecipeSelectionSet.ts
git diff --cached --check -- front-dev-home/app/utils/recipeSelection.ts front-dev-home/app/utils/recipeSelection.test.ts front-dev-home/app/composables/useRecipeSelectionSet.ts
git commit --only front-dev-home/app/utils/recipeSelection.ts front-dev-home/app/utils/recipeSelection.test.ts front-dev-home/app/composables/useRecipeSelectionSet.ts -m "feat(recipe-search): persist result source in working sets"
```

---

### Task 2: Preserve source through detail routes and Recipe switching

**Files:**

- Modify: `front-dev-home/app/utils/recipeView.ts:80-126`
- Modify: `front-dev-home/app/utils/recipeView.test.ts:119-178`
- Modify: `front-dev-home/app/components/ebeam/RecipeDetailNav.vue:1-28`
- Modify: `front-dev-home/app/components/ebeam/RecipeSwitcher.vue:1-49`
- Modify: `front-dev-home/app/components/ebeam/RecipeOpenView.vue:3-6`
- Modify: `front-dev-home/app/components/ebeam/RecipeLateralView.vue:105-109`
- Modify: `front-dev-home/app/components/ebeam/RecipeMeasHistView.vue:160-164`

**Interfaces:**

- Consumes: `RecipeSearchSource`, `RecipeSelectionEntry`, and `useRecipeSelectionSet().entries/sourceOf` from Task 1.
- Produces:
  - `recipeDetailRoute(..., source?: RecipeSearchSource)`
  - `buildRecipeDetailNavItems(..., setFlag, source?: RecipeSearchSource)`
  - `readRecipeSourceQuery(route)`
  - `RecipeSwitcher` prop `activeScreen: RecipeDetailScreen`

- [ ] **Step 1: Add failing source-route tests**

Append to the route/nav sections of `app/utils/recipeView.test.ts`:

```ts
test('OpenSearch detail routes carry source while Redis routes keep legacy URLs', () => {
  assert.deepEqual(
    recipeDetailRoute('cdsem', 'R3', 'lateral', 'CD_A', 'opensearch'),
    {
      path: '/ebeam/cdsem/r3/recipe-search/lateral',
      query: { recipe_name: 'CD_A', source: 'opensearch' }
    }
  )
  assert.deepEqual(
    recipeDetailRoute('cdsem', 'R3', 'lateral', 'CD_A', 'redis').query,
    { recipe_name: 'CD_A' }
  )
})

test('OpenSearch detail navigation excludes open and preserves source plus set', () => {
  const items = buildRecipeDetailNavItems(
    'cdsem', 'R3', 'CD_A', 'lateral', '1', 'opensearch'
  )
  assert.deepEqual(items.map(item => item.screen), ['lateral', 'meas-hist'])
  assert.deepEqual(items.map(item => item.to.query), [
    { recipe_name: 'CD_A', source: 'opensearch', set: '1' },
    { recipe_name: 'CD_A', source: 'opensearch', set: '1' }
  ])
})

test('readRecipeSourceQuery accepts only the explicit OpenSearch marker', () => {
  assert.equal(readRecipeSourceQuery(routeWith({ source: 'opensearch' })), 'opensearch')
  assert.equal(readRecipeSourceQuery(routeWith({ source: 'redis' })), 'redis')
  assert.equal(readRecipeSourceQuery(routeWith({ source: ['opensearch'] })), 'redis')
  assert.equal(readRecipeSourceQuery(routeWith({})), 'redis')
})
```

Add `readRecipeSourceQuery` to the import list.

- [ ] **Step 2: Run the route test and verify RED**

Run:

```bash
node --test app/utils/recipeView.test.ts
```

Expected: FAIL because the fifth route argument and `readRecipeSourceQuery` do not exist.

- [ ] **Step 3: Implement source-aware route helpers**

In `app/utils/recipeView.ts`, import `RecipeSearchSource` and change the helpers to:

```ts
import type { RecipeSearchSource } from '~/utils/recipeSelection'

export const recipeDetailRoute = (
  toolType: string,
  fab: string,
  screen: RecipeDetailScreen,
  recipeName: string,
  source: RecipeSearchSource = 'redis'
) => ({
  path: `/ebeam/${toolType}/${fab.toLowerCase()}/recipe-search/${screen}`,
  query: {
    recipe_name: recipeName,
    ...(source === 'opensearch' ? { source } : {})
  }
})

export const buildRecipeDetailNavItems = (
  toolType: string,
  fab: string,
  recipeName: string,
  activeScreen: RecipeDetailScreen,
  setFlag: unknown,
  source: RecipeSearchSource = 'redis'
) => RECIPE_ROW_ACTIONS
  .filter(action => source === 'redis' || action.screen !== 'open')
  .map((action) => {
    const target = recipeDetailRoute(toolType, fab, action.screen, recipeName, source)
    return {
      ...action,
      active: action.screen === activeScreen,
      to: setFlag === '1'
        ? { ...target, query: { ...target.query, set: '1' } }
        : target
    }
  })

export const readRecipeSourceQuery = (
  route: RouteLocationNormalizedLoaded
): RecipeSearchSource => route.query.source === 'opensearch' ? 'opensearch' : 'redis'
```

Existing four-argument `recipeDetailRoute()` and six-argument
`buildRecipeDetailNavItems()` calls must continue to default to Redis and keep
their current literal URL expectations.

- [ ] **Step 4: Run route tests and verify GREEN**

Run:

```bash
node --test app/utils/recipeView.test.ts app/utils/recipeDetailNavigation.test.ts
```

Expected: all existing and new route tests PASS.

- [ ] **Step 5: Make `RecipeDetailNav` read the route source**

Import `readRecipeSourceQuery` and pass it as the final builder argument:

```ts
import {
  buildRecipeDetailNavItems,
  readRecipeSourceQuery,
  type RecipeDetailScreen
} from '~/utils/recipeView'

const source = computed(() => readRecipeSourceQuery(route))
const items = computed(() => buildRecipeDetailNavItems(
  props.toolType,
  props.fab,
  props.recipeName,
  props.activeScreen,
  route.query.set,
  source.value
))
```

This removes `열어보기` from an OpenSearch Recipe's lateral/history nav without
changing Redis navigation.

- [ ] **Step 6: Make `RecipeSwitcher` source-aware**

Add `activeScreen: RecipeDetailScreen` to its props, use `entries` instead of
the plain name array, and replace the switching logic with:

```ts
import type { RecipeSearchToolType } from '~/composables/useRecipeSearchApi'
import { readRecipeNameQuery, type RecipeDetailScreen } from '~/utils/recipeView'

const props = defineProps<{
  toolType: RecipeSearchToolType
  fab: string
  activeScreen: RecipeDetailScreen
}>()

const { entries } = useRecipeSelectionSet(props.toolType, props.fab)
const availableEntries = computed(() =>
  props.activeScreen === 'open'
    ? entries.value.filter(entry => entry.source === 'redis')
    : entries.value
)
const show = computed(() => Boolean(route.query.set) && availableEntries.value.length >= 2)

const switchTo = (entry: RecipeSelectionEntry) => {
  if (entry.name === activeName.value) return
  const nextQuery = { ...route.query }
  delete nextQuery.source
  nextQuery.recipe_name = entry.name
  if (entry.source === 'opensearch') nextQuery.source = 'opensearch'
  router.replace({ query: nextQuery })
}
```

Update the template loop from `name in selected` to `entry in availableEntries`,
use `entry.name` for key/label/active checks, and call `switchTo(entry)`.
Import `RecipeSelectionEntry` as a type from `~/utils/recipeSelection`.

- [ ] **Step 7: Pass the active screen from all three detail views**

Add the exact prop to each existing switcher:

```vue
<!-- RecipeOpenView.vue -->
<EbeamRecipeSwitcher
  :tool-type="toolType"
  :fab="fab"
  active-screen="open"
/>

<!-- RecipeLateralView.vue -->
<EbeamRecipeSwitcher
  :tool-type="toolType"
  :fab="fab"
  active-screen="lateral"
/>

<!-- RecipeMeasHistView.vue -->
<EbeamRecipeSwitcher
  :tool-type="toolType"
  :fab="fab"
  active-screen="meas-hist"
/>
```

- [ ] **Step 8: Run focused verification**

Run:

```bash
node --test app/utils/recipeView.test.ts app/utils/recipeDetailNavigation.test.ts
npm run typecheck
npm run lint -- app/utils/recipeView.ts app/utils/recipeView.test.ts app/components/ebeam/RecipeDetailNav.vue app/components/ebeam/RecipeSwitcher.vue app/components/ebeam/RecipeOpenView.vue app/components/ebeam/RecipeLateralView.vue app/components/ebeam/RecipeMeasHistView.vue
```

Expected: tests PASS; typecheck and focused lint exit 0.

- [ ] **Step 9: Commit only route/navigation files**

```bash
git add front-dev-home/app/utils/recipeView.ts front-dev-home/app/utils/recipeView.test.ts front-dev-home/app/components/ebeam/RecipeDetailNav.vue front-dev-home/app/components/ebeam/RecipeSwitcher.vue front-dev-home/app/components/ebeam/RecipeOpenView.vue front-dev-home/app/components/ebeam/RecipeLateralView.vue front-dev-home/app/components/ebeam/RecipeMeasHistView.vue
git diff --cached --check -- front-dev-home/app/utils/recipeView.ts front-dev-home/app/utils/recipeView.test.ts front-dev-home/app/components/ebeam/RecipeDetailNav.vue front-dev-home/app/components/ebeam/RecipeSwitcher.vue front-dev-home/app/components/ebeam/RecipeOpenView.vue front-dev-home/app/components/ebeam/RecipeLateralView.vue front-dev-home/app/components/ebeam/RecipeMeasHistView.vue
git commit --only front-dev-home/app/utils/recipeView.ts front-dev-home/app/utils/recipeView.test.ts front-dev-home/app/components/ebeam/RecipeDetailNav.vue front-dev-home/app/components/ebeam/RecipeSwitcher.vue front-dev-home/app/components/ebeam/RecipeOpenView.vue front-dev-home/app/components/ebeam/RecipeLateralView.vue front-dev-home/app/components/ebeam/RecipeMeasHistView.vue -m "fix(recipe-search): preserve fallback source in detail routes"
```

---

### Task 3: Model Redis precedence and fallback view states

**Files:**

- Modify: `front-dev-home/app/utils/recipeSearchMatch.ts:1-68`
- Modify: `front-dev-home/app/utils/recipeSearchMatch.test.ts:1-96`

**Interfaces:**

- Consumes: `RecipeSearchSource` from Task 1.
- Produces:
  - `RecipeSearchResult { recipe_name, source }`
  - `toRecipeSearchResults(names, source)`
  - `shouldProbeRecipeFallback(input)`
  - `activeRecipeResults(redisResults, fallbackResults)`
  - `resolveRecipeSearchViewState(input)`
  - `RecipeSearchViewState`

- [ ] **Step 1: Write failing failover-decision tests**

Extend the import list and append:

```ts
test('fallback probing waits for Redis and runs only for a searchable zero match', () => {
  assert.equal(shouldProbeRecipeFallback({
    canSearch: true, catalogPending: false, redisMatchCount: 0
  }), true)
  assert.equal(shouldProbeRecipeFallback({
    canSearch: true, catalogPending: true, redisMatchCount: 0
  }), false)
  assert.equal(shouldProbeRecipeFallback({
    canSearch: true, catalogPending: false, redisMatchCount: 1
  }), false)
  assert.equal(shouldProbeRecipeFallback({
    canSearch: false, catalogPending: false, redisMatchCount: 0
  }), false)
})

test('source-aware results dedupe names and Redis results always win', () => {
  const redis = toRecipeSearchResults(['A', 'B'], 'redis')
  const fallback = toRecipeSearchResults(['B', 'C', 'C'], 'opensearch')
  assert.deepEqual(fallback, [
    { recipe_name: 'B', source: 'opensearch' },
    { recipe_name: 'C', source: 'opensearch' }
  ])
  assert.equal(activeRecipeResults(redis, fallback), redis)
  assert.equal(activeRecipeResults([], fallback), fallback)
})

test('view state distinguishes fallback loading, results, empty and both-source failure', () => {
  const base = {
    canSearch: true,
    catalogPending: false,
    catalogFailed: false,
    resultCount: 0,
    fallbackPending: false,
    fallbackSettled: false,
    fallbackFailed: false
  }
  assert.equal(resolveRecipeSearchViewState({
    ...base, fallbackPending: true
  }), 'fallback-loading')
  assert.equal(resolveRecipeSearchViewState({
    ...base, resultCount: 2
  }), 'results')
  assert.equal(resolveRecipeSearchViewState({
    ...base, fallbackSettled: true
  }), 'empty')
  assert.equal(resolveRecipeSearchViewState({
    ...base, catalogFailed: true, fallbackSettled: true, fallbackFailed: true
  }), 'sources-error')
  assert.equal(resolveRecipeSearchViewState({
    ...base, fallbackSettled: true, fallbackFailed: true
  }), 'fallback-error')
})

test('view state preserves catalog loading and pre-search idle behavior', () => {
  assert.equal(resolveRecipeSearchViewState({
    canSearch: true,
    catalogPending: true,
    catalogFailed: false,
    resultCount: 0,
    fallbackPending: false,
    fallbackSettled: false,
    fallbackFailed: false
  }), 'catalog-loading')
  assert.equal(resolveRecipeSearchViewState({
    canSearch: false,
    catalogPending: false,
    catalogFailed: true,
    resultCount: 0,
    fallbackPending: false,
    fallbackSettled: false,
    fallbackFailed: false
  }), 'idle')
})
```

- [ ] **Step 2: Run matcher tests and verify RED**

Run:

```bash
node --test app/utils/recipeSearchMatch.test.ts
```

Expected: FAIL because the source-aware failover exports do not exist.

- [ ] **Step 3: Implement failover helpers**

Append to `app/utils/recipeSearchMatch.ts`:

```ts
import type { RecipeSearchSource } from '~/utils/recipeSelection'

export interface RecipeSearchResult {
  recipe_name: string
  source: RecipeSearchSource
}

export const toRecipeSearchResults = (
  names: string[],
  source: RecipeSearchSource
): RecipeSearchResult[] => {
  const seen = new Set<string>()
  const results: RecipeSearchResult[] = []
  for (const raw of names) {
    const recipeName = raw.trim()
    if (!recipeName || seen.has(recipeName)) continue
    seen.add(recipeName)
    results.push({ recipe_name: recipeName, source })
  }
  return results
}

export const shouldProbeRecipeFallback = (input: {
  canSearch: boolean
  catalogPending: boolean
  redisMatchCount: number
}): boolean =>
  input.canSearch && !input.catalogPending && input.redisMatchCount === 0

export const activeRecipeResults = (
  redisResults: RecipeSearchResult[],
  fallbackResults: RecipeSearchResult[]
): RecipeSearchResult[] => redisResults.length ? redisResults : fallbackResults

export type RecipeSearchViewState =
  | 'idle'
  | 'catalog-loading'
  | 'fallback-loading'
  | 'results'
  | 'empty'
  | 'fallback-error'
  | 'sources-error'

export const resolveRecipeSearchViewState = (input: {
  canSearch: boolean
  catalogPending: boolean
  catalogFailed: boolean
  resultCount: number
  fallbackPending: boolean
  fallbackSettled: boolean
  fallbackFailed: boolean
}): RecipeSearchViewState => {
  if (input.catalogPending) return 'catalog-loading'
  if (!input.canSearch) return 'idle'
  if (input.resultCount > 0) return 'results'
  if (input.fallbackPending || !input.fallbackSettled) return 'fallback-loading'
  if (input.fallbackFailed) {
    return input.catalogFailed ? 'sources-error' : 'fallback-error'
  }
  return 'empty'
}
```

If ESLint requires imports before declarations, move the type import to the
top of the file. Do not change existing matching/ranking behavior.

- [ ] **Step 4: Run matcher tests and verify GREEN**

Run:

```bash
node --test app/utils/recipeSearchMatch.test.ts
```

Expected: all existing matching tests and four new failover tests PASS.

- [ ] **Step 5: Run focused type/lint checks**

Run:

```bash
npm run typecheck
npm run lint -- app/utils/recipeSearchMatch.ts app/utils/recipeSearchMatch.test.ts
```

Expected: both commands exit 0.

- [ ] **Step 6: Commit only failover-domain files**

```bash
git add front-dev-home/app/utils/recipeSearchMatch.ts front-dev-home/app/utils/recipeSearchMatch.test.ts
git diff --cached --check -- front-dev-home/app/utils/recipeSearchMatch.ts front-dev-home/app/utils/recipeSearchMatch.test.ts
git commit --only front-dev-home/app/utils/recipeSearchMatch.ts front-dev-home/app/utils/recipeSearchMatch.test.ts -m "feat(recipe-search): model Redis to OpenSearch failover"
```

---

### Task 4: Render actionable OpenSearch results in Recipe 검색

**Files:**

- Modify: `front-dev-home/app/components/ebeam/RecipeSearchView.vue:1-735`
- Modify: `front-dev-home/app/components/ebeam/recipeCompare/SearchSelectTray.vue:1-120`

**Interfaces:**

- Consumes:
  - selection entries/capabilities/promotion from Task 1
  - source-preserving `recipeDetailRoute()` from Task 2
  - failover helpers and `RecipeSearchResult` from Task 3
- Produces: end-to-end Redis-primary/OpenSearch-fallback search UI.

- [ ] **Step 1: Replace catalog-only rows with source-aware active rows**

Update imports from `recipeSearchMatch` to include:

```ts
import {
  activeRecipeResults,
  matchesRecipeQuery,
  matchingHistoryNames,
  rankRecipeMatches,
  resolveRecipeSearchViewState,
  shouldProbeRecipeFallback,
  toRecipeSearchResults,
  tokenizeRecipeQuery,
  type RecipeSearchResult
} from '~/utils/recipeSearchMatch'
```

Keep catalog matching separate from active results:

```ts
const redisMatchedNames = computed<string[]>(() => {
  if (!canSearch.value) return []
  return rankRecipeMatches(searchableRows.value, query.value)
})

const redisResults = computed(() =>
  toRecipeSearchResults(redisMatchedNames.value, 'redis')
)
const fallbackResults = computed(() =>
  toRecipeSearchResults(historyMatches.value, 'opensearch')
)
const filteredRows = computed(() =>
  activeRecipeResults(redisResults.value, fallbackResults.value)
)
const activeSource = computed(() =>
  redisResults.value.length ? 'redis' : fallbackResults.value.length ? 'opensearch' : null
)
```

Change `searchableRows.value` from `{ recipe_name }` objects to recipe-name
strings so `rankRecipeMatches()` returns `string[]`:

```ts
return recipeNames.value.map(recipeName => ({
  value: recipeName,
  searchText: recipeName.trim().toLowerCase()
}))
```

Change `filteredRows`, `refinedRows`, `pagedRows`, `columns`, and table slots to
use `RecipeSearchResult`. The in-table filter still reads
`row.recipe_name`. `filteredCount`, pagination, and `Matched` stat now derive
from active results.

- [ ] **Step 2: Promote persisted OpenSearch selections when Redis catches up**

Destructure the expanded composable:

```ts
const {
  entries,
  selected,
  capabilities,
  has,
  toggle,
  remove,
  clear,
  count,
  sourceOf,
  promoteRedis
} = useRecipeSelectionSet(props.toolType, props.fab)

watch(recipeNames, names => promoteRedis(names), { immediate: true })
```

`togglePageSelection()` must pass each row's source:

```ts
const togglePageSelection = () => {
  const allSelected = pagedRows.value.length > 0
    && pagedRows.value.every(row => has(row.recipe_name))
  if (allSelected) {
    pagedRows.value.forEach(row => remove(row.recipe_name))
  } else {
    pagedRows.value.forEach((row) => {
      if (!has(row.recipe_name)) toggle(row.recipe_name, row.source)
    })
  }
}
```

The row checkbox calls:

```vue
@update:model-value="toggle(row.original.recipe_name, row.original.source)"
```

- [ ] **Step 3: Turn the history hint watcher into explicit failover state**

Remove `HISTORY_HINT`, `useToast()`, `historyMatchesLabel`,
`lastHistoryToastKey`, and the toast call. Add:

```ts
const historyMatches = ref<string[]>([])
const fallbackPending = ref(false)
const fallbackSettled = ref(false)
const fallbackFailed = ref(false)

const historyProbeKey = computed(() =>
  shouldProbeRecipeFallback({
    canSearch: canSearch.value,
    catalogPending: pending.value,
    redisMatchCount: redisMatchedNames.value.length
  })
    ? `${props.toolType}:${props.fab || 'ALL'}:${normalizedQuery.value}:${error.value ? 'redis-error' : 'redis-miss'}`
    : ''
)
```

Replace the watcher body with:

```ts
watch(historyProbeKey, (key) => {
  clearTimeout(historyProbeTimer)
  const seq = ++historyProbeSeq
  historyMatches.value = []
  fallbackPending.value = Boolean(key)
  fallbackSettled.value = false
  fallbackFailed.value = false
  if (!key) return

  const tokens = queryTokens.value
  historyProbeTimer = setTimeout(async () => {
    try {
      const response = await searchMeasHist({
        toolType: props.toolType,
        fab: props.fab ? [props.fab] : undefined,
        recipe: tokens,
        limit: HISTORY_PROBE_LIMIT
      })
      if (seq !== historyProbeSeq) return
      historyMatches.value = matchingHistoryNames(
        response.rows.map(row => row.full_name),
        tokens
      )
    } catch {
      if (seq !== historyProbeSeq) return
      fallbackFailed.value = true
    } finally {
      if (seq === historyProbeSeq) {
        fallbackPending.value = false
        fallbackSettled.value = true
      }
    }
  }, HISTORY_PROBE_DEBOUNCE_MS)
}, { immediate: true })
```

This preserves the existing timer and sequence gate while exposing pending,
settled, and failed states.

- [ ] **Step 4: Resolve one test-backed view state**

Add:

```ts
const viewState = computed(() => resolveRecipeSearchViewState({
  canSearch: canSearch.value,
  catalogPending: pending.value,
  catalogFailed: Boolean(error.value),
  resultCount: filteredCount.value,
  fallbackPending: fallbackPending.value,
  fallbackSettled: fallbackSettled.value,
  fallbackFailed: fallbackFailed.value
}))

const fallbackMode = computed(() =>
  !pending.value && (
    Boolean(error.value)
    || totalRows.value === 0
    || activeSource.value === 'opensearch'
  )
)
```

Use `viewState` rather than the old `pending/error/canSearch/filteredCount`
branch sequence:

- `catalog-loading`: existing catalog loading card
- `idle`: no main card
- `fallback-loading`: OpenSearch loader
- `results`: result table
- `empty`: two-source empty state
- `fallback-error`: Redis miss plus OpenSearch failure notice
- `sources-error`: both-source failure with Redis Retry button

- [ ] **Step 5: Preserve source in every row and working-set route**

Change route builders to accept `source`:

```ts
const getRecipeDetailRoute = (recipeName: string, source = sourceOf(recipeName)) =>
  recipeDetailRoute(props.toolType, props.fab, 'open', recipeName, source)

const getLateralRoute = (recipeName: string, source = sourceOf(recipeName)) =>
  recipeDetailRoute(props.toolType, props.fab, 'lateral', recipeName, source)

const getMeasHistRoute = (recipeName: string, source = sourceOf(recipeName)) =>
  recipeDetailRoute(props.toolType, props.fab, 'meas-hist', recipeName, source)
```

Use the first entry, not only its name:

```ts
const firstSelectedEntry = computed(() => entries.value[0] ?? null)

const openSetDetail = () => {
  const first = firstSelectedEntry.value
  if (first && capabilities.value.open) {
    router.push(withSetFlag(getRecipeDetailRoute(first.name, first.source)))
  }
}
const openSetLateral = () => {
  const first = firstSelectedEntry.value
  if (first) router.push(withSetFlag(getLateralRoute(first.name, first.source)))
}
const openSetMeasHist = () => {
  const first = firstSelectedEntry.value
  if (first) router.push(withSetFlag(getMeasHistRoute(first.name, first.source)))
}
const openSetCompare = () => {
  if (count.value < 1 || !capabilities.value.compare) return
  router.push({ path: recipeSubpath('compare') })
}
```

Per-row handlers pass the source explicitly and defensively reject unsupported
open requests:

```ts
const openRecipeDetail = (row: RecipeSearchResult) => {
  if (row.source !== 'redis') return
  recordRecentSearch(query.value.trim())
  router.push(getRecipeDetailRoute(row.recipe_name, row.source))
}

const openLateral = (row: RecipeSearchResult) => {
  recordRecentSearch(query.value.trim())
  router.push(getLateralRoute(row.recipe_name, row.source))
}

const openMeasHist = (row: RecipeSearchResult) => {
  recordRecentSearch(query.value.trim())
  router.push(getMeasHistRoute(row.recipe_name, row.source))
}
```

Do not infer an OpenSearch row as Redis before it has been selected.

- [ ] **Step 6: Replace the amber hint with the normal result table**

In the lookup card, show a compact fallback-mode banner when
`fallbackMode` is true:

```vue
<div
  v-if="fallbackMode"
  class="mt-2.5 flex items-center justify-between gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-[11px] text-amber-800 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-200"
>
  <span class="flex items-center gap-1.5">
    <UIcon name="i-lucide-database-zap" class="h-3.5 w-3.5" />
    Redis 결과를 사용할 수 없어 OpenSearch fallback을 사용합니다.
  </span>
  <UButton
    v-if="error"
    size="xs"
    color="neutral"
    variant="ghost"
    label="Redis Retry"
    @click="refresh()"
  />
</div>
```

Render these exact status messages:

```vue
<!-- fallback-loading -->
<p>OpenSearch에서 Recipe를 검색하는 중입니다.</p>

<!-- empty -->
<p>Redis와 OpenSearch에서 검색 결과를 찾지 못했습니다.</p>

<!-- fallback-error -->
<p>OpenSearch fallback 검색을 완료하지 못했습니다.</p>

<!-- sources-error -->
<p>Redis와 OpenSearch 검색을 모두 사용할 수 없습니다.</p>
```

The results section remains one `UTable`. Add an `OpenSearch fallback` badge
next to `Recipe results` when `activeSource === 'opensearch'`. Add a small
`OpenSearch` indicator beside fallback recipe names.

Use source-specific action cells:

```vue
<UButton
  v-if="row.original.source === 'redis'"
  size="sm"
  color="neutral"
  variant="outline"
  icon="i-lucide-file-search"
  label="열어 보기"
  @click="openRecipeDetail(row.original)"
/>
<UButton
  size="sm"
  color="neutral"
  variant="outline"
  icon="i-lucide-network"
  label="횡전개"
  @click="openLateral(row.original)"
/>
<UButton
  size="sm"
  color="neutral"
  variant="outline"
  icon="i-lucide-history"
  label="측정 이력"
  @click="openMeasHist(row.original)"
/>
```

- [ ] **Step 7: Gate tray actions by capability intersection**

Add a required prop to `SearchSelectTray.vue`:

```ts
import type { RecipeSelectionCapabilities } from '~/utils/recipeSelection'

defineProps<{
  selected: string[]
  capabilities: RecipeSelectionCapabilities
}>()
```

Render `열어보기` only when the set is empty or `capabilities.open` is true,
and render `비교하기` only when the set is empty or `capabilities.compare` is
true. Empty sets retain the current four disabled buttons; OpenSearch/mixed
sets show only the two supported actions.

```vue
<UButton
  v-if="!selected.length || capabilities.open"
  color="neutral"
  variant="outline"
  icon="i-lucide-file-search"
  label="열어보기"
  class="justify-center"
  :disabled="!selected.length"
  @click="emit('open')"
/>

<UButton
  v-if="!selected.length || capabilities.compare"
  color="primary"
  variant="solid"
  icon="i-lucide-scale"
  label="비교하기"
  class="justify-center"
  :disabled="!selected.length"
  @click="emit('compare')"
/>
```

Pass the prop from `RecipeSearchView.vue`:

```vue
<EbeamRecipeCompareSearchSelectTray
  :selected="selected"
  :capabilities="capabilities"
  @remove="remove"
  @clear="clear"
  @compare="openSetCompare"
  @open="openSetDetail"
  @lateral="openSetLateral"
  @meas-hist="openSetMeasHist"
/>
```

- [ ] **Step 8: Run focused automated verification**

Run:

```bash
node --test app/utils/recipeSelection.test.ts app/utils/recipeSearchMatch.test.ts app/utils/recipeView.test.ts app/utils/recipeDetailNavigation.test.ts
npm run typecheck
npm run lint -- app/components/ebeam/RecipeSearchView.vue app/components/ebeam/recipeCompare/SearchSelectTray.vue
```

Expected: all focused tests PASS; typecheck and focused lint exit 0.

- [ ] **Step 9: Verify UI behavior in the running app**

Start or reuse the backend and frontend:

```bash
# repo root
.venv/bin/python index.py

# front-dev-home, separate terminal
npm run dev
```

Use the in-app browser at the Recipe 검색 route and verify:

1. A known Redis recipe renders immediately with all three row actions.
2. A query present only in `meas_hist` shows the same result table with
   `OpenSearch fallback`, checkbox, `횡전개`, and `측정 이력`, but no
   `열어보기`.
3. Selecting fallback rows leaves only `횡전개` and `측정 이력` in the tray.
4. Changing back to a Redis match removes the fallback badge and restores
   Redis actions.
5. Rapidly replacing one missing query with another never lets the first
   OpenSearch response overwrite the second query.

If office Redis/OpenSearch are unavailable in this environment, use the home
mock to verify Redis behavior and source/headless inspection for the fallback
branches; explicitly record that live office failover remains unverified.

- [ ] **Step 10: Commit only search UI files**

```bash
git add front-dev-home/app/components/ebeam/RecipeSearchView.vue front-dev-home/app/components/ebeam/recipeCompare/SearchSelectTray.vue
git diff --cached --check -- front-dev-home/app/components/ebeam/RecipeSearchView.vue front-dev-home/app/components/ebeam/recipeCompare/SearchSelectTray.vue
git commit --only front-dev-home/app/components/ebeam/RecipeSearchView.vue front-dev-home/app/components/ebeam/recipeCompare/SearchSelectTray.vue -m "feat(recipe-search): expose actionable OpenSearch fallback results"
```

---

### Task 5: Defensively block compare for fallback selections

**Files:**

- Modify: `front-dev-home/app/utils/recipeSelection.ts`
- Modify: `front-dev-home/app/utils/recipeSelection.test.ts`
- Modify: `front-dev-home/app/components/ebeam/RecipeCompareView.vue:1-202`

**Interfaces:**

- Consumes: `entries`, `selected`, and `canCompareRecipeSelection()` from Task 1.
- Produces: compare view that never calls the synthetic IDP compare endpoint for OpenSearch/mixed selections.

- [ ] **Step 1: Write a failing compare-request boundary test**

Add `recipeNamesForCompare` to the import list and append:

```ts
test('compare request names exist only for a Redis-only set of at least two', () => {
  assert.deepEqual(recipeNamesForCompare([
    { name: 'A', source: 'redis' },
    { name: 'B', source: 'redis' }
  ]), ['A', 'B'])
  assert.equal(recipeNamesForCompare([
    { name: 'A', source: 'redis' },
    { name: 'B', source: 'opensearch' }
  ]), null)
  assert.equal(recipeNamesForCompare([
    { name: 'A', source: 'redis' }
  ]), null)
})
```

This test catches the production mutation where the compare view sends every
selected name without checking source.

- [ ] **Step 2: Run the new boundary test and verify RED**

Run:

```bash
node --test app/utils/recipeSelection.test.ts
```

Expected: FAIL because `recipeNamesForCompare` is not exported.

- [ ] **Step 3: Implement the tested request boundary**

Append to `recipeSelection.ts`:

```ts
export const recipeNamesForCompare = (
  entries: RecipeSelectionEntry[]
): string[] | null =>
  canCompareRecipeSelection(entries)
    ? entries.map(entry => entry.name)
    : null
```

Run:

```bash
node --test app/utils/recipeSelection.test.ts
```

Expected: all selection tests PASS.

- [ ] **Step 4: Add the defensive compare guard**

In `RecipeCompareView.vue`, import `recipeNamesForCompare` and destructure
`entries`:

```ts
import { recipeNamesForCompare } from '~/utils/recipeSelection'

const { entries, selected, remove } = useRecipeSelectionSet(props.toolType, props.fab)
const containsFallback = computed(() =>
  entries.value.some(entry => entry.source === 'opensearch')
)
const compareNames = computed(() => recipeNamesForCompare(entries.value))
const compareAllowed = computed(() => compareNames.value !== null)
```

Change the empty-state branch to `v-if="!compareAllowed"`. Use this message
when `containsFallback` is true:

```vue
<p class="mt-2 sk-body">
  OpenSearch fallback Recipe는 아직 비교하기를 지원하지 않습니다.
</p>
<p class="mt-1 sk-meta">
  횡전개 또는 측정 이력을 이용해주세요.
</p>
```

Keep the existing “2개 이상 선택” message when there is no fallback source.

Guard the cache and request:

```ts
const cacheKey = computed(() =>
  compareNames.value
    ? `recipe-compare:${props.toolType}:${props.fab || 'ALL'}:${[...compareNames.value].sort().join('|')}`
    : `recipe-compare:unsupported:${props.toolType}:${props.fab || 'ALL'}`
)

const { data, pending, error, refresh } = await useAsyncData<RecipeCompareResponse | null>(
  () => cacheKey.value,
  () => {
    const names = compareNames.value
    return names
      ? fetchCompare({
          toolType: props.toolType,
          fabName: props.fab,
          recipeNames: names
        })
      : Promise.resolve(null)
  },
  {
    watch: [cacheKey],
    default: () => null,
    getCachedData: (key, nuxtApp) => nuxtApp.payload.data[key] ?? nuxtApp.static.data[key]
  }
)
```

- [ ] **Step 5: Run focused and full frontend verification**

Run:

```bash
node --test app/utils/recipeSelection.test.ts
npm run typecheck
npm run lint -- app/components/ebeam/RecipeCompareView.vue
npm test
```

Expected: focused selection tests and the complete frontend Node suite PASS;
typecheck and focused lint exit 0.

- [ ] **Step 6: Commit only the compare boundary files**

```bash
git add front-dev-home/app/utils/recipeSelection.ts front-dev-home/app/utils/recipeSelection.test.ts front-dev-home/app/components/ebeam/RecipeCompareView.vue
git diff --cached --check -- front-dev-home/app/utils/recipeSelection.ts front-dev-home/app/utils/recipeSelection.test.ts front-dev-home/app/components/ebeam/RecipeCompareView.vue
git commit --only front-dev-home/app/utils/recipeSelection.ts front-dev-home/app/utils/recipeSelection.test.ts front-dev-home/app/components/ebeam/RecipeCompareView.vue -m "fix(recipe-search): block compare for fallback selections"
```

---

## Final Verification Gate

Do not claim completion or publish until every command below has been run
fresh against the final implementation.

- [ ] From `front-dev-home/`, select Node 24 if needed:

```bash
export PATH="/Users/daeyoung/.nvm/versions/node/v24.13.0/bin:$PATH"
node --version
```

Expected: `v24.13.0`.

- [ ] Run all frontend gates:

```bash
npm run lint
npm run typecheck
npm test
npm run build
```

Expected: all commands exit 0. If full lint finds pre-existing errors in
untouched files, record exact paths/counts and still require every modified
Recipe file to pass focused lint.

- [ ] From repo root, check patch hygiene and intended scope:

```bash
git diff --check
git status --short
git log -5 --oneline
```

Expected: no whitespace errors; only the implementation plan and unrelated
user-owned work remain uncommitted; the five intended Recipe commits are at
HEAD.

- [ ] Recheck the requirement matrix:

| Scenario | Expected result |
| --- | --- |
| Redis returns matches | Redis rows only; no OpenSearch request; all current actions |
| Redis query returns 0 | OpenSearch row table; selectable; lateral/history only |
| Redis catalog is empty | OpenSearch fallback mode after a valid query |
| Redis request fails | Search input remains usable; OpenSearch fallback runs |
| OpenSearch also returns 0 | honest two-source empty state |
| OpenSearch request fails after Redis miss | fallback error state |
| Both requests fail | two-source error plus Redis Retry |
| OpenSearch-only set | lateral/history tray and switcher |
| Mixed set | lateral/history only; no open/compare handler |
| Previously selected OpenSearch Recipe appears in Redis | selection is promoted to Redis |
| OpenSearch lateral/history route | `source=opensearch`; detail nav omits open |
| Redis route | existing URL and all three detail hops unchanged |

- [ ] Inspect each implementation commit:

```bash
git show --stat --oneline HEAD~4
git show --stat --oneline HEAD~3
git show --stat --oneline HEAD~2
git show --stat --oneline HEAD~1
git show --stat --oneline HEAD
```

Expected: each commit contains only its named Recipe files and no Skewvoir,
`msr_file`, OpenWiki, or datatable changes.
