# Recipe Compare 개선 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Recipe 비교 화면에서 인라인 "+recipe 추가"를 제거하고, "Recipe 검색으로" 돌아가기 버튼을 추가하며, Excel 다운로드 시 활성 슬롯+파라미터의 SEM 썸네일을 셀 이미지로 삽입한다.

**Architecture:** Excel 이미지 삽입을 위해 비교 export만 `xlsx` → `exceljs`로 교체한다. 순수·테스트된 `buildCompareWorkbook`은 그대로 두고, 엔진/이미지 변경은 writer(`downloadCompareWorkbook`)와 신규 브라우저 전용 헬퍼(`semNoiseImage.ts`)에 격리한다. PNG는 canvas로 `SemNoise` 텍스처를 재현해 view에서 생성, writer로 data URL을 전달한다(브라우저 캔버스 코드를 `node --test` 대상 `recipeCompare.ts`에 import하지 않기 위함).

**Tech Stack:** Nuxt 4 + NuxtUI, `<script setup>`, ExcelJS, Canvas 2D, Vue Router.

**Spec:** `docs/superpowers/specs/2026-06-14-recipe-compare-refinements-design.md`

**Testing note:** 변경되는 코드는 `.vue` 컴포넌트, 브라우저 전용 canvas/ExcelJS writer뿐이며 추출 가능한 순수 로직 추가가 없다(`buildCompareWorkbook`은 미변경, 기존 `node --test`로 회귀만 확인). 따라서 이 계획의 검증 게이트는 `node --test`(회귀) + `nuxt typecheck` + `eslint` + Playwright E2E다.

---

## File Structure

- `front-dev-home/package.json` — `exceljs` 의존성 추가 (modify)
- `front-dev-home/app/utils/semNoiseImage.ts` — canvas로 SEM 노이즈 PNG 생성 (create, 브라우저 전용)
- `front-dev-home/app/utils/recipeCompare.ts` — `downloadCompareWorkbook`를 ExcelJS + 이미지 블록으로 재작성 (modify; `buildCompareWorkbook` 등 순수 함수는 미변경)
- `front-dev-home/app/components/ebeam/recipeCompare/RecipeSetBar.vue` — "+recipe 추가" 제거, back 버튼 추가 (modify)
- `front-dev-home/app/components/ebeam/RecipeCompareView.vue` — add 배선 제거, backRoute 전달, downloadExcel가 imageBlock 전달 (modify)

---

### Task 1: `exceljs` 의존성 추가

**Files:**
- Modify: `front-dev-home/package.json`

- [ ] **Step 1: 설치**

Run (from `front-dev-home/`): `npm install exceljs`
Expected: `exceljs` added to `dependencies`, exit 0.

- [ ] **Step 2: 설치 확인**

Run (from `front-dev-home/`): `node -e "console.log(require('exceljs/package.json').version)"`
Expected: 버전 문자열 출력 (예: `4.x.x`).

- [ ] **Step 3: Commit**

```bash
git add front-dev-home/package.json front-dev-home/package-lock.json
git commit -m "build(recipe-compare): add exceljs for Excel cell images"
```

---

### Task 2: `semNoiseImage.ts` — canvas SEM 노이즈 PNG 헬퍼

**Files:**
- Create: `front-dev-home/app/utils/semNoiseImage.ts`

- [ ] **Step 1: 파일 작성**

`front-dev-home/app/utils/semNoiseImage.ts`를 아래 내용으로 생성:

```ts
// Browser-only helper. Renders a deterministic SEM-noise placeholder PNG that
// mirrors EbeamRecipeOpenSemNoise (a fixed CSS-gradient texture on #23201B), so
// the Excel export shows the same placeholder the compare matrix shows on screen.
//
// IMPORTANT: do NOT import this from recipeCompare.ts. That module is run under
// `node --test`, which has no `document`/`canvas`. The compare view (browser)
// calls this and passes the resulting data URL into downloadCompareWorkbook.

export type SemRole = 'address' | 'measure'

export function renderSemNoisePng(role: SemRole, size = 180): string {
  const canvas = document.createElement('canvas')
  canvas.width = size
  canvas.height = size
  const ctx = canvas.getContext('2d')
  if (!ctx) return ''

  // base fill (matches SemNoise background #23201B)
  ctx.fillStyle = '#23201B'
  ctx.fillRect(0, 0, size, size)

  // diagonal light lines (~45deg): 2px stroke, 5px pitch
  ctx.save()
  ctx.translate(size / 2, size / 2)
  ctx.rotate(Math.PI / 4)
  ctx.translate(-size, -size)
  ctx.strokeStyle = 'rgba(255,255,255,0.04)'
  ctx.lineWidth = 2
  for (let y = 0; y < size * 2; y += 5) {
    ctx.beginPath()
    ctx.moveTo(0, y)
    ctx.lineTo(size * 2, y)
    ctx.stroke()
  }
  ctx.restore()

  // diagonal dark lines (~-30deg): 1px stroke, 3px pitch
  ctx.save()
  ctx.translate(size / 2, size / 2)
  ctx.rotate(-Math.PI / 6)
  ctx.translate(-size, -size)
  ctx.strokeStyle = 'rgba(0,0,0,0.18)'
  ctx.lineWidth = 1
  for (let y = 0; y < size * 2; y += 3) {
    ctx.beginPath()
    ctx.moveTo(0, y)
    ctx.lineTo(size * 2, y)
    ctx.stroke()
  }
  ctx.restore()

  // soft radial highlights
  const glow = (cx: number, cy: number, r: number, alpha: number) => {
    const g = ctx.createRadialGradient(cx, cy, 0, cx, cy, r)
    g.addColorStop(0, `rgba(255,255,255,${alpha})`)
    g.addColorStop(1, 'rgba(255,255,255,0)')
    ctx.fillStyle = g
    ctx.fillRect(0, 0, size, size)
  }
  glow(size * 0.30, size * 0.40, size * 0.60, 0.07)
  glow(size * 0.70, size * 0.70, size * 0.55, 0.05)

  // role badge (MEAS / ADDR) top-left
  const isMeas = role === 'measure'
  const label = isMeas ? 'MEAS' : 'ADDR'
  ctx.font = `bold ${Math.round(size * 0.066)}px monospace`
  ctx.textBaseline = 'middle'
  const padX = size * 0.04
  const textW = ctx.measureText(label).width
  const bx = size * 0.04
  const by = size * 0.04
  const bw = textW + padX * 2
  const bh = size * 0.11
  ctx.fillStyle = isMeas ? '#2f6df0' : '#1f1b16'
  ctx.fillRect(bx, by, bw, bh)
  ctx.fillStyle = '#ffffff'
  ctx.fillText(label, bx + padX, by + bh / 2 + size * 0.004)

  return canvas.toDataURL('image/png')
}
```

- [ ] **Step 2: Typecheck**

Run (from `front-dev-home/`): `npm run typecheck`
Expected: 클린 (TS 에러 없음; `ℹ Nuxt Icon ...` info 라인만).

- [ ] **Step 3: Lint**

Run (from `front-dev-home/`): `npx eslint app/utils/semNoiseImage.ts`
Expected: exit 0, 출력 없음.

- [ ] **Step 4: Commit**

```bash
git add front-dev-home/app/utils/semNoiseImage.ts
git commit -m "feat(recipe-compare): canvas SEM-noise PNG helper for Excel images"
```

---

### Task 3: `downloadCompareWorkbook`를 ExcelJS + 이미지 블록으로 재작성

**Files:**
- Modify: `front-dev-home/app/utils/recipeCompare.ts` (`downloadCompareWorkbook` 함수, 현재 254-265행)

`buildCompareWorkbook`과 다른 순수 함수는 건드리지 않는다. `imageBlock`은 optional이므로 기존 호출부(`downloadCompareWorkbook(workbook, filename)`)는 그대로 컴파일된다(Task 5에서 호출 갱신).

- [ ] **Step 1: writer 교체**

`front-dev-home/app/utils/recipeCompare.ts`에서 아래 기존 함수를 찾는다:

```ts
export async function downloadCompareWorkbook(
  workbook: CompareWorkbook,
  filename: string
): Promise<void> {
  const XLSX = await import('xlsx')
  const book = XLSX.utils.book_new()
  for (const sheet of workbook.sheets) {
    const ws = XLSX.utils.aoa_to_sheet(sheet.rows)
    XLSX.utils.book_append_sheet(book, ws, sheet.name.slice(0, 31))
  }
  XLSX.writeFile(book, filename)
}
```

다음으로 교체한다:

```ts
export interface CompareImageBlock {
  sheetName: string // 활성 슬롯의 stage 이름 (예: 'Measure 1')
  parameter: string // 활성 파라미터
  images: (string | null)[] // recipe별 이미지 파일명(없으면 null); 빈 셀 판정용
  pngDataUrl: string // 브라우저에서 미리 렌더한 SEM 노이즈 PNG (data URL)
}

export async function downloadCompareWorkbook(
  workbook: CompareWorkbook,
  filename: string,
  imageBlock?: CompareImageBlock
): Promise<void> {
  const mod = await import('exceljs')
  const ExcelJS = (mod as unknown as { default?: typeof mod }).default ?? mod
  const book = new ExcelJS.Workbook()

  for (const sheet of workbook.sheets) {
    const ws = book.addWorksheet(sheet.name.slice(0, 31))
    for (const row of sheet.rows) {
      ws.addRow(row)
    }

    if (imageBlock && sheet.name === imageBlock.sheetName) {
      // header occupies row 1; insert an image strip directly beneath it:
      // row 2 = label, row 3 = image anchor row, row 4 = spacer.
      ws.spliceRows(2, 0, ['이미지', imageBlock.parameter], [], [])
      ws.getRow(3).height = 115

      const imageId = book.addImage({
        base64: imageBlock.pngDataUrl,
        extension: 'png'
      })
      imageBlock.images.forEach((file, i) => {
        if (!file) return
        // columns: 0='parameter', 1='attr', recipe columns start at index 2 (C).
        // ExcelJS anchors are 0-based; row index 2 === Excel row 3 (the anchor row).
        ws.addImage(imageId, {
          tl: { col: 2 + i, row: 2 },
          ext: { width: 150, height: 150 }
        })
      })
    }
  }

  const buffer = await book.xlsx.writeBuffer()
  const blob = new Blob([buffer], {
    type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
  })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  anchor.click()
  URL.revokeObjectURL(url)
}
```

- [ ] **Step 2: 순수 함수 회귀 테스트**

Run (from `front-dev-home/`): `node --test`
Expected: 기존 `recipeCompare` 테스트(약 65 cases) 전부 PASS (writer는 테스트 대상 아님; `buildCompareWorkbook` 미변경).

- [ ] **Step 3: Typecheck**

Run (from `front-dev-home/`): `npm run typecheck`
Expected: 클린. 만약 `exceljs` 타입 해석 실패 시, `exceljs`가 설치됐는지(Task 1) 확인.

- [ ] **Step 4: Lint**

Run (from `front-dev-home/`): `npx eslint app/utils/recipeCompare.ts`
Expected: exit 0, 출력 없음.

- [ ] **Step 5: Commit**

```bash
git add front-dev-home/app/utils/recipeCompare.ts
git commit -m "feat(recipe-compare): ExcelJS writer with active-slot cell images"
```

---

### Task 4: `RecipeSetBar.vue` — "+recipe 추가" 제거 + back 버튼

**Files:**
- Modify: `front-dev-home/app/components/ebeam/recipeCompare/RecipeSetBar.vue`

- [ ] **Step 1: 파일 전체 교체**

`front-dev-home/app/components/ebeam/recipeCompare/RecipeSetBar.vue`를 아래로 교체한다. 인라인 검색 입력·자동완성·`addQuery`/`suggestions`/`pick`/catalog `useAsyncData`/`add` emit/`toolType`·`fab` props/`useRecipeSearchApi` import을 모두 제거하고, `backRoute` prop과 back 버튼을 추가한다. chip remove(×)와 Excel 버튼은 유지한다.

```vue
<template>
  <div class="dashboard-surface flex flex-col gap-3 rounded-2xl p-4 lg:flex-row lg:items-center">
    <div class="min-w-0 flex-1">
      <div class="mb-1.5 flex items-center gap-2">
        <p class="text-[10px] font-bold tracking-wider text-(--sk-brand) uppercase">
          비교 대상 recipe · {{ selected.length }}
        </p>
        <UButton
          size="xs"
          color="neutral"
          variant="outline"
          icon="i-lucide-arrow-left"
          label="Recipe 검색"
          :to="backRoute"
        />
      </div>
      <div class="flex flex-wrap items-center gap-1.5">
        <span
          v-for="name in selected"
          :key="name"
          class="inline-flex max-w-[240px] items-center gap-1 rounded-[var(--sk-r-chip)] bg-(--sk-brand-soft)/60 py-1 pl-2.5 pr-1 font-mono text-[10.5px] text-(--sk-ink)"
        >
          <span class="truncate">{{ name }}</span>
          <button
            type="button"
            :aria-label="`Remove ${name}`"
            class="rounded-md p-0.5 hover:bg-zinc-300 dark:hover:bg-zinc-600"
            @click="emit('remove', name)"
          >
            <UIcon
              name="i-lucide-x"
              class="h-3 w-3"
            />
          </button>
        </span>
      </div>
    </div>

    <UButton
      class="shrink-0"
      size="sm"
      color="neutral"
      variant="solid"
      icon="i-lucide-download"
      label="Excel 다운로드"
      :disabled="!canExport"
      @click="emit('download')"
    />
  </div>
</template>

<script setup lang="ts">
defineProps<{
  selected: string[]
  backRoute: string
  canExport: boolean
}>()

const emit = defineEmits<{
  remove: [name: string]
  download: []
}>()
</script>
```

- [ ] **Step 2: Typecheck**

Run (from `front-dev-home/`): `npm run typecheck`
Expected: 이 시점에서는 부모(`RecipeCompareView.vue`)가 아직 `:tool-type`/`:fab`/`@add`를 넘기고 `:back-route`를 안 넘기므로 **타입 에러가 날 수 있다**. Task 5에서 부모를 갱신하면 해소된다. 에러가 `RecipeCompareView.vue`의 prop 관련이면 정상 — 다음 단계로 진행한다. `RecipeSetBar.vue` 자체의 에러면 멈추고 수정한다.

- [ ] **Step 3: Lint (이 파일만)**

Run (from `front-dev-home/`): `npx eslint app/components/ebeam/recipeCompare/RecipeSetBar.vue`
Expected: exit 0, 출력 없음.

- [ ] **Step 4: Commit**

```bash
git add front-dev-home/app/components/ebeam/recipeCompare/RecipeSetBar.vue
git commit -m "feat(recipe-compare): drop inline +add, add back-to-search button in set bar"
```

---

### Task 5: `RecipeCompareView.vue` — add 배선 제거 + backRoute + imageBlock 전달

**Files:**
- Modify: `front-dev-home/app/components/ebeam/RecipeCompareView.vue`

- [ ] **Step 1: imports에 `COMPARE_SLOTS`, `imageFilenames`, `renderSemNoisePng` 추가**

기존 import 블록을 찾는다:

```ts
import {
  GROUPING_DEFAULT_THRESHOLD,
  buildCompareWorkbook,
  buildOverlap,
  commonParameters,
  downloadCompareWorkbook
} from '~/utils/recipeCompare'
import { IMAGE_SLOTS, type ImageSlotKey } from '~/utils/recipeView'
```

다음으로 교체한다:

```ts
import {
  COMPARE_SLOTS,
  GROUPING_DEFAULT_THRESHOLD,
  buildCompareWorkbook,
  buildOverlap,
  commonParameters,
  downloadCompareWorkbook,
  imageFilenames
} from '~/utils/recipeCompare'
import { IMAGE_SLOTS, type ImageSlotKey } from '~/utils/recipeView'
import { renderSemNoisePng } from '~/utils/semNoiseImage'
```

- [ ] **Step 2: `useRecipeSelectionSet`에서 `add` 제거**

찾기:

```ts
const { selected, add, remove } = useRecipeSelectionSet(props.toolType, props.fab)
```

교체:

```ts
const { selected, remove } = useRecipeSelectionSet(props.toolType, props.fab)
```

- [ ] **Step 3: set bar 사용부 갱신**

찾기:

```vue
      <EbeamRecipeCompareRecipeSetBar
        :selected="selected"
        :tool-type="toolType"
        :fab="fab"
        :can-export="!!data && selectedParameters.length > 0"
        @remove="remove"
        @add="add"
        @download="downloadExcel"
      />
```

교체:

```vue
      <EbeamRecipeCompareRecipeSetBar
        :selected="selected"
        :back-route="backRoute"
        :can-export="!!data && selectedParameters.length > 0"
        @remove="remove"
        @download="downloadExcel"
      />
```

- [ ] **Step 4: `downloadExcel`가 활성 슬롯+파라미터 imageBlock을 전달하도록 변경**

찾기:

```ts
const downloadExcel = async () => {
  if (!recipes.value.length || !selectedParameters.value.length) return
  try {
    const workbook = buildCompareWorkbook(recipes.value, selectedParameters.value)
    await downloadCompareWorkbook(workbook, `recipe-compare_${props.toolType}_${props.fab}.xlsx`)
  } catch (err) {
    console.error('Excel export failed', err)
  }
}
```

교체:

```ts
const downloadExcel = async () => {
  if (!recipes.value.length || !selectedParameters.value.length) return
  try {
    const workbook = buildCompareWorkbook(recipes.value, selectedParameters.value)
    const slot = COMPARE_SLOTS.find(s => s.key === activeSlot.value)
    const imageBlock = (slot && activeParam.value)
      ? {
          sheetName: slot.stage,
          parameter: activeParam.value,
          images: imageFilenames(recipes.value, activeParam.value, activeSlot.value),
          pngDataUrl: renderSemNoisePng(slot.role)
        }
      : undefined
    await downloadCompareWorkbook(
      workbook,
      `recipe-compare_${props.toolType}_${props.fab}.xlsx`,
      imageBlock
    )
  } catch (err) {
    console.error('Excel export failed', err)
  }
}
```

`slot.role`은 `AmpRole`(`'address' | 'measure'`)로, `renderSemNoisePng`의 `SemRole`과 동일해 그대로 전달 가능하다.

- [ ] **Step 5: Typecheck**

Run (from `front-dev-home/`): `npm run typecheck`
Expected: 클린 (Task 4의 prop 불일치가 해소됨).

- [ ] **Step 6: Lint**

Run (from `front-dev-home/`): `npx eslint app/components/ebeam/RecipeCompareView.vue`
Expected: exit 0, 출력 없음.

- [ ] **Step 7: Commit**

```bash
git add front-dev-home/app/components/ebeam/RecipeCompareView.vue
git commit -m "feat(recipe-compare): wire back-route + pass active-slot image block to Excel"
```

---

### Task 6: E2E 검증 + 문서 상태 갱신

**Files:** 검증 + `docs/superpowers/specs/2026-06-14-recipe-compare-refinements-design.md` (Status 갱신). 서버는 사용자가 PyCharm에서 구동: Flask `:5050` + Nuxt `:3000`.

- [ ] **Step 1: dev 서버에서 ExcelJS 번들 동작 확인**

`http://localhost:3000/ebeam/cd-sem/r3/recipe-search/compare`로 이동(working-set ≥ 2 필요; 없으면 먼저 `recipe-search`에서 2개 이상 체크). 브라우저 콘솔에 ExcelJS 관련 모듈 해석 에러가 없는지 확인한다.

ExcelJS는 `package.json`에 `browser` 엔트리를 제공하므로 Vite가 `await import('exceljs')`를 브라우저용으로 해석해야 한다 — **`nuxt.config`(vite.optimizeDeps / build.transpile)를 선제적으로 수정하지 말 것**. 만약 실제로 node 내장 모듈(`fs`/`stream` 등) 해석 에러가 확인되면, dist 번들 import로 바꾸기보다 먼저 프로젝트 `.d.ts`에 `declare module 'exceljs/dist/exceljs.min.js' { export * from 'exceljs' }` shim을 추가하거나 동적 import에 단일 `@ts-expect-error`를 붙이는 방식을 우선 검토한다. 변경이 필요하면 typecheck/lint/commit을 다시 수행한다.

- [ ] **Step 2: Playwright E2E — set bar UI**

Playwright MCP로 구동(스크린샷은 `.playwright-mcp/screenshots/`):
1. compare 페이지에서 set bar에 "+recipe 추가" 입력이 **없음**을 확인.
2. "비교 대상 recipe" 레이블 옆에 "Recipe 검색" back 버튼이 **있음**을 확인. 스크린샷 `recipe-compare-setbar.png`.
3. back 버튼 클릭 → URL이 `.../recipe-search`로 이동함을 확인.

- [ ] **Step 3: Playwright E2E — Excel 다운로드 + 이미지 검증**

1. compare로 복귀, 활성 슬롯/파라미터가 선택된 상태에서 "Excel 다운로드" 클릭.
2. 다운로드된 `.xlsx`를 ExcelJS로 재파싱해 이미지가 임베드됐는지 검증한다. Playwright MCP의 `browser_run_code_unsafe`(또는 다운로드 경로 확보 후 별도 node 스니펫)로 아래를 실행:

```js
const ExcelJS = require('exceljs')
const wb = new ExcelJS.Workbook()
await wb.xlsx.readFile(DOWNLOADED_XLSX_PATH)
// 활성 슬롯 시트명(예: 'Measure 1') 워크시트의 이미지 개수 > 0 확인
const ws = wb.getWorksheet(ACTIVE_SLOT_STAGE)
const imgs = ws.getImages()
console.log('image count:', imgs.length) // > 0 expected
```

Expected: 활성 슬롯 시트의 이미지 개수 ≥ 1 (해당 파라미터에 이미지가 있는 recipe 수만큼).

> 참고: 브라우저 자동 다운로드 경로 확보가 어려우면, 동일 입력으로 `downloadCompareWorkbook`의 ExcelJS writer 부분만 node 스니펫에서 재현해 `getImages().length > 0`을 확인해도 된다(이미지 임베드 동작 검증이 목적).

- [ ] **Step 4: 회귀 — row-button/단일 흐름 영향 없음**

`recipe-search`에서 단일 recipe row의 열어보기 등 기존 흐름이 그대로 동작하는지 1회 확인(컴포넌트 변경이 compare 한정임을 확인).

- [ ] **Step 5: spec Status 갱신**

`docs/superpowers/specs/2026-06-14-recipe-compare-refinements-design.md`의 `Status:`를 `구현 완료 (Implemented), E2E 검증 완료`로 변경한다.

- [ ] **Step 6: Markdown lint + Commit**

Run (from repo root): `npx markdownlint-cli2 "docs/superpowers/specs/2026-06-14-recipe-compare-refinements-design.md"`
Expected: 0 errors.

```bash
git add docs/superpowers/specs/2026-06-14-recipe-compare-refinements-design.md
git commit -m "docs(recipe-compare): mark refinements implemented + E2E verified"
```

---

## Self-Review

**Spec coverage:**
- D1 (인라인 +add 제거) → Task 4 파일 교체. ✓
- D2 (remove × 유지) → Task 4 템플릿에 chip remove 유지. ✓
- D3 (backRoute prop + back 버튼) → Task 4 (prop+버튼) + Task 5 Step 3 (`:back-route` 전달). ✓
- D4 (xlsx→exceljs, xlsx 미제거) → Task 1 (exceljs 추가) + Task 3 (writer 교체). xlsx 제거 단계 없음. ✓
- D5 (buildCompareWorkbook 순수 유지) → Task 3은 writer만 교체, Task 3 Step 2 `node --test` 회귀. ✓
- D6 (canvas PNG 재현, export당 1장 재사용) → Task 2 헬퍼 + Task 3 `book.addImage` 1회 후 다중 anchor. ✓
- D7 (활성 슬롯+파라미터만) → Task 5 Step 4 imageBlock = activeSlot/activeParam. ✓
- D8 (활성 슬롯 시트 상단 삽입: 레이블 행+이미지 행+빈 행) → Task 3 `spliceRows(2,0,...)` + col 2+i anchor. ✓
- D9 (단위 테스트 없음; typecheck/lint/E2E) → 각 Task의 게이트 + Task 6. ✓

**Placeholder scan:** TBD/TODO 없음. 모든 코드 단계가 전체 내용을 포함. Task 6 Step 1/3의 대안(dist 번들 / node 스니펫)은 구체적 조건부 지시이며 placeholder 아님. ✓

**Type consistency:**
- `CompareImageBlock`(Task 3) ↔ Task 5에서 만드는 객체(`sheetName`,`parameter`,`images`,`pngDataUrl`) 일치. ✓
- `renderSemNoisePng(role: SemRole)`의 `SemRole='address'|'measure'` ↔ `COMPARE_SLOTS[].role: AmpRole='address'|'measure'` 일치. ✓
- `imageFilenames(recipes, parameter, slot: ImageSlotKey)` ↔ `activeSlot: ImageSlotKey` 일치. ✓
- `RecipeSetBar` props(`selected`,`backRoute`,`canExport`) ↔ Task 5 Step 3 바인딩 일치. emits(`remove`,`download`) ↔ 바인딩 일치. ✓
