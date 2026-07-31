# Recipe Open Addressing/Measurement Layout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `recipe-search/open`의 `이미지 + 설정` 탭에서 Addressing 이미지와
설정을 왼쪽에, Measurement 이미지와 설정을 오른쪽에 표시합니다.

**Architecture:** 기존 `ParamDetail` API contract는 유지합니다.
`recipeView.ts`의 순수 함수가 Sequence를 제외한 AF/PR 행을 section prefix로
분류하고, `ParamSettings.vue`가 기존 이미지 role과 분류 결과를 사용하여 두
domain 열을 렌더링합니다. 알 수 없는 AF/PR section은 별도 fallback 표에
남겨 open contract를 보존합니다.

**Tech Stack:** Nuxt 4, Vue 3 Composition API, TypeScript, Tailwind utility
classes, Node built-in test runner

## Global Constraints

- 백엔드 응답, `ParamDetail`, raw-recipe endpoint를 변경하지 않습니다.
- 왼쪽은 Addressing 이미지, `addressing_*` AF/PR, Addressing 빔 조건만
  표시합니다.
- 오른쪽은 Measurement 이미지, `measurement_*` AF/PR, Measurement 빔
  조건만 표시합니다.
- 알 수 없는 AF/PR section과 section 없는 행을 누락하지 않습니다.
- 원본 `source`, 행 순서, `null`과 빈 block의 의미 차이를 보존합니다.
- 좁은 화면에서는 Addressing 영역 다음에 Measurement 영역을 쌓습니다.
- `AMP`, `Sequence`, `측정 위치`, image lightbox와 fetch 동작은 변경하지
  않습니다.
- 두 개 이상의 파일을 수정하므로 실행 전에
  `superpowers:using-git-worktrees`로 별도 worktree를 생성합니다.
- 기존 `.remember/` 변경은 사용자 소유이므로 stage하거나 수정하지
  않습니다.

---

## File Map

- `front-dev-home/app/utils/recipeView.ts`: AF/PR block의 domain 분류를
  담당하는 순수 함수와 반환 type을 추가합니다.
- `front-dev-home/app/utils/recipeView.test.ts`: 분류, 순서, source,
  fallback, `null`, 빈 block contract를 검증합니다.
- `front-dev-home/app/components/ebeam/recipeOpen/ParamSettings.vue`: 이미지,
  AF/PR, 빔 조건을 Addressing/Measurement 두 열로 렌더링합니다.

### Task 1: AF/PR Domain 분류 함수

**Files:**

- Modify: `front-dev-home/app/utils/recipeView.test.ts:4-9,270-348`
- Modify: `front-dev-home/app/utils/recipeView.ts:68-97`

**Interfaces:**

- Consumes: `SettingBlock | null`, 각 `SettingRow.section`
- Produces:
  `splitAfPrSectionsByDomain(block: SettingBlock | null): SplitAfPrSettingBlock`
- `SplitAfPrSettingBlock`의 field:
  `addressing`, `measurement`, `other`, 각각 `SettingBlock | null`

- [ ] **Step 1: 테스트에 새 함수 import와 대표 fixture를 추가합니다.**

`recipeView.test.ts`의 import에 `splitAfPrSectionsByDomain`을 추가하고,
기존 `afPrBlock` 아래에 다음 테스트를 추가합니다.

```ts
test('splitAfPrSectionsByDomain separates addressing, measurement and unknown rows', () => {
  const settings = splitSequenceSections({
    source: 'ENMP0012',
    rows: [
      { key: 'Address Method 1', value: 'A1', section: 'addressing_auto_focus1' },
      { key: 'Measure PR', value: 'M1', section: 'measurement_pattern_recognition' },
      { key: 'Address Method 2', value: 'A2', section: 'addressing_auto_focus2' },
      { key: 'Measure Focus', value: 'M2', section: '  MEASUREMENT_Focusing  ' },
      { key: 'Vendor Flag', value: 'V', section: 'vendor_extension' },
      { key: 'Version', value: '3' },
      { key: 'Image Save', value: 'yes', section: 'sequence_measurement' }
    ]
  }).settings

  const grouped = splitAfPrSectionsByDomain(settings)

  assert.deepEqual(
    grouped.addressing?.rows.map(row => row.key),
    ['Address Method 1', 'Address Method 2']
  )
  assert.deepEqual(
    grouped.measurement?.rows.map(row => row.key),
    ['Measure PR', 'Measure Focus']
  )
  assert.deepEqual(
    grouped.other?.rows.map(row => row.key),
    ['Vendor Flag', 'Version']
  )
  assert.equal(grouped.addressing?.source, 'ENMP0012')
  assert.equal(grouped.measurement?.source, 'ENMP0012')
  assert.equal(grouped.other?.source, 'ENMP0012')
})

test('splitAfPrSectionsByDomain preserves empty blocks for domains absent from a file', () => {
  assert.deepEqual(
    splitAfPrSectionsByDomain({
      source: 'ENMP0013',
      rows: [
        { key: 'Method', value: 'Fast2', section: 'measurement_focusing' }
      ]
    }),
    {
      addressing: { source: 'ENMP0013', rows: [] },
      measurement: {
        source: 'ENMP0013',
        rows: [
          { key: 'Method', value: 'Fast2', section: 'measurement_focusing' }
        ]
      },
      other: { source: 'ENMP0013', rows: [] }
    }
  )
})

test('splitAfPrSectionsByDomain passes a missing file through as null', () => {
  assert.deepEqual(splitAfPrSectionsByDomain(null), {
    addressing: null,
    measurement: null,
    other: null
  })
})
```

이 테스트에서 production change를 제거하면 domain별 기대 행과 fallback
보존 assertion이 실패합니다. mock이나 component mounting 없이 실제 순수
함수를 직접 검증합니다.

- [ ] **Step 2: 새 테스트가 올바른 이유로 실패하는지 확인합니다.**

Run:

```bash
cd front-dev-home
node --test app/utils/recipeView.test.ts
```

Expected: `splitAfPrSectionsByDomain` export가 없어서 FAIL합니다.

- [ ] **Step 3: 최소 domain 분류 구현을 추가합니다.**

`recipeView.ts`의 `splitSequenceSections` 다음에 추가합니다.

```ts
export interface SplitAfPrSettingBlock {
  addressing: SettingBlock | null
  measurement: SettingBlock | null
  other: SettingBlock | null
}

export function splitAfPrSectionsByDomain(
  block: SettingBlock | null
): SplitAfPrSettingBlock {
  if (!block) {
    return {
      addressing: null,
      measurement: null,
      other: null
    }
  }

  const addressing: SettingRow[] = []
  const measurement: SettingRow[] = []
  const other: SettingRow[] = []

  for (const row of block.rows) {
    const section = row.section?.trim().toLowerCase() ?? ''
    if (section.startsWith('addressing_')) {
      addressing.push(row)
    } else if (section.startsWith('measurement_')) {
      measurement.push(row)
    } else {
      other.push(row)
    }
  }

  const withRows = (rows: SettingRow[]): SettingBlock => ({
    source: block.source,
    rows
  })

  return {
    addressing: withRows(addressing),
    measurement: withRows(measurement),
    other: withRows(other)
  }
}
```

- [ ] **Step 4: focused test와 TypeScript 검사를 실행합니다.**

Run:

```bash
cd front-dev-home
node --test app/utils/recipeView.test.ts
npm run typecheck
```

Expected: 모든 `recipeView` test가 PASS하고 typecheck가 exit 0입니다.

- [ ] **Step 5: Task 1 파일만 commit합니다.**

```bash
git add front-dev-home/app/utils/recipeView.ts \
  front-dev-home/app/utils/recipeView.test.ts
git diff --cached --check
git commit -m "feat(recipe-search): classify AF PR settings by domain"
```

### Task 2: Addressing/Measurement 두 열 렌더링

**Files:**

- Modify:
  `front-dev-home/app/components/ebeam/recipeOpen/ParamSettings.vue:7-94`

**Interfaces:**

- Consumes:
  `splitAfPrSectionsByDomain(block)`의
  `{ addressing, measurement, other }`
- Consumes: 기존 `ParamImage`, `roleOf(slot)`, `imageSrc(name)`
- Produces: `lanes`, 각 항목은 `key`, `title`, `images`, `afPr`를 가집니다.

- [ ] **Step 1: 기존 flat 이미지 행과 서로 다른 의미의 두 설정 열을
  domain lane markup으로 교체합니다.**

`ParamSettings.vue` template의 기존 이미지 행과 설정 grid를 다음 구조로
교체합니다.

```vue
<div class="grid gap-3 md:grid-cols-2 md:items-start">
  <section
    v-for="lane in lanes"
    :key="lane.key"
    class="flex min-w-0 flex-col gap-3 rounded-xl border border-zinc-200/70 p-3 dark:border-zinc-800/60"
  >
    <div class="flex items-center justify-between gap-2">
      <span class="text-xs font-bold tracking-wide text-zinc-900 dark:text-zinc-100">
        {{ lane.title }}
      </span>
      <span class="font-mono text-[10px] text-(--sk-ink-muted)">
        {{ lane.images.length }} image
      </span>
    </div>

    <div
      v-if="lane.images.length"
      class="grid gap-3"
      :style="{ gridTemplateColumns: `repeat(${lane.images.length}, minmax(0, 1fr))` }"
    >
      <EbeamRecipeOpenImgThumb
        v-for="image in lane.images"
        :key="image.slot"
        :label="image.slot"
        :stage="image.stage"
        :name="image.name"
        :src="imageSrc(image.name)"
        :role="roleOf(image.slot)"
        @open="emit('openImage', image)"
      />
    </div>
    <p
      v-else-if="!pending"
      class="sk-meta"
    >
      {{ lane.title }} 이미지가 없습니다.
    </p>

    <EbeamRecipeOpenSettingTable
      title="AF / PR (포커스 · 패턴 인식)"
      :block="lane.afPr"
    />

    <EbeamRecipeOpenSettingTable
      v-for="image in lane.images"
      :key="`cond-${image.slot}`"
      :title="`${image.stage} 빔 조건`"
      :block="image.cond"
    />
  </section>
</div>

<EbeamRecipeOpenSettingTable
  v-if="groupedAfPr.other?.rows.length"
  class="mt-3"
  title="기타 AF / PR"
  :block="groupedAfPr.other"
/>
```

이 구조에서 outer grid의 DOM 순서는 Addressing, Measurement입니다.
`md:grid-cols-2`보다 좁으면 동일한 순서로 세로 배치됩니다.

- [ ] **Step 2: script의 단일 AF/PR computed를 domain lane model로
  교체합니다.**

`splitAfPrSectionsByDomain`을 import하고 기존 `afPrSettings` computed를
다음 코드로 교체합니다.

```ts
const groupedAfPr = computed(() => splitAfPrSectionsByDomain(
  splitSequenceSections(props.detail?.af_pr ?? null).settings
))

const lanes = computed(() => [
  {
    key: 'address',
    title: 'Addressing',
    images: images.value.filter(image => roleOf(image.slot) === 'address'),
    afPr: groupedAfPr.value.addressing
  },
  {
    key: 'measure',
    title: 'Measurement',
    images: images.value.filter(image => roleOf(image.slot) === 'measure'),
    afPr: groupedAfPr.value.measurement
  }
] as const)
```

Import는 다음 shape를 사용합니다.

```ts
import {
  IMAGE_SLOTS,
  splitAfPrSectionsByDomain,
  splitSequenceSections,
  type SlotRole
} from '~/utils/recipeView'
```

- [ ] **Step 3: focused frontend 검사를 실행합니다.**

Run:

```bash
cd front-dev-home
node --test app/utils/recipeView.test.ts
npm run typecheck
npm run lint -- app/utils/recipeView.ts app/utils/recipeView.test.ts \
  app/components/ebeam/recipeOpen/ParamSettings.vue
```

Expected: test, typecheck, scoped ESLint가 모두 exit 0입니다.

- [ ] **Step 4: 실행 화면에서 layout과 기존 동작을 확인합니다.**

Backend와 frontend dev server를 실행하고 Redis-backed recipe의
`recipe-search/open` 화면에서 `이미지 + 설정` 탭을 확인합니다.

Desktop 확인:

- Addressing 열이 왼쪽, Measurement 열이 오른쪽입니다.
- `img_add1`, `image_add3` 썸네일과 각 빔 조건은 왼쪽입니다.
- `img_meas1` 썸네일과 빔 조건은 오른쪽입니다.
- `addressing_*` AF/PR 행은 왼쪽, `measurement_*` 행은 오른쪽입니다.
- thumbnail click의 기존 lightbox가 열립니다.

Narrow viewport 확인:

- 두 열이 Addressing 다음 Measurement 순서로 세로 배치됩니다.
- 각 표의 가로 overflow와 전체 panel 세로 scroll이 유지됩니다.

실행 화면을 사용할 수 없으면 source, test, typecheck, lint 검증과
미확인 visual 항목을 완료 보고에서 명확히 구분합니다.

- [ ] **Step 5: Task 2 파일만 commit합니다.**

```bash
git add front-dev-home/app/components/ebeam/recipeOpen/ParamSettings.vue
git diff --cached --check
git commit -m "feat(recipe-search): separate addressing and measurement settings"
```

### Task 3: 전체 frontend 회귀 검사와 main 통합

**Files:**

- Verify only: `front-dev-home/`
- Preserve: `.remember/`

**Interfaces:**

- Consumes: Task 1과 Task 2의 두 commit
- Produces: 검증된 local `main` 통합 commit history

- [ ] **Step 1: 전체 frontend test를 실행합니다.**

Run:

```bash
cd front-dev-home
npm test
```

Expected: 전체 Node test suite가 PASS합니다.

- [ ] **Step 2: production type/build gate를 실행합니다.**

Run:

```bash
cd front-dev-home
npm run typecheck
npm run build
```

Expected: 두 command 모두 exit 0입니다.

- [ ] **Step 3: diff와 worktree 상태를 확인합니다.**

Run:

```bash
git status --short
git diff --check HEAD~2..HEAD
git log -2 --oneline
```

Expected: worktree에 Task 1/2 외 변경이 없고 두 commit만 표시됩니다.

- [ ] **Step 4: main에 fast-forward 통합하고 임시 worktree를 제거합니다.**

Main checkout에서 실행합니다.

```bash
git merge --ff-only work/recipe-open-domain-layout
git worktree remove ../skewnono-recipe-open-domain-layout
git branch -d work/recipe-open-domain-layout
git worktree list
```

Expected: `main`이 두 implementation commit을 포함하며 임시 worktree와
`work/recipe-open-domain-layout` branch가 제거됩니다. 사용자가 별도로
요청하지 않았으므로 이 plan은 remote push를 수행하지 않습니다.
