# Tool Roster Cleanup and Table Refinement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 모든 화면에서 두 VeritySEM 모델 접두사를 올바르게 분류하고, Tool Roster에서 `127.0.0.1` 장비를 제외하며, 랜딩 복귀 버튼과 `DESIGN.md`에 맞는 읽기 좋은 집계표를 제공합니다.

**Architecture:** 공용 장비 분류 함수가 VeritySEM 표기 변형을 한 번에 해석하도록 확장합니다. Tool Roster 전용 순수 함수가 API 응답의 루프백 행을 화면 파생 상태보다 먼저 제외합니다. 페이지는 고정된 `/` 링크, Terracotta `SkChip` 필터, Paper/Walnut surface와 hairline grid, Ink 선택 셀, inset 드릴다운을 렌더링하며 백엔드 pending API 계약과 환경별 office adapter는 변경하지 않습니다.

**Tech Stack:** Nuxt 4, Vue 3, TypeScript, `@nuxt/ui`, Node test runner, `@vue/compiler-sfc`

## Global Constraints

- `VeritySEM`과 `Verity_SEM` 접두사만 대소문자 무관 규칙을 추가합니다.
- `127.0.0.1`만 제외하며, 비교 전에 `eqp_ip.trim()`을 적용합니다.
- 루프백 행은 Tool Roster의 수량, 필터, 매트릭스, 드릴다운, IP 복사와 CSV에서 모두 제외합니다.
- 알 수 없는 다른 모델은 계속 `미분류`로 유지합니다.
- 뒤로가기 버튼은 브라우저 이력이 아니라 고정된 랜딩 경로 `/`로 이동합니다.
- Tool Type 필터는 데이터를 좁히므로 활성 상태에 Terracotta를 쓰는 `SkChip`을
  사용합니다.
- 표의 값은 12px 이상의 full Ink, 레이블만 muted Ink를 사용합니다.
- 카드·표·inset panel은 `--sk-surface`, `--sk-muted-surface`,
  `--sk-border-soft`와 6/8/10/14px radius scale만 사용합니다.
- 표 행 hover 이외에는 직접적인 zinc 색상 클래스를 추가하지 않습니다.
- 집계표는 카드 폭을 채우고 모델 열이 넘칠 때만 가로 스크롤합니다.
- 선택 셀은 NAVIGATE 의미의 Ink fill과 `aria-pressed`를 사용합니다.
- `GET /api/sem-list/pending` 계약과 백엔드 provider를 변경하지 않습니다.
- Pinia, Vue Query, Vitest, Jest, jsdom 또는 새 의존성을 추가하지 않습니다.
- 여러 제품 파일을 수정하므로 격리된 git worktree에서 구현하고 완료 후 즉시 제거합니다.

---

## File Map

| File | Responsibility |
| --- | --- |
| `front-dev-home/app/utils/toolType.ts` | 모든 프론트엔드 화면이 공유하는 모델 접두사 분류 |
| `front-dev-home/app/utils/toolType.test.ts` | VeritySEM 접두사와 대소문자 회귀 테스트 |
| `front-dev-home/app/utils/pendingToolMatrix.ts` | Tool Roster 전용 행 정제와 기존 집계 순수 함수 |
| `front-dev-home/app/utils/pendingToolMatrix.test.ts` | 루프백 제외 규칙의 순수 함수 테스트 |
| `front-dev-home/app/pages/tool-roster.vue` | 정제된 행, 랜딩 링크와 DESIGN.md 기반 집계·드릴다운 UI |

### Task 1: 공용 VeritySEM 분류

**Files:**

- Create: `front-dev-home/app/utils/toolType.test.ts`
- Modify: `front-dev-home/app/utils/toolType.ts:16-22`

**Interfaces:**

- Consumes: `classifyToolType(eqpModelCd: string): ToolType | null`
- Produces: 같은 함수가 `VERITYSEM` 또는 `VERITY_SEM` 접두사의 대소문자
  변형에 대해 `'verity-sem'`을 반환합니다.

- [ ] **Step 1: 실패하는 공용 분류 테스트 작성**

```ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { classifyToolType } from './toolType.ts'

test('classifyToolType recognizes both VeritySEM prefixes case-insensitively', () => {
  for (const model of [
    'VERITYSEM_4',
    'VeritySEM_4',
    'veritysem_4',
    'VERITY_SEM_5',
    'Verity_SEM_5',
    'verity_sem_5'
  ]) {
    assert.equal(classifyToolType(model), 'verity-sem', model)
  }
})

test('classifyToolType keeps an unrelated model unclassified', () => {
  assert.equal(classifyToolType('ZZ9000'), null)
})
```

- [ ] **Step 2: 실패 확인**

Run:

```bash
cd front-dev-home
node --test app/utils/toolType.test.ts
```

Expected: 첫 번째 테스트가 `VeritySEM_4` 또는 `VERITY_SEM_5`에서
`null !== 'verity-sem'`으로 실패합니다.

- [ ] **Step 3: 최소 분류 구현**

`classifyToolType()`의 VeritySEM 분기만 다음과 같이 변경합니다.

```ts
export const classifyToolType = (eqpModelCd: string): ToolType | null => {
  if (eqpModelCd.startsWith('CG') || eqpModelCd.startsWith('GT')) return 'cd-sem'
  if (eqpModelCd.startsWith('TP')) return 'hv-sem'
  const normalizedModel = eqpModelCd.toUpperCase()
  if (
    normalizedModel.startsWith('VERITYSEM')
    || normalizedModel.startsWith('VERITY_SEM')
  ) return 'verity-sem'
  if (eqpModelCd.startsWith('PROVISION')) return 'provision'
  return null
}
```

- [ ] **Step 4: 통과 확인**

Run:

```bash
cd front-dev-home
node --test app/utils/toolType.test.ts
```

Expected: 2 tests pass.

- [ ] **Step 5: 첫 번째 변경 커밋**

```bash
git add front-dev-home/app/utils/toolType.ts front-dev-home/app/utils/toolType.test.ts
git commit -m "fix(tool-type): recognize VeritySEM model variants"
```

### Task 2: Tool Roster 루프백 행 제외

**Files:**

- Modify: `front-dev-home/app/utils/pendingToolMatrix.ts:48-69`
- Modify: `front-dev-home/app/utils/pendingToolMatrix.test.ts:1-60`
- Modify: `front-dev-home/app/pages/tool-roster.vue:214-233`

**Interfaces:**

- Consumes: `PendingToolRow[]`
- Produces:
  `filterActionablePendingTools(rows: PendingToolRow[]): PendingToolRow[]`
- Page integration: `rows`는 `filterActionablePendingTools(data.value ?? [])`의
  계산 결과입니다.

- [ ] **Step 1: 실패하는 루프백 제외 테스트 작성**

`pendingToolMatrix.test.ts`의 import에 `filterActionablePendingTools`를 추가하고
다음 테스트를 작성합니다.

```ts
test('filterActionablePendingTools removes only exact loopback IPs after trimming', () => {
  const rows = [
    tool('A', 'CG6380', 'M16A', '177.1.1.1'),
    tool('B', 'CG6380', 'M16A', '127.0.0.1'),
    tool('C', 'TP4000', 'M14B', ' 127.0.0.1 '),
    tool('D', 'TP4000', 'M14B', '127.0.0.2'),
    tool('E', 'GT2000', 'M16B', '')
  ]

  assert.deepEqual(
    filterActionablePendingTools(rows).map(row => row.eqp_id),
    ['A', 'D', 'E']
  )
  assert.equal(rows.length, 5)
})
```

- [ ] **Step 2: 실패 확인**

Run:

```bash
cd front-dev-home
node --test app/utils/pendingToolMatrix.test.ts
```

Expected: 모듈에 `filterActionablePendingTools` export가 없어 실패합니다.

- [ ] **Step 3: 최소 순수 함수 구현**

`pendingToolMatrix.ts`에서 `fabLabel` 아래에 다음 함수를 추가합니다.

```ts
export const filterActionablePendingTools = (
  rows: PendingToolRow[]
): PendingToolRow[] => rows.filter(row => row.eqp_ip.trim() !== '127.0.0.1')
```

- [ ] **Step 4: 페이지 최상위 행 계산에 정제 함수 연결**

`tool-roster.vue`의 `pendingToolMatrix` import에
`filterActionablePendingTools`를 추가하고 `rows` 계산을 변경합니다.

```ts
const rows = computed<PendingToolRow[]>(() =>
  filterActionablePendingTools(data.value ?? [])
)
```

헤더 수량, 빈 상태, `countByGroup`, `filterByGroup`, 매트릭스, IP 복사와 CSV가
모두 기존 `rows` 또는 그 파생값을 사용하므로 다른 위치에 IP 조건을 추가하지
않습니다.

- [ ] **Step 5: 통과 확인**

Run:

```bash
cd front-dev-home
node --test app/utils/pendingToolMatrix.test.ts
```

Expected: 모든 `pendingToolMatrix` tests pass.

- [ ] **Step 6: 두 번째 변경 커밋**

```bash
git add front-dev-home/app/utils/pendingToolMatrix.ts \
  front-dev-home/app/utils/pendingToolMatrix.test.ts \
  front-dev-home/app/pages/tool-roster.vue
git commit -m "fix(tool-roster): exclude loopback roster rows"
```

### Task 3: 랜딩 복귀와 DESIGN.md 기반 표 개선

**Files:**

- Modify: `front-dev-home/app/pages/tool-roster.vue:7-210`

**Interfaces:**

- Consumes: Nuxt UI `UButton`, `SkChip`, `selectedCell`,
  `matrix: PendingToolMatrix`
- Produces:
  - `to="/"`, `label="뒤로가기"`,
    `icon="i-lucide-arrow-left"`인 헤더 버튼
  - Terracotta 활성 상태의 Tool Type `SkChip`
  - full-width hairline 집계표, sticky header/Fab 열과 Ink 선택 셀
  - `--sk-muted-surface` inset drill-down panel

- [ ] **Step 1: 헤더 버튼 구현**

`tool-roster.vue`의 제목 앞에 다음 버튼과 hairline 구분자를 배치합니다.
테스트와 속성 순서를 일치시킵니다.

```vue
<UButton
  to="/"
  size="sm"
  color="neutral"
  variant="ghost"
  icon="i-lucide-arrow-left"
  label="뒤로가기"
/>
<span
  class="h-6 w-px bg-(--sk-border-soft)"
  aria-hidden="true"
/>
```

- [ ] **Step 2: 필터를 Terracotta `SkChip`으로 교체**

기존 filter bar의 `UButton v-for`를 다음 구조로 교체합니다.

```vue
<div
  class="flex flex-wrap items-center gap-2 border-b border-(--sk-border) bg-(--sk-brand-soft) px-4 py-3"
>
  <div
    class="flex flex-wrap items-center gap-1.5"
    role="group"
    aria-label="장비 유형 필터"
  >
    <SkChip
      v-for="chip in groupChips"
      :key="chip.value"
      size="sm"
      :label="chip.label"
      :count="chip.count"
      :active="chip.value === activeGroup"
      @click="selectGroup(chip.value)"
    />
  </div>
  <div class="flex-1" />
  <UButton
    size="sm"
    color="neutral"
    variant="outline"
    icon="i-lucide-clipboard"
    label="IP 목록 복사"
    :disabled="visibleRows.length === 0"
    @click="copyIpList"
  />
  <UButton
    size="sm"
    color="neutral"
    variant="outline"
    icon="i-lucide-download"
    label="CSV 다운로드"
    :disabled="visibleRows.length === 0"
    @click="downloadPendingCsv"
  />
</div>
```

- [ ] **Step 3: 집계표를 full-width hairline matrix로 재구성**

표에는 접근 가능한 caption을 추가하고 다음 구조를 적용합니다.

```vue
<table class="min-w-full w-max border-separate border-spacing-0 text-left">
  <caption class="sr-only">
    Fab별 미연결 장비 모델 수
  </caption>
  <thead>
    <tr>
      <th
        scope="col"
        class="sticky left-0 top-0 z-30 border-b border-r border-(--sk-border-soft) bg-(--sk-muted-surface) px-3 py-2 sk-label"
      >
        Fab
      </th>
      <th
        v-for="model in matrix.models"
        :key="model"
        scope="col"
        class="sticky top-0 z-20 whitespace-nowrap border-b border-r border-(--sk-border-soft) bg-(--sk-muted-surface) px-3 py-2 text-center sk-label"
      >
        {{ model }}
      </th>
      <th
        scope="col"
        class="sticky right-0 top-0 z-30 border-b border-l border-(--sk-border-soft) bg-(--sk-muted-surface) px-3 py-2 text-center sk-label"
      >
        합계
      </th>
    </tr>
  </thead>
  <tbody>
    <tr
      v-for="(fab, fabAt) in matrix.fabs"
      :key="fab"
      class="group transition-colors hover:bg-zinc-50 dark:hover:bg-zinc-800/50"
    >
      <th
        scope="row"
        class="sticky left-0 z-10 whitespace-nowrap border-b border-r border-(--sk-border-soft) bg-(--sk-surface) px-3 py-1.5 text-left group-hover:bg-zinc-50 dark:group-hover:bg-zinc-800/50 sk-value"
      >
        {{ fab }}
      </th>
      <td
        v-for="(model, modelAt) in matrix.models"
        :key="model"
        class="border-b border-r border-(--sk-border-soft) px-3 py-1.5 text-center"
      >
        <button
          v-if="cellCount(fabAt, modelAt)"
          type="button"
          :aria-pressed="isSelectedCell(fab, model)"
          class="inline-flex min-h-7 min-w-8 items-center justify-center rounded-[var(--sk-r-sidebar)] border px-2 py-1 transition-colors sk-value-num"
          :class="isSelectedCell(fab, model)
            ? 'border-(--sk-ink) bg-(--sk-ink) text-(--sk-ink-fg)'
            : 'border-(--sk-border) bg-(--sk-muted-surface) text-(--sk-ink) hover:bg-(--sk-accent-soft)'"
          @click="selectCell(fab, model)"
        >
          {{ cellCount(fabAt, modelAt) }}
        </button>
        <span
          v-else
          class="text-(--sk-ink-subtle) sk-label"
        >·</span>
      </td>
      <td class="sticky right-0 z-10 border-b border-l border-(--sk-border-soft) bg-(--sk-surface) px-3 py-1.5 text-center group-hover:bg-zinc-50 dark:group-hover:bg-zinc-800/50 sk-value-num">
        {{ matrix.fabTotals[fabAt] }}
      </td>
    </tr>
  </tbody>
  <tfoot>
    <tr class="bg-(--sk-muted-surface)">
      <th
        scope="row"
        class="sticky left-0 z-10 border-r border-t border-(--sk-border-soft) bg-(--sk-muted-surface) px-3 py-2 text-left sk-label"
      >
        합계
      </th>
      <td
        v-for="(model, modelAt) in matrix.models"
        :key="model"
        class="border-r border-t border-(--sk-border-soft) px-3 py-2 text-center sk-value-num"
      >
        {{ matrix.modelTotals[modelAt] }}
      </td>
      <td class="sticky right-0 z-10 border-l border-t border-(--sk-border-soft) bg-(--sk-muted-surface) px-3 py-2 text-center sk-value-num">
        {{ matrix.total }}
      </td>
    </tr>
  </tfoot>
</table>
```

`script setup`에 선택 여부 helper를 추가합니다.

```ts
const isSelectedCell = (fab: string, model: string): boolean =>
  selectedCell.value?.fab === fab && selectedCell.value.model === model
```

- [ ] **Step 4: 드릴다운을 inset panel로 묶기**

선택 상세 영역의 바깥 구조를 다음처럼 변경합니다.

```vue
<div
  v-if="selectedCell"
  class="m-3 overflow-hidden rounded-[var(--sk-r-card)] border border-(--sk-border) bg-(--sk-muted-surface)"
>
  <div class="flex items-center justify-between gap-3 border-b border-(--sk-border-soft) px-3 py-2.5">
    <div class="flex items-center gap-2">
      <h3 class="sk-title">{{ selectedCell.fab }} / {{ selectedCell.model }}</h3>
      <UBadge color="neutral" variant="subtle">{{ drilldownRows.length }}대</UBadge>
    </div>
    <UButton
      size="xs"
      color="neutral"
      variant="ghost"
      icon="i-lucide-x"
      aria-label="드릴다운 닫기"
      @click="selectedCell = null"
    />
  </div>
  <UTable
    class="bg-(--sk-surface)"
    :columns="drilldownColumns"
    :data="drilldownRows"
    :meta="drilldownTableMeta"
    :ui="{
      root: 'w-full',
      base: 'min-w-0 w-full',
      td: 'px-3 py-1.5 sk-value',
      th: 'px-3 py-2 sk-label'
    }"
  >
    <template #eqp_id-cell="{ row }">
      <span class="sk-value-num">{{ row.original.eqp_id }}</span>
    </template>
    <template #eqp_ip-cell="{ row }">
      <span class="sk-value-num">{{ row.original.eqp_ip }}</span>
    </template>
    <template #vendor_nm-cell="{ row }">
      <span class="capitalize sk-value">
        {{ row.original.vendor_nm.toLowerCase() }}
      </span>
    </template>
    <template #updt_dt-cell="{ row }">
      <span class="sk-value-num">{{ arrivalDate(row.original.updt_dt) }}</span>
    </template>
  </UTable>
</div>
```

- [ ] **Step 5: Vue 정적 검증**

Run:

```bash
cd front-dev-home
npm run typecheck
./node_modules/.bin/eslint app/pages/tool-roster.vue
```

Expected: 두 명령 모두 exit 0입니다. 이 저장소에는 Vue mounting harness가
없으므로 SFC 소스 문자열을 검사하는 change-detector 테스트를 만들지 않습니다.
버튼 이동과 시각 구조는 Task 4의 실행 화면 검증에서 확인합니다.

- [ ] **Step 6: 세 번째 변경 커밋**

```bash
git add front-dev-home/app/pages/tool-roster.vue
git commit -m "style(tool-roster): refine roster table hierarchy"
```

### Task 4: 전체 검증과 UI 확인

**Files:**

- Verify only: `front-dev-home/app/utils/toolType.ts`
- Verify only: `front-dev-home/app/utils/toolType.test.ts`
- Verify only: `front-dev-home/app/utils/pendingToolMatrix.ts`
- Verify only: `front-dev-home/app/utils/pendingToolMatrix.test.ts`
- Verify only: `front-dev-home/app/pages/tool-roster.vue`

**Interfaces:**

- Consumes: Tasks 1-3의 세 독립 커밋
- Produces: 자동 검증 결과와 실행 중인 앱의 UI 확인 기록

- [ ] **Step 1: 전체 프론트엔드 테스트 실행**

Run:

```bash
cd front-dev-home
npm test
```

Expected: 모든 Node tests pass.

- [ ] **Step 2: TypeScript 검사 실행**

Run:

```bash
cd front-dev-home
npm run typecheck
```

Expected: Nuxt typecheck exits 0.

- [ ] **Step 3: 변경 파일 ESLint 실행**

Run:

```bash
cd front-dev-home
./node_modules/.bin/eslint \
  app/utils/toolType.ts \
  app/utils/toolType.test.ts \
  app/utils/pendingToolMatrix.ts \
  app/utils/pendingToolMatrix.test.ts \
  app/pages/tool-roster.vue
```

Expected: exits 0 with no errors.

- [ ] **Step 4: 작업 트리와 커밋 범위 확인**

Run:

```bash
git status --short
git log -4 --oneline
git diff HEAD~3..HEAD --check
git diff HEAD~3..HEAD --stat
```

Expected: 제품 파일은 clean이고, 최근 세 커밋은 Tasks 1-3만 포함하며,
whitespace 오류가 없습니다.

- [ ] **Step 5: 실행 중인 앱에서 UI 검증**

백엔드와 Nuxt를 실행한 뒤 `/tool-roster`에서 다음을 확인합니다.

- `뒤로가기` 버튼이 보이고 선택하면 `/`로 이동합니다.
- `VERITYSEM*`, `VERITY_SEM*`와 대소문자 변형이 VeritySEM 수량에 포함됩니다.
- 해당 행이 더 이상 `미분류` 수량에 포함되지 않습니다.
- `127.0.0.1` 행이 전체 수량, Tool Type 수량, 매트릭스와 드릴다운에 없습니다.
- IP 복사와 CSV에도 `127.0.0.1`이 없습니다.
- 실제 데이터에 해당 변형이 없으면 순수 함수 자동 테스트를 증거로 남기고,
  버튼과 기존 데이터의 화면 회귀만 확인합니다.
- Tool Type 활성 필터는 Terracotta이고 비활성 필터는 Paper surface입니다.
- 집계표는 카드 폭을 채우며 값은 12px full Ink로 읽힙니다.
- 헤더와 Fab 열은 스크롤 중 고정되고 hairline grid가 행·열 관계를 구분합니다.
- 선택 셀은 Ink fill이며 `aria-pressed="true"`입니다.
- 드릴다운은 muted inset panel 안에서 집계표와 명확히 연결됩니다.
- 좁은 viewport에서는 숫자나 모델명이 줄바꿈되지 않고 표 내부만 가로
  스크롤합니다.

- [ ] **Step 6: main에 fast-forward 병합하고 정리**

main 작업 트리에서 다음을 실행합니다.

```bash
git merge --ff-only work/tool-roster-cleanup
git worktree remove ../skewnono-tool-roster-cleanup
git branch -d work/tool-roster-cleanup
git worktree list
```

Expected: `main`이 구현 커밋을 포함하고 worktree 목록에는 기본 작업 트리만
남습니다. 사용자가 별도로 요청하지 않았으므로 push는 수행하지 않습니다.
