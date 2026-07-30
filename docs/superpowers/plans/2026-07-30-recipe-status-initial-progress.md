# Recipe 현황 초기 로딩 진행 표시 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Recipe 현황의 최초 백엔드 대기 중에도 상단 헤더와 탭을 유지하면서 Nuxt UI 기반 진행 패널을 표시합니다.

**Architecture:** 공용 `AppLoadingState` 표현 컴포넌트가 indeterminate `UProgress`와 접근 가능한 상태 문구를 렌더링합니다. `RecipeStatusView`는 기존 `KeepAlive` 자식 영역을 `Suspense`로 감싸고, 비동기 setup이 완료될 때까지 이 공용 컴포넌트를 fallback으로 사용합니다.

**Tech Stack:** Nuxt 4, Vue 3 `Suspense`/`KeepAlive`, TypeScript, Nuxt UI 4 `UProgress`, Tailwind CSS

## Global Constraints

- 실제 적용 범위는 Recipe 현황으로 제한합니다.
- 진행 패널은 Recipe 현황 `EbeamMetaBar`와 탭 바로 아래의 대시보드 영역에 표시합니다.
- 백엔드가 진행률을 제공하지 않으므로 퍼센트나 예상 남은 시간을 표시하지 않습니다.
- 기존 API, cache key, `useAsyncData` 병렬 요청과 응답 형태를 변경하지 않습니다.
- 기존 `KeepAlive` 상태 보존과 자식 화면의 후속 refetch pending 처리를 유지합니다.
- 전역 `NuxtLoadingIndicator`, timeout, retry, 오류 토스트를 추가하지 않습니다.
- Vue mounting test harness가 없으므로 새 컴포넌트 단위 테스트를 만들지 않습니다.

---

### Task 1: 공용 초기 로딩 상태 컴포넌트

**Files:**
- Create: `front-dev-home/app/components/AppLoadingState.vue`

**Interfaces:**
- Consumes: Nuxt UI auto-imported `UProgress`; global `dashboard-surface`, `sk-body`, `sk-meta` CSS classes
- Produces: `AppLoadingState` auto-imported Vue component with props `{ title: string, description?: string }`

- [ ] **Step 1: Create the reusable presentation component**

Create `front-dev-home/app/components/AppLoadingState.vue` with this complete implementation:

```vue
<template>
  <div
    class="dashboard-surface rounded-2xl px-6 py-12"
    role="status"
    aria-live="polite"
  >
    <div class="mx-auto max-w-md">
      <UProgress
        animation="carousel"
        size="sm"
      />
      <p class="mt-4 text-center sk-body">
        {{ title }}
      </p>
      <p
        v-if="description"
        class="mt-1 text-center sk-meta"
      >
        {{ description }}
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  title: string
  description?: string
}>()
</script>
```

- [ ] **Step 2: Verify the component compiles and follows frontend style**

Run:

```bash
cd front-dev-home
npm run lint -- app/components/AppLoadingState.vue
npm run typecheck
```

Expected: both commands exit 0. `UProgress` and `defineProps` resolve through Nuxt auto-imports without explicit imports.

- [ ] **Step 3: Commit the reusable component**

```bash
git add front-dev-home/app/components/AppLoadingState.vue
git diff --cached --check
git commit -m "feat(ui): add reusable loading progress state"
```

Expected: the commit contains only `AppLoadingState.vue`.

### Task 2: Recipe 현황 Suspense fallback 적용

**Files:**
- Modify: `front-dev-home/app/components/ebeam/RecipeStatusView.vue:31-51`

**Interfaces:**
- Consumes: `AppLoadingState` from Task 1 with `title: string`
- Produces: Recipe 현황 child-view boundary that preserves its header and tabs while showing an initial loading fallback

- [ ] **Step 1: Wrap the existing kept-alive child region with Suspense**

Replace the current standalone `KeepAlive` block in
`RecipeStatusView.vue` with:

```vue
    <Suspense>
      <KeepAlive>
        <EbeamRecipeTatView
          v-if="activeTab === 'tat'"
          v-model:include-today="includeToday"
          :fab="fab"
          :tool-label="toolLabel"
          :tool-type="toolType"
        />
        <EbeamFailIssueView
          v-else
          v-model:include-today="includeToday"
          :fab="fab"
          :tool-label="toolLabel"
          :tool-type="toolType"
          :section="activeTab"
        />
      </KeepAlive>

      <template #fallback>
        <AppLoadingState title="Recipe 현황 데이터를 불러오는 중입니다." />
      </template>
    </Suspense>
```

Keep the existing explanatory comment immediately above the boundary. Do not
change props, tab routing, `includeToday`, API composables, or either child
component.

- [ ] **Step 2: Run targeted static verification**

Run:

```bash
cd front-dev-home
npm run lint -- app/components/AppLoadingState.vue app/components/ebeam/RecipeStatusView.vue
npm run typecheck
```

Expected: both commands exit 0 with no new warnings or errors.

- [ ] **Step 3: Run the frontend regression suite**

Run:

```bash
cd front-dev-home
npm test
```

Expected: all Node tests pass with zero failures.

- [ ] **Step 4: Inspect the initial loading behavior in the running app**

Start the home backend and frontend if they are not already running:

```bash
.venv/bin/python index.py
cd front-dev-home
npm run dev
```

Open a Recipe 현황 route and delay its TAT/fail API responses using the
available interactive browser tooling. Confirm:

- Recipe 현황 header and TAT/Align/Meas tabs remain visible.
- The `UProgress` loading panel appears directly below the tabs.
- The loading text is `Recipe 현황 데이터를 불러오는 중입니다.`.
- The dashboard replaces the fallback after the response completes.
- The same fallback appears on the first visit to an unloaded sibling tab.
- Returning to an already loaded tab preserves its prior state without a new
  initial fallback.
- The panel remains readable in both light and dark themes.

If interactive browser tooling is unavailable, report the visual verification
gap explicitly and do not claim browser verification.

- [ ] **Step 5: Run final diff and whitespace checks**

Run:

```bash
git diff --check
git diff -- front-dev-home/app/components/AppLoadingState.vue front-dev-home/app/components/ebeam/RecipeStatusView.vue
git status --short
```

Expected: no whitespace errors; only the intended implementation file remains
uncommitted after Task 1, apart from unrelated pre-existing worktree changes.

- [ ] **Step 6: Commit the Recipe 현황 integration**

```bash
git add front-dev-home/app/components/ebeam/RecipeStatusView.vue
git diff --cached --check
git commit -m "feat(recipe-status): show initial loading progress" -m "Keep the Recipe status header and tabs visible while async child views wait for backend data. Render the shared indeterminate Nuxt UI progress state in the dashboard area without changing API or refetch behavior."
```

Expected: the commit contains only `RecipeStatusView.vue`.

### Task 3: Final branch verification

**Files:**
- Verify only; no additional file changes

**Interfaces:**
- Consumes: Task 1 and Task 2 commits
- Produces: fresh evidence that the complete implementation is ready to integrate

- [ ] **Step 1: Run all required frontend checks**

Run from `front-dev-home/`:

```bash
npm run lint
npm run typecheck
npm test
```

Expected: every command exits 0. If a pre-existing failure appears, record the
exact command and output and keep it separate from change-specific results.

- [ ] **Step 2: Verify branch scope**

Run:

```bash
git status --short
git log --oneline --decorate -3
git diff main...HEAD --check
git diff main...HEAD --stat
git diff main...HEAD -- front-dev-home/app/components/AppLoadingState.vue front-dev-home/app/components/ebeam/RecipeStatusView.vue
```

Expected: the implementation branch contains exactly the reusable loading
component and the Recipe 현황 integration, plus this already-approved plan if
the plan commit is part of the branch base.
