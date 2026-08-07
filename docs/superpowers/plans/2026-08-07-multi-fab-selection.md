# 사이드바 FAB 다중 선택 Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 사이드바에서 FAB을 여러 개 선택하면 filter-style feature(storage·hardware·recipe-status(tat/fail-issue)·장비상태 landing)가 선택된 FAB 집합의 데이터를 합산해 보여준다.

**Architecture:** URL 세그먼트를 쉼표 결합 목록(`/ebeam/cd-sem/r3,m16b/storage`)으로 확장하고, `utils/fab.ts`의 순수 함수(파싱·결합·토글)가 모든 불변식을 소유한다. store는 `fabs: string[]`(대문자·중복 제거·선택 순서, `fabs[0]`=primary)를 들고, 기존 `fab` 접근자는 primary를 돌려주는 호환 computed로 남아 미이관 소비자가 계속 컴파일된다. 백엔드는 공유 지점 두 곳(`resolve_analytics_scope`, `filter_clauses`)의 시그니처를 목록형으로 바꿔 recipe_tat·fail_issue를 한 번에 획득하고, storage는 이미 목록형이라 변경이 없다.

**Tech Stack:** Nuxt 4 (SPA, `useState` composables), Python 3.14 + Flask, pytest, node --test.

**Spec:** `docs/superpowers/specs/2026-08-07-multi-fab-selection-design.md`

## Global Constraints

- 커밋은 **직접 편집한 파일만 명시 경로로** 스테이징한다. `git add -A`, `git add .`, `git commit -a` 금지.
- 다중 파일 작업이므로 **전용 worktree**(`../skewnono-multi-fab`, branch `work/multi-fab`)에서 진행한다. Task 1이 만들고 Task 11이 반드시 철거한다.
- backend 테스트는 worktree 루트에서 `.venv/bin/python -m pytest`로 실행한다 (`-m`이 루트를 `sys.path`에 올린다). worktree에는 gitignored `office.py` 사본이 없어 skip 수가 main 트리와 다르다 — passed+skipped 합계로 비교한다.
- frontend 명령은 `front-dev-home/`에서: `npm test`, `npm run typecheck`, `npm run lint`.
- Markdown을 고치면 루트에서 `npm run lint:md`. 표는 MD060 compact 스타일.
- UI 색은 `--sk-*` 토큰만. 새 UI를 만지기 전에 루트 `DESIGN.md`를 읽는다.
- Pinia·TanStack Query 도입 금지. localStorage는 기존 플러그인 파일 수정으로만.
- 계약 규칙: **row 단위 필드 `fab_name`(MeasHistRow·FailRow·StorageRow 등)은 그대로 둔다.** 바뀌는 것은 scope/meta echo(`SummaryPayload.fab_name` 등 → `fab_names`)뿐이다.
- 백엔드 provider 계층의 fab 목록 타입은 **`tuple[str, ...]`** — recipe_tat mock의 `_filter_rows`가 `lru_cache`라 인자가 hashable이어야 한다. `list`를 넘기면 `TypeError: unhashable type`.
- 프론트 fab 목록은 항상 `utils/fab.ts`의 `canonicalFabList` 계열을 거친다(대문자, 중복 제거, 순서 보존, sentinel 제거).
- `/api/*`는 20 req/5s rate limit — curl 검증 루프는 간격을 둔다.

## File Structure

```text
front-dev-home/app/
  utils/fab.ts                  # +canonicalFabList/parseFabSegment/buildFabSegment/toggleFabInList
  utils/fab.test.ts             # +다중 FAB 케이스
  stores/navigation.ts          # fab: string → fabs: string[] (+호환 fab computed)
  plugins/persist-fab.client.ts # 쉼표 결합 목록 저장/복원
  composables/useNavigation.ts  # +toggleFab, href가 buildFabSegment 사용
  composables/useFabRoute.ts    # NEW — [fab] 페이지 공용 파싱/스토어 동기화
  composables/useSemListApi.ts  # filterRows가 Fab | readonly Fab[] 수용
  composables/useRecipeTatApi.ts# fabName → fabNames[], 응답 meta fab_names
  composables/useFailIssueApi.ts# 동일
  composables/useStorageApi.ts  # fetchByUrlFab 헬퍼 제거(직접 목록 호출)
  components/nav/FabSidebar.vue # 체크박스 다중 선택
  components/nav/FabScopeNotice.vue # NEW — 단일 FAB 페이지 힌트 1줄
  components/nav/FeatureTabs.vue# 다중 세그먼트 pass-through
  components/ebeam/{Storage,ToolInventory,Hardware,RecipeStatus,RecipeTat,FailIssue}View.vue
                                # props fab: string → fabs: string[]
  pages/ebeam/**/[fab]/**       # 전 페이지 useFabRoute()로 이관
back_dev_home/ebeam/hitachi/
  _analytics_routes.py          # AnalyticsRequestScope.fab_names: tuple[str, ...]
  _analytics.py                 # MeasurementScope.fab_names + set 필터
  _office_meas_hist.py          # filter_clauses: 1개→term, 2개+→terms
  recipe_tat/{routes,data,contracts}.py, providers/{mock,office_example}.py
  fail_issue/{routes,data,contracts}.py, providers/{mock,office_example}.py
  meas_hist(=meas_hist feature)/providers/office_example.py  # filter_clauses 호출부만 목록 래핑
```

**바뀌지 않는 것:** storage 백엔드 전체(이미 목록형), hardware 백엔드 전체(fab은 선택된 장비의 것을 그대로 보냄 — `HardwareView.vue:184` `fabName: selectedTool.value?.fab_name`), live_alarm·skew·recipe_search·pm_planning·lateral_recipe 백엔드, `AppHeader.vue`(primary 호환 computed로 그대로 동작).

---

### Task 1: Worktree와 환경 준비

**Files:** 없음 (환경만)

- [ ] **Step 1: worktree 생성**

```bash
cd /Users/daeyoung/Codes/skewnono_v3_nuxt
git worktree add ../skewnono-multi-fab -b work/multi-fab
```

- [ ] **Step 2: frontend 의존성 설치** (worktree에는 node_modules가 없다)

```bash
cd ../skewnono-multi-fab/front-dev-home && npm install
```

- [ ] **Step 3: 기준선 확인** — worktree에는 `.venv`가 없으므로 main 트리의 절대 경로를 쓴다(이하 모든 backend 명령 동일)

```bash
cd ../skewnono-multi-fab
/Users/daeyoung/Codes/skewnono_v3_nuxt/.venv/bin/python -m pytest -q
cd front-dev-home && npm test && npm run typecheck
```

Expected: 전부 green (office.py 부재로 인한 skip 차이는 정상 — passed+skipped 합계를 기록해 둔다).

---

### Task 2: `utils/fab.ts` 다중 FAB 순수 함수 (TDD)

**Files:**
- Modify: `front-dev-home/app/utils/fab.ts`
- Test: `front-dev-home/app/utils/fab.test.ts`

**Interfaces:**
- Produces (이후 모든 태스크가 사용):
  - `canonicalFabList(fabs: Iterable<string | null | undefined>): string[]`
  - `parseFabSegment(segment: string | string[] | null | undefined): string[]` — 항상 길이 ≥ 1
  - `buildFabSegment(fabs: readonly string[]): string` — 소문자 쉼표 결합, 빈 목록 → `'r3'`
  - `toggleFabInList(fabs: readonly string[], fab: string): string[]` — 최소 1개 불변식
- Consumes: 기존 `normalizeFab`, `hasFab`, `DEFAULT_FAB`, `NO_FAB`

- [ ] **Step 1: 실패하는 테스트 작성** — `fab.test.ts`에 추가

```ts
import {
  canonicalFabList, parseFabSegment, buildFabSegment, toggleFabInList,
  DEFAULT_FAB
} from './fab'

test('canonicalFabList uppercases, dedupes, keeps order, drops blanks and the sentinel', () => {
  assert.deepEqual(canonicalFabList(['r3', 'M16B', 'R3', '', 'all', null, undefined]), ['R3', 'M16B'])
})

test('parseFabSegment splits a comma segment and falls back to R3 when nothing survives', () => {
  assert.deepEqual(parseFabSegment('r3,m16b'), ['R3', 'M16B'])
  assert.deepEqual(parseFabSegment('R3'), ['R3'])
  assert.deepEqual(parseFabSegment(''), [DEFAULT_FAB])
  assert.deepEqual(parseFabSegment(undefined), [DEFAULT_FAB])
  assert.deepEqual(parseFabSegment(',,all,'), [DEFAULT_FAB])
  // Vue Router가 배열을 줄 수도 있는 타입이므로 배열 입력도 흡수한다.
  assert.deepEqual(parseFabSegment(['r3', 'm16b']), ['R3', 'M16B'])
})

test('buildFabSegment round-trips parseFabSegment and lowercases', () => {
  assert.equal(buildFabSegment(['R3', 'M16B']), 'r3,m16b')
  assert.equal(buildFabSegment([]), 'r3')
  assert.deepEqual(parseFabSegment(buildFabSegment(['M16B', 'R3'])), ['M16B', 'R3'])
})

test('toggleFabInList adds, removes, and refuses to empty the list', () => {
  assert.deepEqual(toggleFabInList(['R3'], 'm16b'), ['R3', 'M16B'])
  assert.deepEqual(toggleFabInList(['R3', 'M16B'], 'M16B'), ['R3'])
  assert.deepEqual(toggleFabInList(['R3'], 'R3'), ['R3'])   // 마지막 1개는 못 뺀다
  assert.deepEqual(toggleFabInList(['R3'], 'all'), ['R3'])  // sentinel은 무시
})
```

- [ ] **Step 2: 실패 확인**

Run: `cd front-dev-home && npm test`
Expected: FAIL — `canonicalFabList is not exported` 계열.

- [ ] **Step 3: 구현** — `fab.ts` 끝에 추가 (`NO_FAB_CANONICAL`은 이미 모듈 내부에 있다)

```ts
// ---- 다중 FAB (Phase 1) ----
// 목록 불변식의 단일 소유자: 대문자 정규화, sentinel/공백 제거, 순서 보존 중복 제거.
export const canonicalFabList = (fabs: Iterable<string | null | undefined>): string[] => {
  const out: string[] = []
  for (const fab of fabs) {
    const normalized = normalizeFab(fab)
    if (normalized === '' || normalized === NO_FAB_CANONICAL) continue
    if (!out.includes(normalized)) out.push(normalized)
  }
  return out
}

// URL의 [fab] 세그먼트 → FAB 목록. 무효 세그먼트는 R3 하나로 강등되므로 항상 길이 ≥ 1.
export const parseFabSegment = (segment: string | string[] | null | undefined): string[] => {
  const raw = Array.isArray(segment) ? segment.join(',') : (segment ?? '')
  const fabs = canonicalFabList(raw.split(','))
  return fabs.length > 0 ? fabs : [DEFAULT_FAB]
}

// FAB 목록 → URL 세그먼트. 단일 fabSegment와 같은 규칙: 저장은 대문자, 라우팅은 소문자.
export const buildFabSegment = (fabs: readonly string[]): string => {
  const canonical = canonicalFabList(fabs)
  return (canonical.length > 0 ? canonical : [DEFAULT_FAB]).join(',').toLowerCase()
}

// 체크박스 토글. 마지막 남은 FAB 제거는 무시한다 — 선택이 비면 "아무 데이터도 없음"이
// 아니라 R3 fallback으로 점프해 버려, 사용자가 방금 한 행동과 화면이 어긋난다.
export const toggleFabInList = (fabs: readonly string[], fab: string): string[] => {
  const canonical = canonicalFabList(fabs)
  const target = normalizeFab(fab)
  if (!hasFab(target)) return canonical
  if (!canonical.includes(target)) return [...canonical, target]
  if (canonical.length === 1) return canonical
  return canonical.filter(f => f !== target)
}
```

- [ ] **Step 4: 통과 확인**

Run: `cd front-dev-home && npm test`
Expected: PASS (기존 fab.test.ts 케이스 포함 전부).

- [ ] **Step 5: Commit**

```bash
git add front-dev-home/app/utils/fab.ts front-dev-home/app/utils/fab.test.ts
git commit -m "feat(fab): add multi-fab list primitives to utils/fab"
```

---

### Task 3: navigation store `fabs[]` + persist 플러그인

**Files:**
- Modify: `front-dev-home/app/stores/navigation.ts`
- Modify: `front-dev-home/app/plugins/persist-fab.client.ts`

**Interfaces:**
- Consumes: Task 2의 `canonicalFabList`
- Produces:
  - store state `fabs: string[]` (기본 `[]` = 기억된 FAB 없음)
  - `setFabs(fabs: readonly string[]): void` — 유일한 쓰기 지점
  - `setFab(fab: Fab)` — `setFabs`로 위임 (기존 호출부 전부 그대로 동작)
  - 노출 computed: `fabs` (목록), `fab` (**primary** = `fabs[0] ?? NO_FAB` — 호환용)

- [ ] **Step 1: store 변경** — `navigation.ts`

`NavigationState`와 기본값:

```ts
import { NO_FAB, hasFab, canonicalFabList } from '~/utils/fab'

export interface NavigationState {
  toolType: ToolType
  fabs: string[]
  favorites: string[]
  selectedToolId: string
}

const defaultState: NavigationState = {
  toolType: 'cd-sem',
  fabs: [],
  favorites: [],
  selectedToolId: ''
}
```

쓰기 지점 (기존 `setFab` 본문과 주석을 교체):

```ts
  // The single write point for fabs. Invariant: canonical uppercase, deduped,
  // selection order preserved, sentinel dropped. fabs[0] is the primary fab.
  const setFabs = (fabs: readonly string[]) => {
    state.value.fabs = canonicalFabList(fabs)
  }

  // Single-select compatibility: every legacy caller funnels through the
  // same invariant. NO_FAB (or blank) clears the selection.
  const setFab = (fab: Fab) => {
    setFabs(hasFab(fab) ? [fab] : [])
  }
```

return 블록:

```ts
  return {
    state: readonly(state),
    toolType: computed(() => state.value.toolType),
    fabs: computed(() => state.value.fabs),
    // Primary-fab compatibility accessor: single-fab consumers keep reading `fab`.
    fab: computed(() => state.value.fabs[0] ?? NO_FAB),
    favorites: computed(() => state.value.favorites),
    selectedToolId: computed(() => state.value.selectedToolId),
    setToolType,
    setFabs,
    setFab,
    addFavorite,
    removeFavorite,
    toggleFavorite,
    setSelectedTool
  }
```

`normalizeFab` import가 안 쓰이게 되면 제거한다.

- [ ] **Step 2: persist 플러그인** — `persist-fab.client.ts` 본문 교체

```ts
import { useNavigationStore } from '~/stores/navigation'
import { normalizeFab } from '~/utils/fab'

// New key (was 'skewnono:fab') — old fac_id values like "R3"/"M11" are no longer valid
// fab_names, so dropping the old key avoids redirecting users to no-data URLs after deploy.
// Since Phase 1 the value is a comma-joined multi-fab list; a pre-existing single value
// reads back as a one-element list with no migration step.
const STORAGE_KEY = 'skewnono:fab_name'

// Matches fab_name shape: R or M, 1-2 digits, optional A-C suffix. Validated per token so
// one stale entry drops alone instead of resetting the whole selection.
const FAB_NAME_PATTERN = /^[RM]\d{1,2}[A-C]?$/

export default defineNuxtPlugin(() => {
  const store = useNavigationStore()

  const saved = (window.localStorage.getItem(STORAGE_KEY) ?? '')
    .split(',')
    .map(normalizeFab)
    .filter(token => FAB_NAME_PATTERN.test(token))
  if (saved.length > 0) {
    store.setFabs(saved)
  }

  watch(() => store.fabs.value, (next) => {
    if (next.length === 0) {
      window.localStorage.removeItem(STORAGE_KEY)
    } else {
      window.localStorage.setItem(STORAGE_KEY, next.join(','))
    }
  })
})
```

- [ ] **Step 3: 컴파일 확인**

Run: `cd front-dev-home && npm run typecheck && npm test`
Expected: PASS — `fab` computed가 남아 있어 미이관 소비자(useNavigation·FabSidebar·pages)가 전부 그대로 컴파일된다.

- [ ] **Step 4: Commit**

```bash
git add front-dev-home/app/stores/navigation.ts front-dev-home/app/plugins/persist-fab.client.ts
git commit -m "feat(nav): store holds a fab list; persist plugin round-trips it"
```

---

### Task 4: `useNavigation` — `toggleFab`와 다중 세그먼트 href

**Files:**
- Modify: `front-dev-home/app/composables/useNavigation.ts`
- Modify: `front-dev-home/app/components/nav/FeatureTabs.vue:77-82`
- Modify: `front-dev-home/app/pages/ebeam/{cd-sem,hv-sem,verity-sem,provision}/index.vue` (tool-type 인덱스 리다이렉트 4곳)

**Interfaces:**
- Consumes: Task 2 `buildFabSegment`, `toggleFabInList`; Task 3 `store.fabs`, `store.setFabs`
- Produces: `toggleFab(fab: Fab): void` (FabSidebar가 Task 5에서 사용)

- [ ] **Step 1: `useNavigation.ts` 수정**

import에 `buildFabSegment`, `toggleFabInList` 추가. `toolTypeHref`의 세그먼트를 교체:

```ts
    return `/ebeam/${toolType}/${buildFabSegment(store.fabs.value)}${featureSuffix}`
```

`navigateToFab`은 **본문 그대로** 둔다(단독 선택 의미 유지 — `setFab`이 이미 목록으로 위임). 그 아래에 추가:

```ts
  // Checkbox path: add/remove one fab, stay on the current feature, keep its
  // query params. Same-URL guard: toggleFabInList may return the list unchanged
  // (last-fab removal), in which case there is nothing to route to.
  const toggleFab = (fab: Fab) => {
    const current = store.fabs.value
    const next = toggleFabInList(current, fab)
    if (next.join(',') === current.join(',')) return
    store.setFabs(next)

    const toolType = store.toolType.value
    const feature = currentFeature()
    const featureEnabled = feature !== '' && featureEnabledForToolType(feature, toolType)
    if (featureEnabled && isFablessFeature(feature)) return

    const segment = buildFabSegment(next)
    if (featureEnabled) {
      router.push({ path: `/ebeam/${toolType}/${segment}/${feature}`, query: route.query })
      return
    }
    router.push(`/ebeam/${toolType}/${segment}`)
  }
```

return에 `toggleFab` 추가.

- [ ] **Step 2: `FeatureTabs.vue`** — `getFeatureRoute` 안의 세그먼트 계산을 교체한다. 현재:

```ts
  // For fab-dependent features we need a fab segment in the URL. Prefer the one already in
  // the path; on a fabless feature page there is none, so fall back to the store's last fab
  // and finally to R3. Both go through fabSegment, so a hand-typed uppercase URL does not
  // propagate uppercase into the links we build.
  const basePath = route.path.replace(FEATURE_SLUG_SUFFIX_REGEX, '')
  const pathFab = basePath.split('/')[3]
  const segment = fabSegment(pathFab || fab.value)
```

교체 후:

```ts
  // For fab-dependent features we need a fab segment in the URL. Prefer the one already in
  // the path — since Phase 1 it may be a multi-fab list ("r3,m16b"), which passes through
  // untouched so feature switches keep the whole selection. On a fabless feature page there
  // is none, so fall back to the store's fab list and finally to R3. buildFabSegment
  // lowercases, so a hand-typed uppercase URL does not propagate into the links we build.
  const basePath = route.path.replace(FEATURE_SLUG_SUFFIX_REGEX, '')
  const pathFab = basePath.split('/')[3]
  const segment = pathFab ? pathFab.toLowerCase() : buildFabSegment(fabs.value)
```

이 파일이 `fab`을 어디서 구조분해하는지 확인해 같은 곳에서 `fabs`를 꺼내고, `fabSegment` import가 더 이상 안 쓰이면 `buildFabSegment`로 바꾼다.

- [ ] **Step 3: tool-type 인덱스 리다이렉트 4곳** — `fabSegment(fab.value)` → `buildFabSegment(fabs.value)`. 예: `pages/ebeam/cd-sem/index.vue:14`:

```ts
const { fabs } = useNavigationStore()
...
navigateTo(`/ebeam/cd-sem/${buildFabSegment(fabs.value)}`, { replace: true })
```

같은 변경을 `hv-sem/index.vue:10`, `verity-sem/index.vue:10`, `provision/index.vue:10`에 적용 (각 파일의 실제 접근 방식 — `useNavigation()`인지 `useNavigationStore()`인지 — 은 열어서 따른다).

- [ ] **Step 4: 검증**

Run: `cd front-dev-home && npm run typecheck && npm test`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add front-dev-home/app/composables/useNavigation.ts front-dev-home/app/components/nav/FeatureTabs.vue \
  "front-dev-home/app/pages/ebeam/cd-sem/index.vue" "front-dev-home/app/pages/ebeam/hv-sem/index.vue" \
  "front-dev-home/app/pages/ebeam/verity-sem/index.vue" "front-dev-home/app/pages/ebeam/provision/index.vue"
git commit -m "feat(nav): toggleFab + multi-fab segments in hrefs and tool-type redirects"
```

---

### Task 5: FabSidebar 다중 선택 UI

**Files:**
- Modify: `front-dev-home/app/components/nav/FabSidebar.vue`

**Interfaces:**
- Consumes: Task 3 `fabs`/`fab`, Task 4 `toggleFab`, 기존 `navigateToFab`

- [ ] **Step 0: 루트 `DESIGN.md`를 읽는다** (시각 언어 준수 — 색은 `--sk-*` 토큰, 기존 사이드바의 zinc 계열 hover/active 관용구 유지).

- [ ] **Step 1: script 수정**

```ts
const { toolType, fab, fabs, favorites, navigateToToolType, navigateToFab, toggleFab } = useNavigation()
```

```ts
const fabItems = computed(() => fabNames.value.map(name => ({
  id: name,
  label: name,
  active: fabs.value.includes(name),
  primary: fab.value === name
})))

// 일반 클릭 = 단독 선택(기존 습관 유지), Cmd/Ctrl+클릭 = 추가·제거.
const onFabClick = (event: MouseEvent, id: string) => {
  if (event.metaKey || event.ctrlKey) toggleFab(id)
  else navigateToFab(id)
}
```

- [ ] **Step 2: template 수정** — FAB nav의 `<button v-for="item in fabItems">`를 행 컨테이너 + 본체 버튼 + 체크박스 버튼으로 재구성한다 (button 안에 button을 중첩하면 invalid HTML이라 반드시 형제로 둔다):

```vue
      <div
        v-for="item in fabItems"
        :key="item.id"
        class="group/fab relative flex items-center rounded-lg transition-all duration-200 w-full"
        :class="[
          item.active
            ? 'bg-zinc-900 text-zinc-100 dark:bg-zinc-100 dark:text-zinc-900 shadow-sm sk-fab-active'
            : 'text-zinc-700 dark:text-zinc-300 hover:bg-zinc-100 dark:hover:bg-zinc-800',
          item.active && !item.primary ? 'opacity-85' : ''
        ]"
      >
        <button
          :aria-label="sidebarCollapsed ? item.label : undefined"
          :aria-pressed="item.active"
          :title="sidebarCollapsed ? `${item.label} (Cmd/Ctrl+클릭: 추가 선택)` : undefined"
          type="button"
          class="flex items-center flex-1 min-w-0 cursor-pointer"
          :class="sidebarCollapsed ? 'justify-center px-0 py-2' : 'gap-2 px-3 py-1.5'"
          @click="onFabClick($event, item.id)"
        >
          <span
            v-if="!sidebarCollapsed"
            class="text-sm font-semibold tracking-wide tabular-nums truncate"
          >{{ item.label }}</span>
          <span
            v-else
            class="text-[11px] font-semibold tracking-tight"
          >{{ item.label }}</span>
        </button>
        <button
          v-if="!sidebarCollapsed"
          type="button"
          role="checkbox"
          :aria-checked="item.active"
          :aria-label="`${item.label} 다중 선택 토글`"
          class="mr-2 flex items-center justify-center w-4 h-4 rounded border transition-colors shrink-0"
          :class="item.active
            ? 'bg-white/20 border-white/40 dark:bg-zinc-900/20 dark:border-zinc-900/40 opacity-100'
            : 'border-(--sk-border-soft) opacity-0 group-hover/fab:opacity-100'"
          @click.stop="toggleFab(item.id)"
        >
          <UIcon
            v-if="item.active"
            name="i-lucide-check"
            class="w-3 h-3"
          />
        </button>
      </div>
```

- [ ] **Step 3: 검증**

Run: `cd front-dev-home && npm run typecheck && npm run lint`
Expected: PASS. (브라우저 동작 확인은 Task 11의 verify에서 일괄.)

- [ ] **Step 4: Commit**

```bash
git add front-dev-home/app/components/nav/FabSidebar.vue
git commit -m "feat(sidebar): multi-select fabs via checkbox and Cmd/Ctrl+click"
```

---

### Task 6: `useFabRoute` + 전체 `[fab]` 페이지 이관 + `FabScopeNotice`

**Files:**
- Create: `front-dev-home/app/composables/useFabRoute.ts`
- Create: `front-dev-home/app/components/nav/FabScopeNotice.vue`
- Modify: `[fab]` 배하 **모든** 페이지 (아래 표)

**Interfaces:**
- Consumes: Task 2 `parseFabSegment`; Task 3 `setFabs`
- Produces: `useFabRoute(toolType: ToolType): { fabs: ComputedRef<string[]>, primaryFab: ComputedRef<string>, fabsKey: ComputedRef<string> }`
  - `fabs`는 항상 길이 ≥ 1 (parseFabSegment 보장), `fabsKey`는 `fabs.join(',')`
  - **이번 태스크에서 view에는 여전히 `:fab`(단일 string)을 넘긴다** — view props는 Task 9·10에서 바뀐다. 이 경계에서 앱은 "URL은 다중, 화면은 primary" 상태로 일관된다.

- [ ] **Step 1: `useFabRoute.ts` 생성**

```ts
import type { ToolType } from '~/stores/navigation'
import { DEFAULT_FAB, parseFabSegment } from '~/utils/fab'

// Every [fab] page's shared boilerplate: parse the (possibly multi) URL segment,
// seed the store, and keep it synced. Replaces the copy-pasted
// `String(route.params.fab).toUpperCase()` + setFab + watch block, which would
// corrupt the store with a raw "R3,M16B" string once segments can be lists.
export const useFabRoute = (toolType: ToolType) => {
  const route = useRoute()
  const { setToolType, setFabs } = useNavigation()

  const fabs = computed(() => parseFabSegment(route.params.fab as string | string[] | undefined))
  const primaryFab = computed(() => fabs.value[0] ?? DEFAULT_FAB)
  const fabsKey = computed(() => fabs.value.join(','))

  setToolType(toolType)
  setFabs(fabs.value)

  // Guard on the raw param: on leave-navigation the param empties, and syncing
  // that would clobber the remembered selection with the R3 fallback.
  watch(() => route.params.fab, (next) => {
    if (next == null || next === '') return
    setFabs(parseFabSegment(next as string | string[]))
  })

  return { fabs, primaryFab, fabsKey }
}
```

- [ ] **Step 2: `FabScopeNotice.vue` 생성**

```vue
<script setup lang="ts">
const props = defineProps<{
  fabs: string[]
  primaryFab: string
}>()

const visible = computed(() => props.fabs.length > 1)
</script>

<template>
  <div
    v-if="visible"
    class="flex items-center gap-1.5 px-3 py-1.5 mb-2 rounded-lg text-xs text-(--sk-ink-muted) bg-(--sk-border-soft)"
  >
    <UIcon
      name="i-lucide-info"
      class="w-3.5 h-3.5 shrink-0"
    />
    <span>{{ primaryFab }} 기준 표시 — 이 화면의 다중 FAB 지원은 추후 제공됩니다.</span>
  </div>
</template>
```

- [ ] **Step 3: 페이지 이관** — 모든 `[fab]` 페이지의 boilerplate를 교체한다. 패턴 (cd-sem storage 예시):

```vue
<script setup lang="ts">
const { fabs, primaryFab } = useFabRoute('cd-sem')
</script>
```

기존 `route`/`setToolType`/`setFab`/`applyFab`/`watch` 블록과 `import type { Fab }`을 전부 지운다. template의 `:fab="fabName"`은 `:fab="primaryFab"`으로 바꾼다(이번 태스크 한정 — Task 9·10 대상 페이지 포함 전부).

대상과 template 추가 사항:

| 페이지 (cd-sem / hv-sem 쌍은 tool-type 문자열만 다름) | useFabRoute 인자 | template |
| --- | --- | --- |
| `cd-sem/[fab]/storage/index.vue`, `hv-sem` 쌍 | `'cd-sem'`/`'hv-sem'` | `:fab="primaryFab"` |
| `cd-sem/[fab]/hardware.vue`, `hv-sem` 쌍 | 〃 | 〃 |
| `cd-sem/[fab]/recipe-status.vue`, `hv-sem` 쌍 | 〃 | 〃 |
| `cd-sem/[fab]/index.vue`, `hv-sem` 쌍 | 〃 | `:fab="primaryFab"` + `:eyebrow="\`CD-SEM · ${fabs.join(' + ')}\`"` |
| `verity-sem/[fab]/index.vue`, `provision/[fab]/index.vue` | `'verity-sem'`/`'provision'` | `:fab="primaryFab"` + `:title="\`VeritySEM - ${fabs.join(' + ')}\`"` (provision은 `Provision - …`) — cd-sem landing과 동일 boilerplate 구조라 script 대체 패턴이 같다 |
| `cd-sem/[fab]/skew-check.vue` | `'cd-sem'` | `:fab="primaryFab"` + view 위에 `<FabScopeNotice :fabs="fabs" :primary-fab="primaryFab" />` |
| `cd-sem/[fab]/live-alarm.vue`, `hv-sem` 쌍 | 〃 | 〃 (notice 포함) |
| `cd-sem/[fab]/recipe-search/{index,compare,lateral,open,meas-hist}.vue`, `hv-sem` 쌍 (10개) | 〃 | 〃 (notice 포함) |
| `cd-sem/[fab]/pm-planning.vue` | `'cd-sem'` | 〃 (notice 포함) |

리다이렉트 스텁 `{cd-sem,hv-sem}/[fab]/{recipe-tat/index,fail-issue}.vue`는 `to.params.fab`을 원문 그대로 통과시키므로 **수정하지 않는다** (다중 세그먼트도 그대로 흐른다 — 눈으로만 확인).

주의: 각 페이지의 기존 script가 미묘하게 다르다(§4 탐사 보고 — bare `setFab` vs `applyFab` 가드 vs `route.params.fab` 직접 watch). 파일을 하나씩 열어 **전체 script를 위 패턴으로 대체**하고, 페이지 고유 로직(예: recipe-search 페이지들의 추가 상태)은 남긴다.

- [ ] **Step 4: 검증**

Run: `cd front-dev-home && npm run typecheck && npm test && npm run lint`
Expected: PASS.

- [ ] **Step 5: Commit** (편집한 페이지 경로를 전부 명시 — 긴 목록이면 몇 커밋으로 쪼갠다: composable+notice / cd-sem 페이지 / hv-sem 페이지 / 기타)

```bash
git add front-dev-home/app/composables/useFabRoute.ts front-dev-home/app/components/nav/FabScopeNotice.vue
git commit -m "feat(nav): useFabRoute parses multi-fab segments; FabScopeNotice for single-fab pages"
# 이어서 페이지 이관 커밋(명시 경로)
git commit -m "refactor(pages): route every [fab] page through useFabRoute" -- <편집한 페이지 경로들>
```

---

### Task 7: 백엔드 — analytics scope·mock·계약 목록화 (TDD)

**Files:**
- Modify: `back_dev_home/ebeam/hitachi/_analytics_routes.py`
- Modify: `back_dev_home/ebeam/hitachi/_analytics.py:21-56`
- Modify: `back_dev_home/ebeam/hitachi/recipe_tat/{routes,data,contracts}.py`, `providers/mock.py`
- Modify: `back_dev_home/ebeam/hitachi/fail_issue/{routes,data,contracts}.py`, `providers/mock.py`
- Test: `tests/test_recipe_analytics_home.py`, `back_dev_home/ebeam/hitachi/{recipe_tat,fail_issue}/tests/test_contract.py`

**Interfaces:**
- Produces:
  - `AnalyticsRequestScope.fab_names: tuple[str, ...]` (빈 tuple = 필터 없음; 쉼표 파싱·strip·대문자)
  - `MeasurementScope.fab_names: tuple[str, ...] | None`
  - data/provider 시그니처: `get_ranking(tool_type, fab_names: tuple[str, ...] | None, start_date, end_date, limit=0, lot_cd=None)` — summary/daily_trend/devices 및 fail_issue 5종 동형
  - 응답 meta: `"fab_name": …` → `"fab_names": [...]` (양 feature의 모든 route + SummaryPayload)
- 유지: `MeasHistRow.fab_name`, `FailRow.fab_name` (row 단위 — 절대 변경 금지)

- [ ] **Step 1: 실패하는 route 테스트 추가** — `tests/test_recipe_analytics_home.py`의 `TestRecipeAnalyticsRoutes`에:

```python
    def test_comma_fab_names_filter_as_a_union(self):
        r3 = self.client.get(
            "/api/cdsem/recipe-tat/ranking?fab_name=R3"
        ).get_json()
        both = self.client.get(
            "/api/cdsem/recipe-tat/ranking?fab_name=R3,M16B"
        ).get_json()
        self.assertEqual(both["fab_names"], ["R3", "M16B"])
        # Union: the combined pool covers at least the single-fab pool.
        self.assertGreaterEqual(len(both["rows"]), len(r3["rows"]))

    def test_fail_issue_summary_echoes_fab_names_list(self):
        summary = self.client.get(
            "/api/cdsem/fail-issue/summary?fab_name=r3,m16b"
        ).get_json()
        self.assertEqual(summary["fab_names"], ["R3", "M16B"])
```

- [ ] **Step 2: 실패 확인**

Run: `/Users/daeyoung/Codes/skewnono_v3_nuxt/.venv/bin/python -m pytest tests/test_recipe_analytics_home.py -q` (worktree 루트에서)
Expected: FAIL — `KeyError: 'fab_names'`.

- [ ] **Step 3: `_analytics_routes.py` 구현**

```python
@dataclass(frozen=True)
class AnalyticsRequestScope:
    tool_type: ToolType
    fab_names: tuple[str, ...]
    start_date: str
    end_date: str
    lot_cd: str | None
    limit: int
```

`resolve_analytics_scope`의 해당 필드:

```python
    return AnalyticsRequestScope(
        tool_type=tool_type,
        fab_names=tuple(
            part.strip().upper()
            for part in (request.args.get("fab_name") or "").split(",")
            if part.strip()
        ),
        start_date=start_date,
        end_date=end_date,
        lot_cd=(request.args.get("lot_cd") or "").strip() or None,
        limit=max(0, limit),
    )
```

(쿼리 키는 `fab_name` 그대로 — storage의 기존 관행과 동일하게 값만 쉼표 목록이다.)

- [ ] **Step 4: `_analytics.py` 구현**

```python
class MeasurementScope:
    tool_type: ToolType | None
    fab_names: tuple[str, ...] | None
    start_date: str | None
    end_date: str | None
    lot_cd: str | None = None
```

`filter_measurements`:

```python
    fab_norms = (
        {fab.upper() for fab in scope.fab_names} if scope.fab_names else None
    )
    ...
        if fab_norms and str(row["fab_name"]).upper() not in fab_norms:
            continue
```

- [ ] **Step 5: recipe_tat 전파** — `routes.py` 4개 handler에서 `scope.fab_name` → `scope.fab_names or None`, echo dict `"fab_name": scope.fab_name` → `"fab_names": list(scope.fab_names)`. `data.py`·`providers/mock.py`의 모든 `fab_name: str | None` 파라미터 → `fab_names: tuple[str, ...] | None` (이름·타입 함께). mock의 `_filter_rows`는 `lru_cache` 유지 — tuple이라 hashable. `contracts.py:54` `SummaryPayload.fab_name: str | None` → `fab_names: list[str]`, mock의 summary 조립부에서 `"fab_names": list(fab_names or [])`. **`MeasHistRow.fab_name`(:24)은 그대로.**

- [ ] **Step 6: fail_issue 전파** — 같은 규칙: `routes.py` 5개 handler, `data.py`, `providers/mock.py`(`_filter_rows`·`get_summary`(:242의 echo)·`get_align_ranking`·`get_meas_ranking`·`get_daily_trend`·`get_devices`), `contracts.py:51` `SummaryPayload.fab_name` → `fab_names: list[str]`. **`FailRow.fab_name`(:31)은 그대로.**

- [ ] **Step 7: contract 테스트 갱신** — 두 `tests/test_contract.py`의 `_default_scope`가 `fab_name=None`을 돌려주는 자리를 `fab_names=None`으로 (변수명 포함), `data.get_*` 호출 인자도 맞춘다.

- [ ] **Step 7b: mock docstring 갱신** — 두 `providers/mock.py` 모듈 docstring에 다중 FAB 필터 동작(대소문자 무시 set 합산, 빈 tuple/None = 필터 없음)을 한 줄 명기한다. mock이 office 실물의 대역이라는 CLAUDE.md 원칙(spec 5.3).

- [ ] **Step 8: 통과 확인**

Run: `/Users/daeyoung/Codes/skewnono_v3_nuxt/.venv/bin/python -m pytest back_dev_home/ebeam/hitachi/recipe_tat back_dev_home/ebeam/hitachi/fail_issue tests/test_recipe_analytics_home.py -q`
Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add back_dev_home/ebeam/hitachi/_analytics_routes.py back_dev_home/ebeam/hitachi/_analytics.py \
  back_dev_home/ebeam/hitachi/recipe_tat/routes.py back_dev_home/ebeam/hitachi/recipe_tat/data.py \
  back_dev_home/ebeam/hitachi/recipe_tat/contracts.py back_dev_home/ebeam/hitachi/recipe_tat/providers/mock.py \
  back_dev_home/ebeam/hitachi/fail_issue/routes.py back_dev_home/ebeam/hitachi/fail_issue/data.py \
  back_dev_home/ebeam/hitachi/fail_issue/contracts.py back_dev_home/ebeam/hitachi/fail_issue/providers/mock.py \
  back_dev_home/ebeam/hitachi/recipe_tat/tests/test_contract.py back_dev_home/ebeam/hitachi/fail_issue/tests/test_contract.py \
  tests/test_recipe_analytics_home.py
git commit -m "feat(analytics): fab_name scope becomes a fab_names tuple across recipe-tat and fail-issue"
```

---

### Task 8: 백엔드 — `filter_clauses` terms + office adapter 전파

**Files:**
- Modify: `back_dev_home/ebeam/hitachi/_office_meas_hist.py:106-119`
- Modify: `back_dev_home/ebeam/hitachi/recipe_tat/providers/office_example.py`
- Modify: `back_dev_home/ebeam/hitachi/fail_issue/providers/office_example.py`
- Modify: `back_dev_home/meas_hist/providers/office_example.py` (filter_clauses 호출부만)
- Test: `tests/test_office_adapter_parity.py` 실행으로 시그니처 일치 검증 (기존 스위트)

**Interfaces:**
- Produces: `filter_clauses(fab_names: Sequence[str] | None, start_date, end_date, lot_ids=None)` — 1개면 기존과 동일한 `term`, 2개 이상이면 `terms`
- Consumes: Task 7의 provider 시그니처 (`fab_names: tuple[str, ...] | None`)

- [ ] **Step 1: 실패하는 단위 테스트** — `tests/test_recipe_analytics_home.py`에 추가 (OpenSearch 불필요, 순수 함수):

```python
from back_dev_home.ebeam.hitachi._office_meas_hist import FAB_NAME_KW, filter_clauses


class TestFilterClauses(unittest.TestCase):
    def test_single_fab_keeps_the_term_clause_shape(self):
        clauses = filter_clauses(("r3",), "2026-01-01", "2026-01-31")
        self.assertIn({"term": {FAB_NAME_KW: "R3"}}, clauses)

    def test_multiple_fabs_become_one_terms_clause(self):
        clauses = filter_clauses(("r3", "M16B"), "2026-01-01", "2026-01-31")
        self.assertIn({"terms": {FAB_NAME_KW: ["R3", "M16B"]}}, clauses)

    def test_no_fabs_add_no_fab_clause(self):
        clauses = filter_clauses(None, "2026-01-01", "2026-01-31")
        self.assertFalse(any("term" in c and FAB_NAME_KW in c.get("term", {}) for c in clauses))
        self.assertFalse(any(FAB_NAME_KW in c.get("terms", {}) for c in clauses))
```

(`FAB_NAME_KW = "fab_name.keyword"`는 `_office_meas_hist.py:85`의 모듈 레벨 이름 — 그대로 import된다.)

- [ ] **Step 2: 실패 확인**

Run: `/Users/daeyoung/Codes/skewnono_v3_nuxt/.venv/bin/python -m pytest tests/test_recipe_analytics_home.py -q`
Expected: FAIL — tuple 인자에서 `AttributeError: 'tuple' object has no attribute 'strip'`.

- [ ] **Step 3: `filter_clauses` 구현**

```python
def filter_clauses(
    fab_names: Sequence[str] | None,
    start_date: str | None,
    end_date: str | None,
    lot_ids: list[str] | None = None,
) -> list[dict[str, Any]]:
    clauses: list[dict[str, Any]] = [_range_clause(start_date, end_date)]
    # fab_name is stored uppercase (M16A, R3, ...); the mocks compare
    # case-insensitively, so uppercase the terms for parity. One fab keeps the
    # exact single-`term` shape existing office queries produce.
    wanted = [fab.strip().upper() for fab in (fab_names or []) if fab.strip()]
    if len(wanted) == 1:
        clauses.append({"term": {FAB_NAME_KW: wanted[0]}})
    elif wanted:
        clauses.append({"terms": {FAB_NAME_KW: wanted}})
    if lot_ids is not None:
        clauses.append({"terms": {LOT_ID_KW: lot_ids}})
    return clauses
```

(`Sequence`는 `collections.abc`에서 import.)

- [ ] **Step 4: office_example 전파**
  - `recipe_tat/providers/office_example.py`: 모든 공개 함수의 `fab_name: str | None` → `fab_names: tuple[str, ...] | None` (Task 7의 mock과 동일 시그니처 — parity 테스트가 이것을 강제한다). `_filter_clauses(fab_name, …)` 호출부는 `_filter_clauses(fab_names, …)`. summary echo `fab_name=fab_name` → `fab_names=list(fab_names or [])`.
  - `fail_issue/providers/office_example.py`: 동일 (호출부 `:141`, `:187`, `:289`, `:328`, `:377`).
  - `meas_hist/providers/office_example.py`: route는 단일 유지이므로 함수 시그니처는 그대로 두고, `filter_clauses(fab_name, …)` 호출부만 `filter_clauses((fab_name,) if fab_name else None, …)`으로 래핑.

- [ ] **Step 5: 통과 확인**

Run: `/Users/daeyoung/Codes/skewnono_v3_nuxt/.venv/bin/python -m pytest tests/ back_dev_home -q`
Expected: PASS (worktree라 office.py 사본이 없어 skip 증가는 정상 — passed+skipped 합계가 main 기준선과 같아야 한다).

- [ ] **Step 6: Commit**

```bash
git add back_dev_home/ebeam/hitachi/_office_meas_hist.py \
  back_dev_home/ebeam/hitachi/recipe_tat/providers/office_example.py \
  back_dev_home/ebeam/hitachi/fail_issue/providers/office_example.py \
  back_dev_home/meas_hist/providers/office_example.py \
  tests/test_recipe_analytics_home.py
git commit -m "feat(office): filter_clauses takes a fab list and emits a terms clause for 2+"
```

---

### Task 9: Storage·ToolInventory·Hardware view 다중화

**Files:**
- Modify: `front-dev-home/app/composables/useSemListApi.ts:42-51`
- Modify: `front-dev-home/app/composables/useStorageApi.ts`
- Modify: `front-dev-home/app/components/ebeam/StorageView.vue`
- Modify: `front-dev-home/app/components/ebeam/ToolInventoryView.vue`
- Modify: `front-dev-home/app/components/ebeam/HardwareView.vue`
- Modify: `front-dev-home/app/components/ebeam/storage/PpidUnavailablePanel.vue` (표시 문자열만)
- Modify: 해당 페이지 6+2개 — `{cd-sem,hv-sem}/[fab]/{storage/index,hardware,index}.vue`, `{verity-sem,provision}/[fab]/index.vue` — `:fab="primaryFab"` → `:fabs="fabs"`

**Interfaces:**
- Consumes: Task 6 `useFabRoute().fabs`
- Produces: 세 view의 props가 `fabs: string[]`로 바뀐다. `useSemListApi.filterRows(rows, toolType, fab: Fab | readonly Fab[])`.

- [ ] **Step 1: `useSemListApi.filterRows` 확장**

```ts
  const filterRows = (rows: SemListRow[], toolType: ToolType, fab: Fab | readonly Fab[] = NO_FAB): SemListRow[] => {
    // Normalized once, not per row: row.fab_name carries whatever casing its source DB used,
    // so the comparison has to be case-insensitive — a raw `===` empties the whole list.
    // An empty target set means "no fab filter".
    const list = Array.isArray(fab) ? fab : [fab]
    const targets = new Set(list.filter(hasFab).map(normalizeFab))
    return rows.filter((row) => {
      if (classifyToolType(row.eqp_model_cd) !== toolType) return false
      if (targets.size > 0 && !targets.has(normalizeFab(row.fab_name))) return false
      return true
    })
  }
```

- [ ] **Step 2: `StorageView.vue`**
  - props: `fab: Fab` → `fabs: string[]`.
  - `const fabsKey = computed(() => props.fabs.join(','))`.
  - useAsyncData 두 곳: key `` () => `storage:${storageTool}:${fabsKey.value}` ``, fetch `fetchStorageRows(props.fabs, abortController.signal)` / `fetchPpidUnavailableRows(props.fabs, abortController.signal)`, watch `[fabsKey]`.
  - rows 필터 (:275-287):

```ts
const wantedFabs = computed(() => new Set(props.fabs.map(normalizeFab)))
const rows = computed(() => (data.value ?? []).filter(row =>
  classifyToolType(row.eqp_model_cd) === props.toolType && wantedFabs.value.has(normalizeFab(row.fab_name))
))
const ppidUnavailableRows = computed(() => (ppidUnavailableData.value?.rows ?? []).filter(row =>
  (row.eqp_model_cd === '' || classifyToolType(row.eqp_model_cd) === props.toolType)
  && (wantedFabs.value.has(normalizeFab(row.fab_name)) || row.fab_name === '')
))
```

  - eyebrow (:240): `` `${props.toolLabel} · ${props.fabs.join(' + ')}` ``.
  - `PpidUnavailablePanel`로 내려가는 `:fab="props.fab"` (:209) → `:fab="props.fabs.join(' + ')"` (패널의 prop은 표시 전용 string이라 그대로 둔다).
  - `sameFab` import가 안 쓰이면 제거.
- [ ] **Step 3: `useStorageApi.ts`** — `fetchByUrlFab`/`fetchPpidUnavailableByUrlFab` 헬퍼를 지우고(다른 소비자 없음을 `grep -rn "fetchByUrlFab" app/`으로 확인 후) StorageView가 목록 함수를 직접 쓰게 한다.
- [ ] **Step 4: `ToolInventoryView.vue`**
  - props `fab: Fab` → `fabs: string[]`; `:190-194`의 `filterRows(allRows.value ?? [], props.toolType, props.fab)` → `props.fabs`.
  - `goToHardware` (:211-214): `` navigateTo(`/ebeam/${props.toolType}/${buildFabSegment(props.fabs)}/hardware`) `` — 다중 선택을 hardware로 그대로 들고 간다.
  - CSV 파일명 (:308): `` `${props.toolType}-${props.fabs.join('+').toLowerCase()}-tool-inventory-${today}.csv` ``.
- [ ] **Step 5: `HardwareView.vue`**
  - props `fab: Fab` → `fabs: string[]`; `const fabsKey = computed(() => props.fabs.join(','))`.
  - `:85` `filterRows(allRows.value ?? [], props.toolType, props.fabs)`.
  - 캐시 키 3곳(:179, :203, :235): `${props.fab}` → `${props.fabs.join(',')}` (한 번 평가되는 template literal 성질은 유지 — :175-177 주석 참조).
  - watch 배열의 `() => props.fab` → `fabsKey`.
  - **fetchService의 `fabName: selectedTool.value?.fab_name`은 세 곳 모두 그대로** — 장비 자신의 fab을 보내는 것이 옳다.
  - identity (:91): `` `${props.toolLabel} · ${props.fabs.join(' + ') || '—'}` ``.
- [ ] **Step 6: 페이지 8개** — `:fab="primaryFab"` → `:fabs="fabs"` (`useFabRoute` 구조분해에 `fabs`가 이미 있다). landing 페이지의 eyebrow/title은 Task 6에서 이미 `fabs.join(' + ')`.
- [ ] **Step 6b: row 테이블의 FAB 컬럼 확인** — spec 4.6의 완료 조건: 2개 이상 선택 시 행 귀속이 보여야 한다. StorageView의 스토리지 테이블과 ToolInventoryView의 장비 테이블에 `fab_name` 컬럼이 이미 있는지 template에서 확인하고, 없으면 컬럼을 추가한다(항상 표시 — 조건부 표시로 레이아웃을 흔들지 않는다).
- [ ] **Step 7: 검증**

Run: `cd front-dev-home && npm run typecheck && npm test && npm run lint`
Expected: PASS.

- [ ] **Step 8: Commit** — 편집 파일 명시 경로로 `feat(views): storage/inventory/hardware render the selected fab union`.

---

### Task 10: RecipeStatus·RecipeTat·FailIssue view + API composable 다중화

**Files:**
- Modify: `front-dev-home/app/composables/useRecipeTatApi.ts`
- Modify: `front-dev-home/app/composables/useFailIssueApi.ts`
- Modify: `front-dev-home/app/components/ebeam/RecipeStatusView.vue`
- Modify: `front-dev-home/app/components/ebeam/RecipeTatView.vue`
- Modify: `front-dev-home/app/components/ebeam/FailIssueView.vue`
- Modify: `{cd-sem,hv-sem}/[fab]/recipe-status.vue` — `:fab="primaryFab"` → `:fabs="fabs"`

**Interfaces:**
- Consumes: Task 7 응답 meta `fab_names: string[]`
- Produces: `RecipeTatQuery.fabNames?: string[]`, `FailIssueQuery.fabNames?: string[]`; view props `fabs: string[]`

- [ ] **Step 1: `useRecipeTatApi.ts`**
  - `RecipeTatQuery.fabName?: string` → `fabNames?: string[]`.
  - `buildQuery`: `if (params.fabName)` 분기 →

```ts
  if (params.fabNames?.length) query.fab_name = params.fabNames.join(',')
```

  - `fetchRecipeTatDevices`의 scope 재조립 (:139-156): `fabName: params.fabName` → `fabNames: params.fabNames`.
  - 응답 타입 4곳(:19, :30, :51, :69): `fab_name: string | null` → `fab_names: string[]`.
- [ ] **Step 2: `useFailIssueApi.ts`** — 동일 규칙 (Query 타입, buildQuery, fetchDevices scope :172-177, 응답 타입 :7·:37·:57·:79·:98). `FailIssueToolType` export는 그대로.
- [ ] **Step 3: `RecipeStatusView.vue`** — props `fab: string` → `fabs: string[]`; eyebrow (:4) `` `${toolLabel} · ${fabs.join(' + ')}` ``; 자식 두 곳(:41, :49) `:fab="fab"` → `:fabs="fabs"`.
- [ ] **Step 4: `RecipeTatView.vue`**
  - props `fab: string` → `fabs: string[]`; `const primaryFab = computed(() => props.fabs[0] ?? DEFAULT_FAB)`.
  - queryParams (:348-356): `fabName: props.fab || undefined` → `fabNames: props.fabs.length > 0 ? props.fabs : undefined`.
  - 캐시 키 2곳(:360-364, :382-385): `${queryParams.value.fabName ?? 'ALL'}` → `${queryParams.value.fabNames?.join(',') ?? 'ALL'}`.
  - identity (:308): `fabs.join(' + ')`.
  - `EbeamRecipeRowActions` (:243) `:fab="fab"` → `:fab="primaryFab"` — recipe 상세 화면은 Phase B까지 단일 FAB registry라 대표 FAB으로 보낸다.
  - CSV (:685-686): `` const fab = (props.fabs.join('+') || 'all').toLowerCase() ``.
- [ ] **Step 5: `FailIssueView.vue`** — 같은 규칙 (:284-291 props, :338-345 queryParams, :347-351·:370-373 캐시 키, :297 identity, :232·:255 RowActions → `primaryFab`, :661-662 CSV).
- [ ] **Step 6: recipe-status 페이지 2개** — `:fabs="fabs"`.
- [ ] **Step 7: 검증**

Run: `cd front-dev-home && npm run typecheck && npm test && npm run lint`
Expected: PASS. 이어서 홈 E2E 스모크: worktree에서 Flask(`PORT=5051 /Users/daeyoung/Codes/skewnono_v3_nuxt/.venv/bin/python index.py`) 없이도 mock 검증은 Task 11에서 일괄하므로 여기서는 컴파일 계열만.

- [ ] **Step 8: Commit** — 명시 경로로 `feat(recipe-status): tat/fail-issue query and render the fab union`.

---

### Task 11: 문서·전체 검증·merge·사후 작업

**Files:**
- Modify: `back_dev_home/ebeam/hitachi/recipe_tat/MIGRATION.md`, `back_dev_home/ebeam/hitachi/fail_issue/MIGRATION.md`, `back_dev_home/meas_hist/MIGRATION.md` — office adapter 시그니처가 `fab_names: tuple[str, ...] | None`(meas_hist는 호출부 래핑만)임을 한 줄씩 기록

- [ ] **Step 1: MIGRATION.md 3곳에 변경 기록** 후 `npm run lint:md` (루트).
- [ ] **Step 2: worktree 전체 검증**

```bash
cd ../skewnono-multi-fab
/Users/daeyoung/Codes/skewnono_v3_nuxt/.venv/bin/python -m pytest -q
cd front-dev-home && npm test && npm run typecheck && npm run lint
```

Expected: 전부 green.

- [ ] **Step 3: merge & push** (main 트리에서)

```bash
cd /Users/daeyoung/Codes/skewnono_v3_nuxt
git merge --ff-only work/multi-fab && git push
git worktree remove ../skewnono-multi-fab && git branch -d work/multi-fab
git worktree list   # main 트리 하나만 남았는지 확인
```

ff-only가 거부되면(다른 세션이 main을 진전시킨 경우) worktree에서 `git rebase main` 후 재시도 — 충돌 시 auto-merge를 믿지 말고 테스트를 다시 돌린다(동시 세션 merge 위험).

- [ ] **Step 4: 사후 작업 — stale office.py 갱신** (main 트리에는 `recipe_tat/providers/office.py` gitignored 사본이 있고, `filter_clauses`·시그니처 변경으로 stale이 되어 **앱 부팅이 깨질 수 있다**)

```bash
/Users/daeyoung/Codes/skewnono_v3_nuxt/.venv/bin/python -m scripts.sync_office_adapters recipe_tat
```

- [ ] **Step 5: 부팅 + 스모크**

```bash
/Users/daeyoung/Codes/skewnono_v3_nuxt/.venv/bin/python index.py &
sleep 3
curl -s "http://localhost:5050/api/health/providers" -b "LASTUSER=local-dev" | head -c 400
curl -s "http://localhost:5050/api/cdsem/recipe-tat/summary?fab_name=R3,M16B" -b "LASTUSER=local-dev" | head -c 300
```

Expected: providers 전부 mock, summary의 `fab_names: ["R3","M16B"]`. (rate limit 20 req/5s 유의.)

- [ ] **Step 6: 브라우저 검증** — `verify` skill 절차로 Nuxt(`npm run dev`) 기동 후 Playwright MCP:
  1. 사이드바에서 R3 클릭 → M16B 체크박스 추가 → URL이 `/ebeam/cd-sem/r3,m16b`로 바뀌는지.
  2. storage 페이지에서 두 FAB 행이 함께 보이고 fab_name 컬럼으로 구분되는지.
  3. recipe-status(tat 탭)가 합산 데이터를 그리는지.
  4. 새로고침 후 선택 유지(URL·localStorage 왕복).
  5. skew-check로 이동 시 "R3 기준 표시…" 힌트 1줄.
  6. Cmd+클릭 토글, 마지막 FAB 제거 불가.
  - 스크린샷은 `.playwright-mcp/screenshots/multi-fab-*.png`.
- [ ] **Step 7: 발견된 문제를 고치고 최종 커밋·푸시.** 완료 조건: `git worktree list`에 main 트리 하나, main이 push됨, 전체 스위트 green, 브라우저 6항목 통과.
