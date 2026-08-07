# activity Sparkline ECharts 전환 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `/activity`의 "30일 활동" 막대를 손코딩 SVG에서 ECharts로 바꿔 날짜별 툴팁과 기간 줌을 제공합니다.

**Architecture:** ECharts option을 만드는 순수 함수를 `app/utils/activitySparkline.ts`로 분리하고, `Sparkline.vue`는 차트 호스트와 주변 HTML만 담당합니다. 색은 `useChartPalette()`의 역할 토큰에서 읽어 테마를 따라가게 합니다. 차트 인스턴스 생명주기·리사이즈·줌 보존은 기존 `useEchart` 컴포저블이 이미 처리하므로 새로 작성하지 않습니다.

**Tech Stack:** Nuxt 4, Vue 3 `<script setup>`, ECharts 5, `node --test` (테스트 러너), TypeScript.

## Global Constraints

- 작업 디렉터리는 워크트리 `/Users/daeyoung/Codes/skewnono-activity-echarts`입니다. 프런트엔드 명령은 그 아래 `front-dev-home/`에서 실행합니다.
- 워크트리에는 `node_modules`가 없으므로 메인 체크아웃 것을 심볼릭 링크로 연결해 두었습니다 (`front-dev-home/node_modules` → 메인 트리의 같은 경로). `.gitignore`가 덮으므로 커밋에 들어가지 않고, `node --test`와 `eslint`가 워크트리 안에서 그대로 돕니다. 루트 Markdown 린터만 메인 트리 바이너리를 절대경로로 부릅니다: `/Users/daeyoung/Codes/skewnono_v3_nuxt/node_modules/.bin/markdownlint-cli2`.
- Node는 v24이므로 `node --test`가 `.ts` 파일을 그대로 실행합니다. 트랜스파일 단계가 필요 없습니다.
- `formatSparklineDay`의 ko-KR 출력은 이 환경에서 `"07. 01."`(공백과 마침표 포함)로 확인했습니다. 테스트 기대값은 이 값을 씁니다.
- 색 리터럴을 컴포넌트에 직접 쓰지 않습니다. `app/assets/css/main.css:175-177`이 명시하듯 차트 색은 `utils/chartPalette.ts`에서만 옵니다. `--sk-*` CSS 변수는 캔버스에서 읽히지 않으므로 사용 금지입니다.
- `app/utils/activitySparkline.ts`는 `echarts`를 import하지 않습니다. `npm test`가 `node --test`로 직접 실행하는 모듈이기 때문입니다.
- 커밋은 반드시 명시 경로로만 스테이징합니다. `git add -A`, `git add .`, `git commit -a`는 금지입니다 — 같은 작업 트리에 다른 세션이 있습니다.
- 커밋 메시지는 `type(scope): summary` 형식이며 본문에 무엇을 왜 바꿨는지 적고, 끝에 `Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>`를 붙입니다.
- 기존 사용자 문구는 그대로 유지합니다: 빈 상태는 `30일간 활동이 없습니다.`, 합계는 `합계 {N}`.

---

### Task 1: option 빌더 순수 함수

`Sparkline.vue`가 쓸 ECharts option과 라벨 계산을 `echarts` 의존 없는 모듈로 만듭니다. 이 태스크만으로 `npm test`가 통과해야 합니다.

**Files:**

- Create: `front-dev-home/app/utils/activitySparkline.ts`
- Test: `front-dev-home/app/utils/activitySparkline.test.ts`

**Interfaces:**

- Consumes: `DailyCount` (`front-dev-home/app/composables/useActivityApi.ts:8` — `{ date: string, count: number }`)
- Produces:
  - `formatSparklineDay(iso: string): string`
  - `sparklineTotal(series: DailyCount[]): number`
  - `sparklineHasData(series: DailyCount[]): boolean`
  - `formatSparklineTooltip(iso: string, count: number): string`
  - `buildSparklineOption(series: DailyCount[], barColor: string, zoomable: boolean): EChartsOption`

- [ ] **Step 1: 실패하는 테스트를 작성한다**

`front-dev-home/app/utils/activitySparkline.test.ts`:

```ts
import assert from 'node:assert/strict'
import test from 'node:test'
import {
  buildSparklineOption,
  formatSparklineDay,
  formatSparklineTooltip,
  sparklineHasData,
  sparklineTotal
} from './activitySparkline.ts'

const SERIES = [
  { date: '2026-07-01', count: 3 },
  { date: '2026-07-02', count: 0 },
  { date: '2026-07-03', count: 7 }
]

test('formats a day as MM.DD and passes through an unparseable date', () => {
  assert.equal(formatSparklineDay('2026-07-01'), '07. 01.')
  assert.equal(formatSparklineDay('not-a-date'), 'not-a-date')
})

test('totals the counts and reports whether any activity exists', () => {
  assert.equal(sparklineTotal(SERIES), 10)
  assert.equal(sparklineHasData(SERIES), true)
  assert.equal(sparklineTotal([]), 0)
  assert.equal(sparklineHasData([]), false)
  assert.equal(sparklineHasData([{ date: '2026-07-01', count: 0 }]), false)
})

test('maps every day to one bar, in order', () => {
  const option = buildSparklineOption(SERIES, '#123456', false)
  const series = option.series as Array<{ data: number[], type: string }>
  assert.equal(series.length, 1)
  assert.equal(series[0].type, 'bar')
  assert.deepEqual(series[0].data, [3, 0, 7])

  const xAxis = option.xAxis as { data: string[] }
  assert.deepEqual(xAxis.data, ['2026-07-01', '2026-07-02', '2026-07-03'])
})

test('paints the bars with the colour it was handed', () => {
  const option = buildSparklineOption(SERIES, '#123456', false)
  const series = option.series as Array<{ itemStyle: { color: string } }>
  assert.equal(series[0].itemStyle.color, '#123456')
})

test('adds dataZoom only when zoomable', () => {
  assert.equal(buildSparklineOption(SERIES, '#123456', false).dataZoom, undefined)

  const zoomed = buildSparklineOption(SERIES, '#123456', true)
  const dataZoom = zoomed.dataZoom as Array<{ type: string }>
  assert.deepEqual(dataZoom.map(z => z.type), ['inside', 'slider'])
})

test('reserves bottom room for the slider only when zoomable', () => {
  const flat = buildSparklineOption(SERIES, '#123456', false).grid as { bottom: number }
  const zoomed = buildSparklineOption(SERIES, '#123456', true).grid as { bottom: number }
  assert.equal(flat.bottom, 2)
  assert.ok(zoomed.bottom > flat.bottom, 'the slider needs bottom padding')
})

test('survives an empty series', () => {
  const option = buildSparklineOption([], '#123456', false)
  const series = option.series as Array<{ data: number[] }>
  assert.deepEqual(series[0].data, [])
})

test('renders the tooltip as date and count', () => {
  assert.equal(formatSparklineTooltip('2026-07-03', 7), '07. 03. · 7건')
})
```

`formatSparklineDay`의 기대값에 주의합니다. `toLocaleDateString('ko-KR', { month: '2-digit', day: '2-digit' })`는 Node에서 `07. 01.`을 돌려줍니다(공백과 마침표 포함). Step 2에서 실제 출력을 확인하고 기대값이 다르면 테스트를 실제 출력에 맞춥니다 — 이 포맷은 기존 컴포넌트가 이미 쓰던 것이므로 화면 표기를 바꾸지 않는 것이 목적입니다.

- [ ] **Step 2: 테스트가 실패하는지 확인한다**

```bash
cd /Users/daeyoung/Codes/skewnono-activity-echarts/front-dev-home
node --test "app/utils/activitySparkline.test.ts" 2>&1 | tail -20
```

기대: `Cannot find module './activitySparkline.ts'`로 실패합니다.

- [ ] **Step 3: 최소 구현을 작성한다**

`front-dev-home/app/utils/activitySparkline.ts`:

```ts
import type { EChartsOption } from 'echarts'
import type { DailyCount } from '~/composables/useActivityApi'

/**
 * The activity sparkline's ECharts option, built without importing echarts.
 *
 * echarts is a runtime dependency of the component, not of this module: the
 * option is a plain object literal and `npm test` runs this file directly
 * under `node --test`, where pulling in echarts would cost a browser-only
 * dependency for no gain. Keeping it out is what makes the bar mapping,
 * the zoom toggle and the tooltip text testable as pure functions.
 */

/** 'MM.DD' as ko-KR renders it, or the raw string when it will not parse. */
export const formatSparklineDay = (iso: string): string => {
  const date = new Date(`${iso}T00:00:00Z`)
  if (Number.isNaN(date.getTime())) return iso
  return date.toLocaleDateString('ko-KR', { month: '2-digit', day: '2-digit' })
}

export const sparklineTotal = (series: DailyCount[]): number =>
  series.reduce((sum, d) => sum + d.count, 0)

/**
 * Whether the chart is worth drawing at all. A 30-day window of zeroes is a
 * real answer ("no activity"), and the component renders text for it rather
 * than an empty canvas — which also means no ECharts instance is created for
 * the inactive users in the user table.
 */
export const sparklineHasData = (series: DailyCount[]): boolean =>
  series.some(d => d.count > 0)

export const formatSparklineTooltip = (iso: string, count: number): string =>
  `${formatSparklineDay(iso)} · ${count}건`

export const buildSparklineOption = (
  series: DailyCount[],
  barColor: string,
  zoomable: boolean
): EChartsOption => ({
  // No axis furniture: the host is 64px tall and the dates/total live in HTML
  // around the canvas, so every pixel here belongs to the bars.
  grid: {
    left: 0,
    right: 0,
    top: 2,
    bottom: zoomable ? 20 : 2,
    containLabel: false
  },
  xAxis: {
    type: 'category',
    data: series.map(d => d.date),
    axisLine: { show: false },
    axisTick: { show: false },
    axisLabel: { show: false },
    splitLine: { show: false }
  },
  yAxis: {
    type: 'value',
    min: 0,
    axisLine: { show: false },
    axisTick: { show: false },
    axisLabel: { show: false },
    splitLine: { show: false }
  },
  tooltip: {
    trigger: 'axis',
    axisPointer: { type: 'shadow' },
    formatter: (params) => {
      const first = Array.isArray(params) ? params[0] : params
      if (!first) return ''
      return formatSparklineTooltip(String(first.axisValue ?? ''), Number(first.data ?? 0))
    }
  },
  ...(zoomable
    ? { dataZoom: [{ type: 'inside' as const }, { type: 'slider' as const, height: 14, bottom: 0 }] }
    : {}),
  series: [{
    type: 'bar',
    data: series.map(d => d.count),
    barCategoryGap: '20%',
    itemStyle: { color: barColor, borderRadius: [1.5, 1.5, 0, 0] }
  }]
})
```

- [ ] **Step 4: 테스트가 통과하는지 확인한다**

```bash
cd /Users/daeyoung/Codes/skewnono-activity-echarts/front-dev-home
node --test "app/utils/activitySparkline.test.ts" 2>&1 | tail -20
```

기대: 8개 테스트 모두 pass.

- [ ] **Step 5: 커밋한다**

```bash
cd /Users/daeyoung/Codes/skewnono-activity-echarts
git add front-dev-home/app/utils/activitySparkline.ts front-dev-home/app/utils/activitySparkline.test.ts
git commit -m "feat(activity): sparkline ECharts option을 순수 함수로 분리

Sparkline.vue가 쓸 option/라벨 계산을 echarts 의존 없는 모듈로 옮긴다.
npm test는 node --test로 이 파일을 직접 실행하므로 echarts를 import하면
브라우저 전용 의존성이 테스트에 끌려온다. 분리해두면 막대 매핑, 줌 토글,
툴팁 문구를 순수 함수로 검증할 수 있다.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Sparkline.vue를 ECharts 호스트로 재작성

SVG를 걷어내고 차트 호스트를 놓습니다. 합계/양끝 날짜 HTML은 유지하고, 기존 컴포넌트 테스트는 앵커만 바꿔 살립니다.

**Files:**

- Modify: `front-dev-home/app/components/activity/Sparkline.vue` (전면 재작성, 현재 127줄)
- Modify: `front-dev-home/app/components/activity/Sparkline.test.ts:41` (`<svg>` 앵커 교체)

**Interfaces:**

- Consumes: Task 1의 `buildSparklineOption`, `formatSparklineDay`, `sparklineHasData`, `sparklineTotal`
- Consumes: `useEchart(elRef, optionRef, options)` (`app/composables/useEchart.ts:93`, Nuxt 자동 import). `options.disableDownload: true`로 다운로드 버튼을 끕니다 — 64px 호스트에 오버레이 버튼이 막대를 가립니다.
- Consumes: `useChartPalette()` (`app/composables/useChartPalette.ts:27`, 자동 import). `ComputedRef<ChartPalette>`이므로 `sk.value.series` / `sk.value.brand`로 읽습니다.
- Produces: props `{ series: DailyCount[], tone?: 'series' | 'brand', zoomable?: boolean }`. `color` prop은 사라집니다.

- [ ] **Step 1: 컴포넌트를 재작성한다**

`front-dev-home/app/components/activity/Sparkline.vue` 전체를 아래로 교체합니다:

```vue
<template>
  <div>
    <div
      v-if="hasData"
      class="flex justify-end text-[10px] text-(--sk-ink-muted) mb-1 tabular-nums"
    >
      <span>{{ totalLabel }}</span>
    </div>
    <div
      v-if="hasData"
      ref="chartEl"
      data-testid="sparkline-canvas"
      class="w-full"
      :class="zoomable ? 'h-24' : 'h-16'"
    />
    <div
      v-else
      class="sk-body h-16 flex items-center"
    >
      30일간 활동이 없습니다.
    </div>
    <div
      v-if="hasData && !zoomable"
      class="flex justify-between text-[10px] text-(--sk-ink-muted) mt-1 tabular-nums"
    >
      <span>{{ firstLabel }}</span>
      <span>{{ lastLabel }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { DailyCount } from '~/composables/useActivityApi'
import {
  buildSparklineOption,
  formatSparklineDay,
  sparklineHasData,
  sparklineTotal
} from '~/utils/activitySparkline'

const props = withDefaults(
  defineProps<{
    series: DailyCount[]
    // Which palette role paints the bars. The page uses two so the reader can
    // tell "my activity" from "the user I expanded" at a glance; both follow
    // the active ECharts theme rather than a hardcoded hex.
    tone?: 'series' | 'brand'
    // The zoom slider needs ~20px, which is a third of the flat host. Only the
    // standalone card can spare it — inside the user table the sparkline is a
    // third of a row and the bars would vanish under the slider.
    zoomable?: boolean
  }>(),
  { tone: 'series', zoomable: false }
)

const chartEl = ref<HTMLDivElement | null>(null)
const sk = useChartPalette()

const hasData = computed(() => sparklineHasData(props.series))
const barColor = computed(() => (props.tone === 'brand' ? sk.value.brand : sk.value.series))
const option = computed(() => buildSparklineOption(props.series, barColor.value, props.zoomable))

// The host sits inside v-if, so on an empty series it never mounts and no
// chart is created; useEchart's elRef watch initialises against the node when
// it does appear.
useEchart(chartEl, option, { disableDownload: true })

const totalLabel = computed(() => `합계 ${sparklineTotal(props.series)}`)
const firstLabel = computed(() =>
  props.series.length ? formatSparklineDay(props.series[0]!.date) : ''
)
const lastLabel = computed(() =>
  props.series.length ? formatSparklineDay(props.series[props.series.length - 1]!.date) : ''
)
</script>
```

- [ ] **Step 2: 기존 컴포넌트 테스트의 앵커를 교체한다**

`Sparkline.test.ts`는 SFC의 **템플릿만** 컴파일해 가짜 `data`로 SSR 렌더합니다. 스크립트를 실행하지 않으므로 ECharts도 Nuxt 런타임도 필요 없고, 전환 후에도 유효합니다. `data`에서 SVG 전용 키를 빼고 `zoomable`을 넣은 뒤, `<svg>`를 찾던 자리를 호스트 div로 바꿉니다.

`front-dev-home/app/components/activity/Sparkline.test.ts`의 `renderToString` 호출과 그 아래 단언부를 아래로 교체합니다:

```ts
  const html = await renderToString(createSSRApp({
    data: () => ({
      hasData: true,
      zoomable: false,
      firstLabel: '07. 01.',
      totalLabel: '합계 10',
      lastLabel: '07. 30.'
    }),
    render
  }))

  const totalIndex = html.indexOf('합계 10')
  const hostIndex = html.indexOf('data-testid="sparkline-canvas"')
  const firstDateIndex = html.indexOf('07. 01.')
  const lastDateIndex = html.indexOf('07. 30.')

  assert.ok(hostIndex > -1, 'the chart host must render')
  assert.ok(totalIndex < hostIndex, 'the total must render above the chart')
  assert.ok(
    hostIndex < firstDateIndex && firstDateIndex < lastDateIndex,
    'only the start and end dates must render below the chart'
  )
```

테스트 이름도 실제 내용에 맞춥니다: `'renders the total above the chart and only dates below it'`.

- [ ] **Step 3: 줌일 때 날짜 줄이 사라지는지 검증하는 테스트를 추가한다**

같은 파일 끝에 추가합니다. `compileTemplate` 부분이 두 테스트에 필요하므로 헬퍼로 뽑습니다:

```ts
const renderSparkline = async (data: Record<string, unknown>) => {
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
  return renderToString(createSSRApp({ data: () => data, render }))
}

test('drops the date row when the zoom slider is shown', async () => {
  const html = await renderSparkline({
    hasData: true,
    zoomable: true,
    firstLabel: '07. 01.',
    totalLabel: '합계 10',
    lastLabel: '07. 30.'
  })

  assert.ok(html.includes('data-testid="sparkline-canvas"'), 'the chart host must render')
  assert.equal(html.includes('07. 01.'), false, 'the slider replaces the date row')
})

test('renders the empty state instead of a chart host', async () => {
  const html = await renderSparkline({
    hasData: false,
    zoomable: false,
    firstLabel: '',
    totalLabel: '',
    lastLabel: ''
  })

  assert.ok(html.includes('30일간 활동이 없습니다.'))
  assert.equal(
    html.includes('data-testid="sparkline-canvas"'),
    false,
    'no chart host means no ECharts instance for inactive users'
  )
})
```

첫 번째 테스트도 이 헬퍼를 쓰도록 고쳐 중복을 없앱니다.

- [ ] **Step 4: 테스트를 실행한다**

```bash
cd /Users/daeyoung/Codes/skewnono-activity-echarts/front-dev-home
node --test "app/components/activity/Sparkline.test.ts" 2>&1 | tail -25
```

기대: 3개 테스트 모두 pass.

- [ ] **Step 5: 커밋한다**

```bash
cd /Users/daeyoung/Codes/skewnono-activity-echarts
git add front-dev-home/app/components/activity/Sparkline.vue front-dev-home/app/components/activity/Sparkline.test.ts
git commit -m "feat(activity): Sparkline을 ECharts 호스트로 재작성

손코딩 SVG(rect 30개 + useId gradient)를 걷어내고 useEchart 호스트를 놓는다.
툴팁과 기간 줌이 컴포저블에서 그대로 따라오고, 하드코딩 hex GRADIENT_MAP은
useChartPalette의 series/brand 역할 토큰으로 대체된다.

- color prop -> tone prop ('series' | 'brand')
- zoomable prop 신설: 슬라이더가 20px를 먹으므로 단독 카드에서만 사용
- 빈 시리즈면 호스트를 v-if로 걸러 차트 인스턴스를 만들지 않음
- disableDownload: 64px 호스트에서 다운로드 버튼이 막대를 가림
- 컴포넌트 테스트는 svg 앵커만 호스트 div로 교체해 유지하고, 줌/빈 상태
  케이스를 추가

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: 호출부 교체와 전체 검증

`activity.vue`의 두 소비처를 새 prop으로 바꾸고 저장소 전체 검증을 돌립니다.

**Files:**

- Modify: `front-dev-home/app/pages/activity.vue:128-131` (메인 "30일 활동" 카드)
- Modify: `front-dev-home/app/pages/activity.vue:578-581` (사용자 상세 확장 행)

**Interfaces:**

- Consumes: Task 2의 props `{ series, tone?, zoomable? }`

- [ ] **Step 1: 메인 카드 호출부를 바꾼다**

`front-dev-home/app/pages/activity.vue`에서:

```vue
        <ActivitySparkline
          :series="me.daily"
          color="from-sky-400 to-violet-500"
        />
```

를 아래로 교체합니다:

```vue
        <ActivitySparkline
          :series="me.daily"
          zoomable
        />
```

`tone`은 기본값 `'series'`이므로 적지 않습니다.

- [ ] **Step 2: 확장 행 호출부를 바꾼다**

같은 파일에서:

```vue
                        <ActivitySparkline
                          :series="userDetail.daily"
                          color="from-rose-400 to-amber-500"
                        />
```

를 아래로 교체합니다:

```vue
                        <ActivitySparkline
                          :series="userDetail.daily"
                          tone="brand"
                        />
```

- [ ] **Step 3: `color` prop이 남아있지 않은지 확인한다**

```bash
cd /Users/daeyoung/Codes/skewnono-activity-echarts/front-dev-home
grep -rn "ActivitySparkline" -A 4 app/ | grep -n "color=" || echo "clean"
```

기대: `clean`

- [ ] **Step 4: 전체 검증을 돌린다**

```bash
cd /Users/daeyoung/Codes/skewnono-activity-echarts/front-dev-home
npm test 2>&1 | tail -15
npm run lint 2>&1 | tail -20
```

기대: 테스트 전부 pass, eslint 0 error.

`npm run typecheck`는 `nuxt typecheck`이고 `.nuxt/` 준비 산출물이 필요합니다. 워크트리에서 실패하면 병합 후 메인 체크아웃에서 돌립니다 — Task 4 Step 1에 그 단계가 있습니다.

- [ ] **Step 5: 커밋한다**

```bash
cd /Users/daeyoung/Codes/skewnono-activity-echarts
git add front-dev-home/app/pages/activity.vue
git commit -m "feat(activity): sparkline 호출부를 tone/zoomable prop으로 교체

메인 30일 활동 카드는 zoomable(툴팁+기간 줌), 사용자 상세 확장 행은
tone=brand(툴팁만)로 간다. Tailwind 클래스 문자열을 넘기던 color prop은
사라졌다.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: 병합과 브라우저 확인

**Files:** 없음 (검증·병합만)

- [ ] **Step 1: 메인 체크아웃에서 타입 체크를 돌린다**

병합 전에 워크트리 브랜치를 메인으로 가져와야 `node_modules`가 있는 트리에서 확인할 수 있습니다. 먼저 병합합니다:

```bash
cd /Users/daeyoung/Codes/skewnono_v3_nuxt
git merge --ff-only work/activity-echarts
```

`--ff-only`가 실패하면 그동안 `main`이 움직인 것입니다. 그때는 워크트리에서 `git rebase main` 후 다시 시도합니다.

```bash
cd /Users/daeyoung/Codes/skewnono_v3_nuxt/front-dev-home
npm run typecheck 2>&1 | tail -20
npm test 2>&1 | tail -10
npm run lint 2>&1 | tail -10
```

기대: 셋 다 통과. 실패하면 워크트리가 아니라 메인 트리에서 고치고 별도 커밋합니다.

- [ ] **Step 2: 앱을 띄워 브라우저로 확인한다**

`verify` 스킬의 절차를 따릅니다. 최소한:

```bash
cd /Users/daeyoung/Codes/skewnono_v3_nuxt && .venv/bin/python index.py
cd /Users/daeyoung/Codes/skewnono_v3_nuxt/front-dev-home && npm run dev
```

`http://localhost:3000/activity`에서 확인할 것:

1. "30일 활동" 카드의 막대에 hover하면 `MM. DD. · N건` 툴팁이 뜬다
2. 같은 카드 아래 슬라이더를 드래그하면 기간이 좁혀지고 막대가 다시 그려진다
3. 사용자 표에서 행을 펼치면 확장 행 sparkline이 **다른 색**으로 뜨고 슬라이더가 **없다**
4. 활동이 없는 사용자를 펼치면 `30일간 활동이 없습니다.` 문구가 뜬다
5. 다크 모드로 전환해도 막대가 보인다
6. 설정에서 ECharts 테마를 바꾸면 두 sparkline의 색이 함께 바뀐다

스크린샷은 `.playwright-mcp/screenshots/` 아래에 저장합니다.

- [ ] **Step 3: 푸시하고 워크트리를 정리한다**

```bash
cd /Users/daeyoung/Codes/skewnono_v3_nuxt
git push
git worktree remove ../skewnono-activity-echarts
git branch -d work/activity-echarts
git worktree list
```

기대: `git worktree list`에 `skewnono-activity-echarts`가 없을 것. (다른 세션의 `skewnono-eqp-view`, `skewnono-multi-fab-b`는 그대로 두십시오.)

---

## Self-Review

**Spec coverage**

| Spec 항목 | 담당 태스크 |
| --- | --- |
| option 빌더를 `utils/activitySparkline.ts`로 분리 | Task 1 |
| `echarts` import 금지 | Task 1 Step 3 (주석에 이유 명시) |
| `color` → `tone` prop 교체 | Task 2 Step 1, Task 3 Step 1-2 |
| 하드코딩 hex 제거, `chartPalette` 역할 토큰 사용 | Task 2 Step 1 (`useChartPalette`) |
| 그라디언트 → 단색 | Task 1 Step 3 (`itemStyle.color`) |
| 축 furniture 끄기, 합계/날짜는 HTML 유지 | Task 1 Step 3 (grid/axis), Task 2 Step 1 (템플릿) |
| 줌은 메인 카드만, 높이 `h-16` → `h-24` | Task 2 Step 1, Task 3 Step 1 |
| 빈 상태에서 차트 미생성 | Task 2 Step 1 (`v-if`), Step 3 (테스트) |
| 기존 컴포넌트 테스트 개작 유지 | Task 2 Step 2 |
| 신규 util 테스트 | Task 1 Step 1 |
| 검증(test/typecheck/lint/lint:md/브라우저) | Task 3 Step 4, Task 4 Step 1-2 |
| `FeatureBarList` 미변경 | 어느 태스크에도 없음 (의도적) |

**Placeholder scan:** 없음. 모든 코드 단계에 실제 코드가 들어 있습니다.

**Type consistency:** `buildSparklineOption(series, barColor, zoomable)`의 인자 순서와 이름이 Task 1 정의와 Task 2 호출부에서 일치합니다. `sparklineHasData`/`sparklineTotal`/`formatSparklineDay`도 동일합니다. `tone` 값은 `'series' | 'brand'`로 Task 2 정의와 Task 3 사용처가 일치합니다.

**알려진 위험 두 가지**

1. `formatSparklineDay`의 ko-KR 출력이 `07. 01.`인지 `07.01`인지는 Node ICU 빌드에 달려 있습니다. Task 1 Step 2에서 실제 출력을 먼저 확인하고 테스트 기대값을 맞춥니다. 구현은 기존 컴포넌트에서 그대로 옮긴 것이므로 화면 표기는 바뀌지 않습니다.
2. `tooltip.formatter`의 `params` 타입은 ECharts의 `TopLevelFormatterParams`(단일 또는 배열)입니다. `Array.isArray`로 좁힌 뒤 `axisValue`/`data`를 읽습니다. `npm run typecheck`가 여기서 걸리면 `first`에 `as { axisValue?: unknown, data?: unknown }` 단언을 붙입니다 — `any`는 쓰지 않습니다(eslint가 막습니다).
