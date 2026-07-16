# SKEWNONO History Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an easily editable SKEWNONO v1-v3 history view under the intro page's `시작하기` navigation, with concise v1/v2 entries and detailed v3 feature cards.

**Architecture:** Store all version copy in one typed `skewnonoHistory.ts` array and render it through a focused `IntroHistoryView.vue` component. The existing `intro.vue` remains the view orchestrator: it adds the History navigation button and selects the new component through `activePageId` without introducing a new route or backend dependency.

**Tech Stack:** Nuxt 4, Vue 3 Composition API, TypeScript, Tailwind CSS, Nuxt UI `UIcon`, Node test runner

## Global Constraints

- Keep the existing introduction and page-guide content unchanged.
- Add no route, API, backend, database, or new package dependency.
- Keep v1 and v2 concise; give v3 four detailed feature areas.
- Display v3 as released in `2026.07` and identify it textually as the current version.
- Keep all version copy editable in `front-dev-home/app/data/skewnonoHistory.ts`.
- Use the existing zinc borders, white/dark surfaces, Lucide icons, and semantic typography classes.
- Render the history as semantic `ol` and `li` elements, and do not rely on color alone to identify v3.
- Follow repository formatting: 2-space indentation, no trailing commas, and `1tbs` braces.

---

## File Structure

- Create `front-dev-home/app/data/skewnonoHistory.ts`: typed, editable source of truth for v1-v3 copy and feature metadata.
- Create `front-dev-home/app/data/skewnonoHistory.test.ts`: contract tests for version order, release labels, current-version uniqueness, and required feature content.
- Create `front-dev-home/app/components/intro/HistoryView.vue`: semantic, responsive timeline renderer with compact legacy entries and detailed current-version cards.
- Modify `front-dev-home/app/pages/intro.vue`: add the `History` navigation choice and render `IntroHistoryView` before the existing page-guide fallback.

### Task 1: Define the editable history data contract

**Files:**

- Create: `front-dev-home/app/data/skewnonoHistory.test.ts`
- Create: `front-dev-home/app/data/skewnonoHistory.ts`

**Interfaces:**

- Produces: `SkewnonoHistoryFeature` with `title: string`, `description?: string`, and `icon: string`.
- Produces: `SkewnonoHistoryVersion` with `version: string`, `releasedAt: string`, `summary: string`, `features: SkewnonoHistoryFeature[]`, and optional `current?: boolean`.
- Produces: `skewnonoHistory: SkewnonoHistoryVersion[]`, ordered oldest to newest.

- [ ] **Step 1: Write the failing history-data contract test**

Create `front-dev-home/app/data/skewnonoHistory.test.ts`:

```ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { skewnonoHistory } from './skewnonoHistory.ts'

test('lists SKEWNONO releases from v1 through the current v3', () => {
  assert.deepEqual(
    skewnonoHistory.map(({ version, releasedAt }) => ({ version, releasedAt })),
    [
      { version: 'v1', releasedAt: '2024' },
      { version: 'v2', releasedAt: '2025' },
      { version: 'v3', releasedAt: '2026.07' }
    ]
  )
  assert.deepEqual(
    skewnonoHistory.filter(version => version.current).map(version => version.version),
    ['v3']
  )
})

test('keeps legacy releases concise and gives v3 four detailed feature areas', () => {
  const [v1, v2, v3] = skewnonoHistory

  assert.deepEqual(v1?.features.map(feature => feature.title), [
    '장비 상태',
    '측정 이력',
    'FDC Sharpness'
  ])
  assert.equal(v2?.features.length, 3)
  assert.deepEqual(v3?.features.map(feature => feature.title), [
    'CD-SEM · HV-SEM 통합 관리',
    'Hardware · Calibration 분석',
    'Device Statistics 강화',
    'Skewvoir 분석'
  ])
  assert.ok(v3?.features.every(feature => feature.description))
})
```

- [ ] **Step 2: Run the test and verify it fails because the data module is missing**

Run from `front-dev-home/`:

```bash
node --test app/data/skewnonoHistory.test.ts
```

Expected: FAIL with `ERR_MODULE_NOT_FOUND` for `app/data/skewnonoHistory.ts`.

- [ ] **Step 3: Add the typed history source of truth**

Create `front-dev-home/app/data/skewnonoHistory.ts`:

```ts
export type SkewnonoHistoryFeature = {
  title: string
  description?: string
  icon: string
}

export type SkewnonoHistoryVersion = {
  version: string
  releasedAt: string
  summary: string
  features: SkewnonoHistoryFeature[]
  current?: boolean
}

export const skewnonoHistory = [
  {
    version: 'v1',
    releasedAt: '2024',
    summary: 'SKEWNONO의 첫 버전으로 장비와 측정 상태를 한곳에서 확인하기 시작했습니다.',
    features: [
      { title: '장비 상태', icon: 'i-lucide-monitor-check' },
      { title: '측정 이력', icon: 'i-lucide-history' },
      { title: 'FDC Sharpness', icon: 'i-lucide-activity' }
    ]
  },
  {
    version: 'v2',
    releasedAt: '2025',
    summary: '약 270대의 CD-SEM을 대상으로 장비와 Recipe 운영 정보를 더 폭넓게 연결했습니다.',
    features: [
      { title: 'CD-SEM 약 270대', icon: 'i-lucide-microscope' },
      { title: '장비 운영 정보', icon: 'i-lucide-gauge' },
      { title: 'Recipe · 측정 이력', icon: 'i-lucide-file-clock' }
    ]
  },
  {
    version: 'v3',
    releasedAt: '2026.07',
    current: true,
    summary: 'E-Beam 장비 운영과 측정 데이터를 통합하고 분석 기능을 강화한 현재 버전입니다.',
    features: [
      {
        title: 'CD-SEM · HV-SEM 통합 관리',
        description: 'CD-SEM 약 270대와 HV-SEM 약 50대, 총 약 320대의 장비 상태와 운영 정보를 한곳에서 확인합니다.',
        icon: 'i-lucide-microscope'
      },
      {
        title: 'Hardware · Calibration 분석',
        description: 'Hardware 상태, FDC, Beam Calibration, BM/PM 정보를 측정 결과와 연결해 장비 간 차이와 변화 원인을 확인합니다.',
        icon: 'i-lucide-cpu'
      },
      {
        title: 'Device Statistics 강화',
        description: 'Device와 CD Step별 Recipe·Parameter 현황, 계측 룰 위반, 기간별 변화 추이를 분석합니다.',
        icon: 'i-lucide-table-properties'
      },
      {
        title: 'Skewvoir 분석',
        description: '측정 결과, Wafer 분포, 시간 변화, 상관관계, 측정 이미지를 연결해 이상 징후와 원인을 분석합니다.',
        icon: 'i-lucide-scan-search'
      }
    ]
  }
] satisfies SkewnonoHistoryVersion[]
```

- [ ] **Step 4: Run the focused data test and the full frontend test suite**

Run from `front-dev-home/`:

```bash
node --test app/data/skewnonoHistory.test.ts
npm test
```

Expected: the two new history tests pass, then the complete Node test suite passes.

- [ ] **Step 5: Commit the data contract**

```bash
git add front-dev-home/app/data/skewnonoHistory.ts front-dev-home/app/data/skewnonoHistory.test.ts
git commit -m "feat(intro): add editable SKEWNONO history data"
```

### Task 2: Render the responsive history timeline

**Files:**

- Create: `front-dev-home/app/components/intro/HistoryView.vue`

**Interfaces:**

- Consumes: `skewnonoHistory` from `~/data/skewnonoHistory`.
- Produces: auto-imported Nuxt component `<IntroHistoryView />` with no props or emitted events.

- [ ] **Step 1: Create the focused history presentation component**

Create `front-dev-home/app/components/intro/HistoryView.vue`:

```vue
<template>
  <section class="space-y-6" aria-labelledby="history-title">
    <header class="border-b border-(--sk-border) pb-6">
      <div class="flex items-center gap-2 text-sm font-semibold text-(--sk-ink-muted)">
        <UIcon name="i-lucide-history" class="h-4 w-4" />
        <span>History</span>
      </div>
      <div class="mt-3 max-w-3xl">
        <h1 id="history-title" class="sk-page-title md:text-4xl">
          SKEWNONO History
        </h1>
        <p class="mt-3 sk-body leading-7 md:text-base">
          2024년 첫 버전부터 현재 v3까지, SKEWNONO가 장비 조회 도구에서
          통합 Metrology Workspace로 발전해 온 과정입니다.
        </p>
      </div>
    </header>

    <ol class="space-y-5">
      <li
        v-for="release in skewnonoHistory"
        :key="release.version"
        class="grid gap-3 md:grid-cols-[7rem_minmax(0,1fr)] md:gap-5"
      >
        <div class="pt-1">
          <div class="sk-eyebrow">{{ release.releasedAt }}</div>
          <div class="mt-1 text-xl font-semibold text-zinc-950 dark:text-white">
            {{ release.version }}
          </div>
        </div>

        <article
          class="rounded-lg border bg-white p-5 dark:bg-zinc-950"
          :class="release.current ? 'border-zinc-900 dark:border-zinc-100' : 'border-(--sk-border)'"
        >
          <div class="flex flex-wrap items-start justify-between gap-3">
            <h2 class="sk-heading">{{ release.version }} 주요 변화</h2>
            <span
              v-if="release.current"
              class="rounded-full bg-zinc-900 px-2.5 py-1 text-xs font-semibold text-white dark:bg-zinc-100 dark:text-zinc-950"
            >
              현재 버전
            </span>
          </div>
          <p class="mt-3 sk-body leading-7">{{ release.summary }}</p>

          <div
            v-if="release.current"
            class="mt-5 grid gap-3 sm:grid-cols-2"
          >
            <section
              v-for="feature in release.features"
              :key="feature.title"
              class="rounded-md bg-zinc-50 p-4 dark:bg-zinc-900"
            >
              <UIcon :name="feature.icon" class="h-5 w-5 text-zinc-700 dark:text-zinc-200" />
              <h3 class="mt-3 sk-title">{{ feature.title }}</h3>
              <p v-if="feature.description" class="mt-2 sk-meta leading-5">
                {{ feature.description }}
              </p>
            </section>
          </div>

          <ul v-else class="mt-4 flex flex-wrap gap-2" aria-label="주요 기능">
            <li
              v-for="feature in release.features"
              :key="feature.title"
              class="flex items-center gap-1.5 rounded-md border border-(--sk-border) px-3 py-2 sk-meta"
            >
              <UIcon :name="feature.icon" class="h-4 w-4" />
              <span>{{ feature.title }}</span>
            </li>
          </ul>
        </article>
      </li>
    </ol>
  </section>
</template>

<script setup lang="ts">
import { skewnonoHistory } from '~/data/skewnonoHistory'
</script>
```

- [ ] **Step 2: Run component-level static checks**

Run from `front-dev-home/`:

```bash
npx eslint app/components/intro/HistoryView.vue app/data/skewnonoHistory.ts
npx nuxi typecheck
```

Expected: both commands exit with code 0; the Vue template and imported data types are valid.

- [ ] **Step 3: Commit the history component**

```bash
git add front-dev-home/app/components/intro/HistoryView.vue
git commit -m "feat(intro): render SKEWNONO history timeline"
```

### Task 3: Add History to the intro-page navigation

**Files:**

- Modify: `front-dev-home/app/pages/intro.vue:8-26`
- Modify: `front-dev-home/app/pages/intro.vue:307-314`

**Interfaces:**

- Consumes: Nuxt auto-imported `<IntroHistoryView />` from Task 2.
- Preserves: existing `activePageId`, `selectedPageGuide`, and page-guide fallback behavior.
- Produces: a `History` button that sets `activePageId = 'history'`.

- [ ] **Step 1: Add the History navigation button beside the introduction button**

Replace the single `SKEWNONO 소개` button container in `front-dev-home/app/pages/intro.vue` with:

```vue
<div class="space-y-1">
  <button
    type="button"
    class="flex w-full items-center gap-2 rounded-md px-3 py-2 text-left text-sm transition"
    :class="activePageId === 'overview' ? 'bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-950' : 'text-zinc-600 hover:bg-zinc-100 dark:text-zinc-300 dark:hover:bg-zinc-900'"
    @click="activePageId = 'overview'"
  >
    <UIcon name="i-lucide-sparkles" class="h-4 w-4 shrink-0" />
    <span>SKEWNONO 소개</span>
  </button>
  <button
    type="button"
    class="flex w-full items-center gap-2 rounded-md px-3 py-2 text-left text-sm transition"
    :class="activePageId === 'history' ? 'bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-950' : 'text-zinc-600 hover:bg-zinc-100 dark:text-zinc-300 dark:hover:bg-zinc-900'"
    @click="activePageId = 'history'"
  >
    <UIcon name="i-lucide-history" class="h-4 w-4 shrink-0" />
    <span>History</span>
  </button>
</div>
```

- [ ] **Step 2: Insert the History view before the existing page-guide fallback**

Immediately after the closing tag for the `activePageId === 'overview'` section and before the existing `v-else` page-guide section, add:

```vue
<IntroHistoryView v-else-if="activePageId === 'history'" />
```

Keep the existing page-guide section as the final `v-else`, so normal guide IDs continue to resolve through `selectedPageGuide`.

- [ ] **Step 3: Run all frontend quality gates**

Run from `front-dev-home/`:

```bash
npm test
npm run lint
npm run typecheck
npm run build
```

Expected: every command exits with code 0. The build output completes without a missing component, icon, or data-module error.

- [ ] **Step 4: Inspect the intro page manually**

Run from `front-dev-home/`:

```bash
npm run dev -- --host 0.0.0.0
```

Open `/intro` and verify:

1. `시작하기` contains `SKEWNONO 소개` and `History`.
2. The selected style moves correctly between both buttons.
3. v1, v2, and v3 appear in chronological order.
4. v1 and v2 use compact feature tags.
5. v3 shows `현재 버전` and four detailed cards.
6. The timeline remains readable at desktop and mobile widths.
7. Selecting any page-guide item after History still opens its original guide content.

Stop the development server after verification.

- [ ] **Step 5: Check diff hygiene and commit the integration**

Run from the repository root:

```bash
git diff --check -- front-dev-home/app/pages/intro.vue front-dev-home/app/components/intro/HistoryView.vue front-dev-home/app/data/skewnonoHistory.ts front-dev-home/app/data/skewnonoHistory.test.ts
git status --short
```

Expected: diff check exits with code 0. Status shows only the intended History implementation plus unrelated pre-existing worktree changes, which remain unstaged.

Commit only the intro-page integration:

```bash
git add front-dev-home/app/pages/intro.vue
git commit -m "feat(intro): add History navigation"
```
