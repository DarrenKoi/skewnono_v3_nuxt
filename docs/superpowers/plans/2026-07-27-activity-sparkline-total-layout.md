# Activity Sparkline 합계 레이아웃 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `ActivitySparkline`의 합계를 날짜 축 행에서 분리하여 차트 위에 표시합니다.

**Architecture:** 기존 `ActivitySparkline`의 prop, 계산식, 호출 위치는 유지하고
template 배치만 변경합니다. 실제 SFC template을 컴파일하고 SSR로 렌더링하는
회귀 테스트를 추가하여 합계와 날짜의 상대 위치를 검증합니다.

**Tech Stack:** Nuxt 4, Vue 3, TypeScript, Node test runner,
`@vue/compiler-sfc`, `@vue/server-renderer`

## Global Constraints

- `series`와 `color` prop을 변경하지 않습니다.
- 활동 API와 `activity.vue`의 두 호출 위치를 변경하지 않습니다.
- 합계는 차트 위의 독립된 우측 정렬 행에 표시합니다.
- 차트 아래에는 시작 날짜와 종료 날짜만 표시합니다.
- 현재 혼합 worktree의 다른 변경을 수정하거나 stage하지 않습니다.
- commit과 push는 이 구현 범위에 포함하지 않습니다.

---

### Task 1: Activity Sparkline 합계와 날짜 행 분리

**Files:**

- Create: `front-dev-home/app/components/activity/Sparkline.test.ts`
- Modify: `front-dev-home/app/components/activity/Sparkline.vue:2-51`

**Interfaces:**

- Consumes: `ActivitySparkline`의 기존 `series: DailyCount[]`,
  `color?: string` prop과 `totalLabel`, `firstLabel`, `lastLabel` 계산값
- Produces: 합계가 SVG보다 앞에, 두 날짜가 SVG보다 뒤에 렌더링되는 template
  계약

- [x] **Step 1: 실제 SFC template을 렌더링하는 실패 테스트 작성**

```ts
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import { fileURLToPath } from 'node:url'
import { compileTemplate, parse } from '@vue/compiler-sfc'
import { renderToString } from '@vue/server-renderer'
import { createSSRApp } from 'vue'
import * as Vue from 'vue'

test('renders the total above the bars and only dates below them', async () => {
  const filename = fileURLToPath(new URL('./Sparkline.vue', import.meta.url))
  const { descriptor } = parse(readFileSync(filename, 'utf8'), { filename })
  assert.ok(descriptor.template)

  const compiled = compileTemplate({
    source: descriptor.template.content,
    filename,
    id: 'activity-sparkline-test',
    compilerOptions: { mode: 'function' }
  })
  assert.deepEqual(compiled.errors, [])

  const render = new Function('Vue', compiled.code)(Vue)
  const html = await renderToString(createSSRApp({
    data: () => ({
      hasData: true,
      width: 300,
      height: 60,
      gradientId: 'test-gradient',
      gradientStops: { start: '#38bdf8', end: '#8b5cf6' },
      bars: [{ x: 4, y: 4, h: 52 }],
      barWidth: 8,
      firstLabel: '07.01',
      totalLabel: '합계 10',
      lastLabel: '07.30'
    }),
    render
  }))

  const totalIndex = html.indexOf('합계 10')
  const svgStartIndex = html.indexOf('<svg')
  const svgEndIndex = html.indexOf('</svg>')
  const firstDateIndex = html.indexOf('07.01')
  const lastDateIndex = html.indexOf('07.30')

  assert.ok(totalIndex < svgStartIndex, 'the total must render above the bars')
  assert.ok(
    svgEndIndex < firstDateIndex && firstDateIndex < lastDateIndex,
    'only the start and end dates must render below the bars'
  )
})
```

- [x] **Step 2: focused test가 현재 layout에서 실패하는지 확인**

Run:

```bash
cd front-dev-home
PATH=/Users/daeyoung/.nvm/versions/node/v24.13.0/bin:$PATH \
  node --test app/components/activity/Sparkline.test.ts
```

Expected: `the total must render above the bars` assertion이 실패합니다.

- [x] **Step 3: 합계를 차트 위의 독립 행으로 이동**

`Sparkline.vue`의 root 안에서 SVG보다 앞에 다음 행을 추가합니다.

```vue
<div
  v-if="hasData"
  class="flex justify-end text-[10px] text-(--sk-ink-muted) mb-1 tabular-nums"
>
  <span>{{ totalLabel }}</span>
</div>
```

기존 하단 행에서는 가운데 합계 span을 제거하고 날짜 두 개만 유지합니다.

```vue
<div
  v-if="hasData"
  class="flex justify-between text-[10px] text-(--sk-ink-muted) mt-1 tabular-nums"
>
  <span>{{ firstLabel }}</span>
  <span>{{ lastLabel }}</span>
</div>
```

- [x] **Step 4: focused test가 통과하는지 확인**

Run:

```bash
cd front-dev-home
PATH=/Users/daeyoung/.nvm/versions/node/v24.13.0/bin:$PATH \
  node --test app/components/activity/Sparkline.test.ts
```

Expected: 1 test passes, 0 tests fail.

- [x] **Step 5: frontend 전체 검증**

Run:

```bash
cd front-dev-home
PATH=/Users/daeyoung/.nvm/versions/node/v24.13.0/bin:$PATH npm test
PATH=/Users/daeyoung/.nvm/versions/node/v24.13.0/bin:$PATH npm run lint
PATH=/Users/daeyoung/.nvm/versions/node/v24.13.0/bin:$PATH npm run typecheck
cd ..
git diff --check
```

Expected: 모든 명령이 exit code 0으로 종료합니다. 기존 baseline 오류가 나타나면
이번 변경 파일과 분리하여 정확한 위치를 보고합니다.
