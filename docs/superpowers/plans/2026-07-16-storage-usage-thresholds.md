# Storage Usage Thresholds Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the storage page classify usage below 90% as healthy, 90% through 97% as warning, and 98% or above as critical.

**Architecture:** Put the threshold policy in one pure TypeScript utility and make `StorageView.vue` consume that classifier for presentation, filtering, and summary counts. Keep unavailable-storage handling and unrelated local component edits unchanged.

**Tech Stack:** Nuxt 4, Vue 3, TypeScript, Node test runner, ESLint, Nuxt type checking

## Global Constraints

- Healthy means usage below 90%.
- Warning means usage from 90% through 97%.
- Critical means usage of 98% or above.
- Preserve the existing `unavailable` classification and `정보 없음` filter.
- Do not change backend response shapes, mock data, layout, styling tokens, recipe-count thresholds, or storage-unavailable handling.
- Preserve pre-existing IP-copy edits in `front-dev-home/app/components/ebeam/StorageView.vue`.
- The working tree is mixed; stage only threshold-related hunks when committing `StorageView.vue`.

---

## File Map

- Create `front-dev-home/app/utils/storageUsage.ts`: owns threshold constants and percentage-to-tier classification.
- Create `front-dev-home/app/utils/storageUsage.test.ts`: proves the four required boundary cases.
- Modify `front-dev-home/app/components/ebeam/StorageView.vue`: consumes the classifier for colors, filter labels/results, and summary counts.

### Task 1: Add the tested storage usage classifier

**Files:**

- Create: `front-dev-home/app/utils/storageUsage.test.ts`
- Create: `front-dev-home/app/utils/storageUsage.ts`

**Interfaces:**

- Consumes: a numeric storage usage percentage.
- Produces: `storageUsageTier(percent: number): StorageUsageTier`, where `StorageUsageTier` is `'healthy' | 'warning' | 'critical'`.
- Produces: `STORAGE_WARNING_THRESHOLD = 90` and `STORAGE_CRITICAL_THRESHOLD = 98`.

- [ ] **Step 1: Write the failing boundary test**

Create `front-dev-home/app/utils/storageUsage.test.ts`:

```ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { storageUsageTier } from './storageUsage.ts'

test('storageUsageTier applies the healthy, warning, and critical boundaries', () => {
  assert.equal(storageUsageTier(89), 'healthy')
  assert.equal(storageUsageTier(90), 'warning')
  assert.equal(storageUsageTier(97), 'warning')
  assert.equal(storageUsageTier(98), 'critical')
})
```

- [ ] **Step 2: Run the focused test and verify RED**

Run from `front-dev-home/`:

```bash
node --test app/utils/storageUsage.test.ts
```

Expected: FAIL because `./storageUsage.ts` does not exist.

- [ ] **Step 3: Add the minimal classifier**

Create `front-dev-home/app/utils/storageUsage.ts`:

```ts
export const STORAGE_WARNING_THRESHOLD = 90
export const STORAGE_CRITICAL_THRESHOLD = 98

export type StorageUsageTier = 'healthy' | 'warning' | 'critical'

export const storageUsageTier = (percent: number): StorageUsageTier => {
  if (percent >= STORAGE_CRITICAL_THRESHOLD) return 'critical'
  if (percent >= STORAGE_WARNING_THRESHOLD) return 'warning'
  return 'healthy'
}
```

- [ ] **Step 4: Run the focused test and verify GREEN**

Run from `front-dev-home/`:

```bash
node --test app/utils/storageUsage.test.ts
```

Expected: PASS with one passing test and no failures.

- [ ] **Step 5: Commit the isolated classifier**

```bash
git add front-dev-home/app/utils/storageUsage.ts front-dev-home/app/utils/storageUsage.test.ts
git diff --cached --check
git commit -m "test: define storage usage boundaries"
```

### Task 2: Apply the classifier throughout the storage page

**Files:**

- Modify: `front-dev-home/app/components/ebeam/StorageView.vue:220-540`
- Test: `front-dev-home/app/utils/storageUsage.test.ts`

**Interfaces:**

- Consumes: `storageUsageTier(percent: number): 'healthy' | 'warning' | 'critical'` from Task 1.
- Produces: consistent colors, filters, labels, and summary counts in the storage view.

- [ ] **Step 1: Import the classifier**

Add this import without changing the existing imports for storage API or IP copy:

```ts
import { storageUsageTier } from '~/utils/storageUsage'
```

- [ ] **Step 2: Drive usage colors from the classifier**

Replace the old numeric comparisons in both color helpers:

```ts
const usageBarClass = (percent: number) => {
  switch (storageUsageTier(percent)) {
    case 'critical':
      return 'bg-(--sk-bad)'
    case 'warning':
      return 'bg-(--sk-warn)'
    default:
      return 'bg-(--sk-ok)'
  }
}

const usageTextClass = (percent: number) => {
  switch (storageUsageTier(percent)) {
    case 'critical':
      return 'text-(--sk-bad)'
    case 'warning':
      return 'text-(--sk-warn)'
    default:
      return 'text-(--sk-ok)'
  }
}
```

- [ ] **Step 3: Update filter copy and matching**

Use the approved Korean ranges:

```ts
const usageFilterOptions = [
  { label: '전체 사용률', value: 'all' },
  { label: '위험 (98% 이상)', value: 'critical' },
  { label: '주의 (90–97%)', value: 'warning' },
  { label: '정상 (90% 미만)', value: 'healthy' },
  { label: '정보 없음', value: 'unavailable' }
]
```

Replace the three old threshold predicates inside `filteredRows` with one tier comparison:

```ts
const pct = parsePercent(row.percent)
if (usage !== storageUsageTier(pct)) return false
```

- [ ] **Step 4: Drive summary counts from the classifier**

Replace the old `80` and `60` comparisons in the summary loop:

```ts
switch (storageUsageTier(parsePercent(row.percent))) {
  case 'critical':
    critical++
    break
  case 'warning':
    warning++
    break
  default:
    healthy++
}
```

- [ ] **Step 5: Verify no old storage thresholds remain**

Run from the repository root:

```bash
rg -n "percent >= 80|percent >= 60|pct < 80|pct < 60|80% 이상|60–79%|60% 미만" front-dev-home/app/components/ebeam/StorageView.vue
```

Expected: no matches.

- [ ] **Step 6: Run focused and full frontend verification**

Run from `front-dev-home/`:

```bash
node --test app/utils/storageUsage.test.ts
npm test
npm run lint
npm run typecheck
```

Expected: every command exits with status 0 and reports no failures or errors.

Run from the repository root:

```bash
git diff --check
```

Expected: exit status 0 with no output.

- [ ] **Step 7: Stage only threshold-related component hunks and commit**

Because `StorageView.vue` already contains unrelated local IP-copy edits, use partial staging:

```bash
git add -p front-dev-home/app/components/ebeam/StorageView.vue
git diff --cached -- front-dev-home/app/components/ebeam/StorageView.vue
```

Stage the new import and the usage color, label, filter, and summary hunks. Do not stage the IP-copy template, `copyTextToClipboard`, `copyIp`, or IP-column-width hunks. After confirming the cached diff:

```bash
git diff --cached --check
git commit -m "fix: raise storage usage alert thresholds"
```
