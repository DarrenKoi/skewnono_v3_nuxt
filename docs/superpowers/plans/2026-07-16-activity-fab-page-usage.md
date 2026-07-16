# Activity Fab별 페이지 사용 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the activity page's "SEM List 모델별 사용" card with a "Fab별 페이지 사용" card that lets you pick a fab and see that fab's most-activated pages.

**Architecture:** A new `get_fab_page_usage()` data function aggregates per-fab page counts from the in-memory `_users` mock (fab is a new per-user field), exposed at `GET /activity/fabs`. The frontend swaps the SEM-model composable/card for a fab composable and a two-pane card (fab selector left, page bar-list right). The SEM-model endpoint, types, and `ModelBarList.vue` are deleted.

**Tech Stack:** Flask (Python, `unittest`), Nuxt 4 + NuxtUI (Vue 3 `<script setup>`, `useAsyncData`), TypeScript.

## Global Constraints

- Home phase only: all reads use the in-memory `_users` dict; the `is_cloud()` branch imports a not-yet-existent `_office_reader` symbol and relies on `try/except` to fall back to the mock. Do **not** create `_office_reader.py`.
- Per-window page counts are **approximations** via the existing `_scale_features()` helper (the mock carries only lifetime `by_feature` totals). Reuse it; do not invent per-day-per-feature storage.
- Unaffiliated traffic (real `record_request` with `fab=None`) rolls up under the literal bucket `"미지정"`.
- Only fabs with `total > 0` appear, sorted by `total` desc then `fab` asc.
- Feature/page slugs come from `back_dev_home/_logging/feature_map.py`; Korean labels from `front-dev-home/app/utils/activity.ts`. Do not rename slugs.
- Commit only when the user asks (project rule). Each task's "Commit" step stages the change; run the actual `git commit` only on user instruction.
- Backend tests: `.venv/bin/python -m unittest tests.test_activity_home`. Frontend checks: `npm run typecheck` and `npm run lint` from `front-dev-home/`.

---

### Task 1: Backend — fab field, `get_fab_page_usage`, `/activity/fabs`

**Files:**
- Modify: `back_dev_home/activity/data.py`
- Modify: `back_dev_home/activity/routes.py`
- Test: `tests/test_activity_home.py` (create)

**Interfaces:**
- Consumes: existing `_UserState`, `_users`, `_lock`, `_scale_features`, `_top_features`, `_now`, `_iso`, `_today`, `seed_demo_users`.
- Produces:
  - `FabPageCount = TypedDict("feature": str, "count": int)`
  - `FabUsageRow = TypedDict("fab": str, "total": int, "pages": list[FabPageCount])`
  - `FabUsageResponse = TypedDict("generated_at": str, "fabs_7d": list[FabUsageRow], "fabs_30d": list[FabUsageRow])`
  - `get_fab_page_usage() -> FabUsageResponse`
  - Route `GET /activity/fabs`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_activity_home.py`:

```python
"""Home-safe tests for the activity fab-page-usage aggregation.

Run only this file:
    .venv/bin/python -m unittest tests.test_activity_home
"""

from __future__ import annotations

import unittest

from back_dev_home.activity import data


class FabPageUsageTestCase(unittest.TestCase):
    def setUp(self):
        # Isolate from any live record_request traffic and other tests.
        data._users.clear()
        data.seed_demo_users()

    def tearDown(self):
        data._users.clear()

    def test_response_shape(self):
        payload = data.get_fab_page_usage()
        self.assertIn("generated_at", payload)
        self.assertIn("fabs_7d", payload)
        self.assertIn("fabs_30d", payload)
        for window in ("fabs_7d", "fabs_30d"):
            self.assertTrue(payload[window], f"{window} should not be empty")
            for row in payload[window]:
                self.assertEqual(set(row), {"fab", "total", "pages"})
                self.assertGreater(row["total"], 0)
                for page in row["pages"]:
                    self.assertEqual(set(page), {"feature", "count"})

    def test_rows_sorted_by_total_desc(self):
        rows = data.get_fab_page_usage()["fabs_30d"]
        totals = [row["total"] for row in rows]
        self.assertEqual(totals, sorted(totals, reverse=True))

    def test_seeded_fabs_present(self):
        fabs = {row["fab"] for row in data.get_fab_page_usage()["fabs_30d"]}
        # Home fabs assigned in seed_demo_users.
        self.assertLessEqual({"M14", "M16B", "M11", "R3", "M15"}, fabs)

    def test_unaffiliated_traffic_buckets_under_mijijeong(self):
        data._users.clear()
        data.record_request("live-dev", "GET", "/api/sem-list", 200, "sem_list")
        fabs = {row["fab"] for row in data.get_fab_page_usage()["fabs_30d"]}
        self.assertIn("미지정", fabs)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m unittest tests.test_activity_home -v`
Expected: FAIL — `AttributeError: module 'back_dev_home.activity.data' has no attribute 'get_fab_page_usage'`.

- [ ] **Step 3: Add the `fab` field to `_UserState`**

In `back_dev_home/activity/data.py`, add the field to the dataclass (after `user_id`):

```python
@dataclass
class _UserState:
    user_id: str
    fab: str | None = None
    total: int = 0
    by_feature: dict[str, int] = field(default_factory=dict)
    daily: dict[date, int] = field(default_factory=dict)
    first_seen: datetime | None = None
    last_seen: datetime | None = None
```

- [ ] **Step 4: Add the TypedDicts**

In `data.py`, replace the `SemModelCount` / `SemModelUsageResponse` class block with:

```python
class FabPageCount(TypedDict):
    feature: str
    count: int


class FabUsageRow(TypedDict):
    fab: str
    total: int
    pages: list[FabPageCount]


class FabUsageResponse(TypedDict):
    generated_at: str
    fabs_7d: list[FabUsageRow]
    fabs_30d: list[FabUsageRow]
```

- [ ] **Step 5: Replace the SEM-model aggregation with fab aggregation**

In `data.py`, delete `_sem_model_usage_from_mock()` and `get_sem_model_usage()` and add:

```python
def _fab_rows(fab_feat: dict[str, dict[str, int]]) -> list[FabUsageRow]:
    rows: list[FabUsageRow] = []
    for fab, feats in fab_feat.items():
        total = sum(feats.values())
        if total <= 0:
            continue
        rows.append({"fab": fab, "total": total, "pages": _top_features(feats)})
    rows.sort(key=lambda r: (-r["total"], r["fab"]))
    return rows


def _fab_page_usage_from_mock(today: date) -> FabUsageResponse:
    week_start = today - timedelta(days=6)
    last30_start = today - timedelta(days=29)
    fab_feat_7d: dict[str, dict[str, int]] = {}
    fab_feat_30d: dict[str, dict[str, int]] = {}
    with _lock:
        for state in _users.values():
            sum_7d = 0
            sum_30d = 0
            for d, n in state.daily.items():
                if n <= 0:
                    continue
                if d >= week_start:
                    sum_7d += n
                if d >= last30_start:
                    sum_30d += n
            fab = state.fab or "미지정"
            _scale_features(state.by_feature, sum_7d, state.total, fab_feat_7d.setdefault(fab, {}))
            _scale_features(state.by_feature, sum_30d, state.total, fab_feat_30d.setdefault(fab, {}))
    return {
        "generated_at": _iso(_now()) or "",
        "fabs_7d": _fab_rows(fab_feat_7d),
        "fabs_30d": _fab_rows(fab_feat_30d),
    }


def get_fab_page_usage() -> FabUsageResponse:
    today = _today()
    if is_cloud():
        try:
            from ._office_reader import fab_page_usage_from_backends
            return fab_page_usage_from_backends(today)
        except Exception:
            pass
    return _fab_page_usage_from_mock(today)
```

- [ ] **Step 6: Update `__all__` and `seed_demo_users`**

In `data.py` `__all__`: remove `"SemModelCount"`, `"SemModelUsageResponse"`, `"get_sem_model_usage"`; add `"FabPageCount"`, `"FabUsageRow"`, `"FabUsageResponse"`, `"get_fab_page_usage"`.

In `seed_demo_users`, widen the demo tuples with a fab and pass it into `_UserState`:

```python
    demo: list[tuple[str, str, dict[str, int], int, int]] = [
        ("kim.minju",   "M14",  {"sem_list": 220, "recipe_search": 160, "meas_hist": 45, "fail_issue": 30},         14, 35),
        ("park.jinho",  "M16B", {"recipe_search": 190, "sem_list": 120, "recipe_tat": 65, "storage": 25},           12, 28),
        ("lee.soyoung", "M11",  {"sem_list": 140, "storage": 80, "fail_issue": 55, "hardware": 20},                  9, 22),
        ("choi.eunwoo", "R3",   {"recipe_tat": 70, "sem_list": 60, "recipe_search": 40, "device_statistics": 25},    6, 18),
        ("jung.hari",   "M15",  {"skewvoir": 90, "sem_list": 30, "afm": 25, "meas_hist": 15},                        4, 14),
    ]
    now = _now()
    with _lock:
        for user_id, fab, features, days_back, peak in demo:
            if user_id in _users:
                continue
            state = _UserState(user_id=user_id, fab=fab)
```

(Leave the rest of the loop body — `state.total`, `by_feature`, `daily`, `first_seen`, `last_seen` — unchanged.)

- [ ] **Step 7: Update the route**

In `back_dev_home/activity/routes.py`, change the import `get_sem_model_usage` → `get_fab_page_usage`, and replace the sem-models route:

```python
@bp.get("/activity/fabs")
def activity_fabs():
    return jsonify(get_fab_page_usage())
```

- [ ] **Step 8: Run the test to verify it passes**

Run: `.venv/bin/python -m unittest tests.test_activity_home -v`
Expected: PASS (4 tests).

- [ ] **Step 9: Run the full backend suite for regressions**

Run: `.venv/bin/python -m unittest discover tests`
Expected: OK (no failures; the deleted `get_sem_model_usage` has no other importers — verify with `grep -rn "get_sem_model_usage\|sem_model_usage\|SemModelUsage" back_dev_home tests` returning nothing).

- [ ] **Step 10: Commit**

```bash
git add back_dev_home/activity/data.py back_dev_home/activity/routes.py tests/test_activity_home.py
git commit -m "feat(activity): add fab page-usage aggregation, drop sem-model breakdown"
```

---

### Task 2: Frontend — swap `useActivitySemModels` for `useActivityFabs`

**Files:**
- Modify: `front-dev-home/app/composables/useActivityApi.ts`

**Interfaces:**
- Consumes: `get_fab_page_usage` response shape from Task 1 (`/activity/fabs`).
- Produces:
  - `interface FabUsageRow { fab: string; total: number; pages: FeatureCount[] }`
  - `interface FabUsageResponse { generated_at: string; fabs_7d: FabUsageRow[]; fabs_30d: FabUsageRow[] }`
  - `useActivityFabs()` returning a `useAsyncData` handle (key `activity-fabs`).

- [ ] **Step 1: Replace the SEM-model types**

In `useActivityApi.ts`, delete `SemModelCount` and `SemModelUsageResponse` and add (reusing the existing `FeatureCount`):

```ts
export interface FabUsageRow {
  fab: string
  total: number
  pages: FeatureCount[]
}

export interface FabUsageResponse {
  generated_at: string
  fabs_7d: FabUsageRow[]
  fabs_30d: FabUsageRow[]
}
```

- [ ] **Step 2: Replace the key, in-flight ref, and URL**

- Change `const SEM_MODELS_KEY = 'activity-sem-models'` → `const FABS_KEY = 'activity-fabs'`.
- Change `let inFlightSemModels: Promise<SemModelUsageResponse> | null = null` → `let inFlightFabs: Promise<FabUsageResponse> | null = null`.
- In `useActivityUrls`, change `semModelsUrl: joinApiPath(base, '/activity/sem-models')` → `fabsUrl: joinApiPath(base, '/activity/fabs')`.

- [ ] **Step 3: Replace the composable**

Delete `useActivitySemModels` and add:

```ts
export const useActivityFabs = () => {
  const { fabsUrl } = useActivityUrls()
  const fetchOnce = () => {
    if (!inFlightFabs) {
      inFlightFabs = $fetch<FabUsageResponse>(fabsUrl).catch((err) => {
        inFlightFabs = null
        throw err
      })
    }
    return inFlightFabs
  }
  return useAsyncData(FABS_KEY, fetchOnce, {
    getCachedData: (key, nuxtApp) => nuxtApp.payload.data[key] ?? nuxtApp.static.data[key]
  })
}
```

- [ ] **Step 4: Update `resetActivityCache`**

Change the line `inFlightSemModels = null` → `inFlightFabs = null`.

- [ ] **Step 5: Typecheck**

Run (from `front-dev-home/`): `npm run typecheck`
Expected: no errors referencing `useActivityApi.ts`. (The activity page still references the old names until Task 3 — expect only `activity.vue` errors here; those are resolved in Task 3. If you prefer a clean gate, run typecheck after Task 3 instead.)

- [ ] **Step 6: Commit**

```bash
git add front-dev-home/app/composables/useActivityApi.ts
git commit -m "feat(activity): add useActivityFabs composable, drop sem-model composable"
```

---

### Task 3: Frontend — Fab card in `activity.vue`, delete `ModelBarList.vue`

**Files:**
- Modify: `front-dev-home/app/pages/activity.vue`
- Delete: `front-dev-home/app/components/activity/ModelBarList.vue`

**Interfaces:**
- Consumes: `useActivityFabs`, `FabUsageRow`, `FeatureCount` from Task 2; existing `ActivityFeatureBarList` (auto-imported as `ActivityFeatureBarList`, source `app/components/activity/FeatureBarList.vue`), `windowTabs`.

- [ ] **Step 1: Update the script imports**

In the `<script setup>` import from `~/composables/useActivityApi`: remove `useActivitySemModels` and `type SemModelCount`; add `useActivityFabs` and `type FabUsageRow`. Keep `type FeatureCount`.

- [ ] **Step 2: Swap the shared query wiring**

- In the `Promise.all` for `sharedQueries`, replace `useActivitySemModels()` with `useActivityFabs()` and rename the destructured/assembled key `semModels` → `fabs`:

```ts
const sharedQueries = await Promise.all([
  useActivitySummary(),
  useActivityUsers(),
  useActivityFabs()
]).then(
  ([summary, users, fabs]) => ({ summary, users, fabs })
)

const summary = computed(() => sharedQueries.summary.data.value ?? null)
const users = computed(() => sharedQueries.users.data.value ?? null)
const fabs = computed(() => sharedQueries.fabs.data.value ?? null)
```

- In `loadError`: replace `sharedQueries.semModels.error.value` → `sharedQueries.fabs.error.value`.
- In `refreshing`: replace the `sharedQueries.semModels.status.value` check → `sharedQueries.fabs.status.value`.
- In `refreshAll`: replace `sharedQueries.semModels.refresh()` → `sharedQueries.fabs.refresh()`.

- [ ] **Step 3: Replace the SEM-model computed block with fab state**

Delete the `modelWindowKey` ref and the `modelGroups` computed (the `--- shared usage: SEM List per-model breakdown ---` block) and add:

```ts
// --- shared usage: Fab page breakdown ---
const fabWindowKey = ref<'7d' | '30d'>('7d')
const fabsForWindow = computed<FabUsageRow[]>(() =>
  fabWindowKey.value === '7d'
    ? fabs.value?.fabs_7d ?? []
    : fabs.value?.fabs_30d ?? []
)
const selectedFab = ref<string | null>(null)
watchEffect(() => {
  const rows = fabsForWindow.value
  if (!rows.length) {
    selectedFab.value = null
    return
  }
  if (!selectedFab.value || !rows.some(row => row.fab === selectedFab.value)) {
    selectedFab.value = rows[0]?.fab ?? null
  }
})
const selectedFabPages = computed<FeatureCount[]>(() => {
  const row = fabsForWindow.value.find(item => item.fab === selectedFab.value)
  return row?.pages ?? []
})
```

- [ ] **Step 4: Replace the SEM-model card template**

Replace the entire `<!-- SEM List usage per equipment model -->` `<UCard>` (currently lines ~225–261) with:

```vue
      <!-- Fab별 페이지 사용 -->
      <UCard class="dashboard-surface">
        <template #header>
          <div class="flex items-center justify-between">
            <span class="text-sm font-medium text-(--sk-ink-muted) flex items-center gap-1.5">
              <UIcon name="i-lucide-factory" />
              Fab별 페이지 사용
            </span>
            <UTabs
              v-model="fabWindowKey"
              :items="windowTabs"
              variant="pill"
              size="xs"
            />
          </div>
        </template>
        <div
          v-if="fabsForWindow.length"
          class="grid grid-cols-1 md:grid-cols-[minmax(0,11rem)_1fr] gap-4"
        >
          <nav
            aria-label="Fab 선택"
            class="flex flex-row md:flex-col gap-1 overflow-x-auto md:overflow-visible border-b md:border-b-0 md:border-r border-(--sk-border) pb-2 md:pb-0 md:pr-3"
          >
            <button
              v-for="row in fabsForWindow"
              :key="row.fab"
              type="button"
              :aria-pressed="selectedFab === row.fab"
              class="flex items-center justify-between gap-2 rounded-lg px-3 py-1.5 text-sm shrink-0 w-full text-left transition-colors"
              :class="selectedFab === row.fab
                ? 'bg-zinc-900 text-zinc-100 dark:bg-zinc-100 dark:text-zinc-900 font-semibold shadow-sm'
                : 'text-zinc-700 dark:text-zinc-300 hover:bg-zinc-100 dark:hover:bg-zinc-800'"
              @click="selectedFab = row.fab"
            >
              <span class="font-semibold tracking-wide truncate">{{ row.fab }}</span>
              <span class="tabular-nums text-xs shrink-0 opacity-80">{{ row.total.toLocaleString() }}</span>
            </button>
          </nav>
          <ActivityFeatureBarList
            :items="selectedFabPages"
            empty-text="아직 데이터가 없습니다."
          />
        </div>
        <div
          v-else
          class="sk-body"
        >
          아직 데이터가 없습니다.
        </div>
      </UCard>
```

- [ ] **Step 5: Delete the now-dead component**

Run: `git rm front-dev-home/app/components/activity/ModelBarList.vue`
Confirm no other references: `grep -rn "ActivityModelBarList\|activity/ModelBarList" front-dev-home/app` → nothing.

- [ ] **Step 6: Typecheck and lint**

Run (from `front-dev-home/`):
`npm run typecheck` → Expected: no errors.
`npm run lint` → Expected: no errors in `activity.vue` / `useActivityApi.ts`.

- [ ] **Step 7: Verify in the running app**

Use the `verify` skill (Flask mock + Nuxt). Confirm: the 사용 통계 page shows a "Fab별 페이지 사용" card; the left fab list is populated and sorted by total; clicking a fab swaps the right-side page bars; the 7일/30일 toggle changes the data; no "SEM List 모델별 사용" card remains.

- [ ] **Step 8: Commit**

```bash
git add front-dev-home/app/pages/activity.vue
git rm front-dev-home/app/components/activity/ModelBarList.vue
git commit -m "feat(activity): replace SEM-model card with Fab page-usage card"
```

---

## Self-Review

**Spec coverage:**
- Fab field on `_UserState` + demo assignment → Task 1 Steps 3, 6. ✓
- `get_fab_page_usage` + `_scale_features` approximation + "미지정" bucket → Task 1 Step 5 (+ test Step 1). ✓
- `GET /activity/fabs`, delete sem-model endpoint/types/`__all__` → Task 1 Steps 4–7. ✓
- No `_office_reader.py` created; cloud branch falls back → Task 1 Step 5 + Global Constraints. ✓
- `useActivityFabs` replaces `useActivitySemModels` → Task 2. ✓
- Fab card: selectable list (activity-only, busiest first), page bars, 7d/30d toggle, empty state → Task 3 Steps 3–4. ✓
- Delete `ModelBarList.vue` → Task 3 Step 5. ✓
- Backend test → Task 1. ✓  Frontend verify → Task 3 Step 7. ✓

**Placeholder scan:** No TBD/TODO/"handle edge cases"; every code step shows full code. ✓

**Type consistency:** `FabUsageRow`/`FabUsageResponse` names identical across Tasks 1–3; frontend `pages: FeatureCount[]` is structurally identical to backend `list[FabPageCount]` ({feature, count}); `fabWindowKey`, `fabsForWindow`, `selectedFab`, `selectedFabPages` used consistently in Task 3 Steps 3–4. ✓
