# Chart Image Download + TAT-tab Chart Colors Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a hover-reveal "download chart as PNG" button to every chart in the app via the one shared `useEchart` composable, and make the two `recipe-status?tab=tat` charts share one layout while reading as distinct colors.

**Architecture:** Two pure, unit-tested helpers (a filename builder and a per-theme background-color lookup) feed one integration change in `useEchart.ts`, which appends a styled overlay button to each chart host `<div>` and exports via ECharts `getDataURL`. A second, independent change in `RecipeTatView.vue` unifies the two charts' grid insets and assigns them `palette[0]` / `palette[1]`.

**Tech Stack:** Nuxt 4 SPA (`ssr: false`), Vue 3 `<script setup>`, ECharts 6.1.0 (raw `echarts.init`), Node built-in test runner (`node --test`, native TS).

## Global Constraints

- Test runner: `node --test "app/**/*.test.ts"` (via `npm test`); run a single file with `node --test app/utils/<file>.test.ts`. Tests are pure TS with `node:test` + `node:assert/strict` — no DOM, no Nuxt runtime, no `~/` runtime imports (type-only `~/` imports are fine, they get stripped).
- All work is under `front-dev-home/`. Run every command from `front-dev-home/`.
- Charts render on a **transparent** canvas by theme design; exported PNGs must bake in a solid theme background so they are not transparent.
- `useEchart` must keep returning `void` and keep its existing call signature working — all 26 existing call sites pass only `(elRef, optionRef)` or `(elRef, optionRef, { onClick })` and must not break.
- Colors must stay theme-aware: read literals from `useEchartsTheme().palette` / the theme metadata, never hardcode a hex in a chart option.
- After editing any Markdown, run `npm run lint:md`. Commit only what each task lists.
- Do not commit/push beyond each task's listed `git add` unless the human asks; work on `main`.

---

## File Structure

- `app/utils/chartExport.ts` (new) — pure filename helpers. One responsibility: turn a name/title/date into a safe `.png` filename.
- `app/utils/chartExport.test.ts` (new) — tests for the above.
- `app/utils/echartsThemes.ts` (modify) — add `getEchartThemeBackground(name)` + backing map, next to the existing `getEchartThemePalette`.
- `app/utils/echartsThemes.test.ts` (new) — tests for `getEchartThemeBackground`.
- `app/composables/useEchart.ts` (modify) — append/teardown the overlay download button; new `exportName` / `disableDownload` options; inject a singleton stylesheet.
- `app/components/ebeam/RecipeTatView.vue` (modify) — unify the two charts' `grid`, color bar = `palette[0]` and trend = `palette[1]`, pass `exportName`.

---

### Task 1: Pure chart-export filename helper

**Files:**

- Create: `app/utils/chartExport.ts`
- Test: `app/utils/chartExport.test.ts`

**Interfaces:**

- Consumes: nothing.
- Produces:
  - `slugifyChartName(raw: string): string`
  - `formatDateStamp(date: Date): string` → `YYYY-MM-DD`
  - `chartExportFilename(exportName: string | undefined, titleText: string | undefined, date: Date): string` → e.g. `top-recipe-by-tat-2026-07-16.png`

- [ ] **Step 1: Write the failing test**

Create `app/utils/chartExport.test.ts`:

```ts
// front-dev-home/app/utils/chartExport.test.ts
// Pure-logic tests for chart-image export filename building.
// Run: cd front-dev-home && node --test app/utils/chartExport.test.ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { slugifyChartName, formatDateStamp, chartExportFilename } from './chartExport.ts'

const D = new Date(2026, 6, 6) // 2026-07-06 (month is 0-indexed)

test('slugifyChartName lowercases and hyphenates', () => {
  assert.equal(slugifyChartName('Top 20 recipes by total TAT'), 'top-20-recipes-by-total-tat')
})

test('slugifyChartName collapses runs and trims edges', () => {
  assert.equal(slugifyChartName('  Daily / TAT  Trend!! '), 'daily-tat-trend')
})

test('slugifyChartName falls back to "chart" when empty after cleaning', () => {
  assert.equal(slugifyChartName('!!!'), 'chart')
})

test('formatDateStamp zero-pads month and day', () => {
  assert.equal(formatDateStamp(D), '2026-07-06')
})

test('chartExportFilename prefers exportName over title', () => {
  assert.equal(chartExportFilename('daily-tat-trend', 'Some Title', D), 'daily-tat-trend-2026-07-06.png')
})

test('chartExportFilename falls back to title text when no exportName', () => {
  assert.equal(chartExportFilename(undefined, 'Top 20 recipes by total TAT', D), 'top-20-recipes-by-total-tat-2026-07-06.png')
})

test('chartExportFilename falls back to "chart" when neither is given', () => {
  assert.equal(chartExportFilename(undefined, undefined, D), 'chart-2026-07-06.png')
})

test('chartExportFilename ignores blank/whitespace inputs', () => {
  assert.equal(chartExportFilename('   ', '   ', D), 'chart-2026-07-06.png')
})
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd front-dev-home && node --test app/utils/chartExport.test.ts`
Expected: FAIL — cannot find module `./chartExport.ts`.

- [ ] **Step 3: Write the minimal implementation**

Create `app/utils/chartExport.ts`:

```ts
// front-dev-home/app/utils/chartExport.ts
// Pure helpers for exporting a chart as a downloadable PNG. Kept free of DOM /
// Nuxt / ECharts imports so the filename logic is unit-testable in isolation;
// the DOM wiring that consumes these lives in composables/useEchart.ts.

// Lowercase, replace any run of non-alphanumerics with a single hyphen, and
// trim leading/trailing hyphens. Empty result falls back to 'chart'.
export const slugifyChartName = (raw: string): string => {
  const slug = raw
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
  return slug || 'chart'
}

// Local calendar date as YYYY-MM-DD (month is 0-indexed on Date).
export const formatDateStamp = (date: Date): string => {
  const y = date.getFullYear()
  const m = String(date.getMonth() + 1).padStart(2, '0')
  const d = String(date.getDate()).padStart(2, '0')
  return `${y}-${m}-${d}`
}

// Preferred filename base is the caller-supplied exportName, else the chart's
// own title text, else the literal 'chart'. Blank/whitespace inputs are ignored.
export const chartExportFilename = (
  exportName: string | undefined,
  titleText: string | undefined,
  date: Date
): string => {
  const base = exportName?.trim() || titleText?.trim() || 'chart'
  return `${slugifyChartName(base)}-${formatDateStamp(date)}.png`
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd front-dev-home && node --test app/utils/chartExport.test.ts`
Expected: PASS — 8 tests, 0 fail.

- [ ] **Step 5: Commit**

```bash
git add front-dev-home/app/utils/chartExport.ts front-dev-home/app/utils/chartExport.test.ts
git commit -m "feat(charts): add pure chartExportFilename helper"
```

---

### Task 2: Per-theme export background color

**Files:**

- Modify: `app/utils/echartsThemes.ts` (add after `getEchartThemePalette`, ~line 233)
- Test: `app/utils/echartsThemes.test.ts` (new)

**Interfaces:**

- Consumes: existing `EchartThemeName` type from the same file.
- Produces: `getEchartThemeBackground(name: EchartThemeName): string` — a solid hex to paint behind an exported PNG (vintage warm paper, dark navy, others white).

- [ ] **Step 1: Write the failing test**

Create `app/utils/echartsThemes.test.ts`:

```ts
// front-dev-home/app/utils/echartsThemes.test.ts
// Verifies the per-theme export background matches each theme's canvas tone.
// Run: cd front-dev-home && node --test app/utils/echartsThemes.test.ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { getEchartThemeBackground } from './echartsThemes.ts'

test('vintage export background is warm paper', () => {
  assert.equal(getEchartThemeBackground('vintage'), '#fef8ef')
})

test('dark export background is deep navy', () => {
  assert.equal(getEchartThemeBackground('dark'), '#100C2A')
})

test('light alt-themes export on white', () => {
  assert.equal(getEchartThemeBackground('macarons'), '#ffffff')
  assert.equal(getEchartThemeBackground('infographic'), '#ffffff')
  assert.equal(getEchartThemeBackground('shine'), '#ffffff')
  assert.equal(getEchartThemeBackground('roma'), '#ffffff')
})
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd front-dev-home && node --test app/utils/echartsThemes.test.ts`
Expected: FAIL — `getEchartThemeBackground` is not exported.

- [ ] **Step 3: Write the minimal implementation**

In `app/utils/echartsThemes.ts`, immediately after the `getEchartThemePalette` function (currently ends ~line 233), add:

```ts
// Themes render on a transparent canvas so charts inherit their card surface.
// A PNG export, however, needs a solid backdrop or it comes out transparent and
// looks broken on light backgrounds. These match each theme's intended tone:
// vintage's warm paper, dark's navy, and white for the light alt-themes.
const themeBackgrounds: Record<EchartThemeName, string> = {
  vintage: '#fef8ef',
  dark: '#100C2A',
  macarons: '#ffffff',
  infographic: '#ffffff',
  shine: '#ffffff',
  roma: '#ffffff'
}

export const getEchartThemeBackground = (name: EchartThemeName): string =>
  themeBackgrounds[name]
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd front-dev-home && node --test app/utils/echartsThemes.test.ts`
Expected: PASS — 3 tests, 0 fail.

- [ ] **Step 5: Commit**

```bash
git add front-dev-home/app/utils/echartsThemes.ts front-dev-home/app/utils/echartsThemes.test.ts
git commit -m "feat(charts): add per-theme PNG export background"
```

---

### Task 3: Wire the download overlay into `useEchart`

**Files:**

- Modify: `app/composables/useEchart.ts` (full-file replacement below)

**Interfaces:**

- Consumes: `chartExportFilename` (Task 1), `getEchartThemeBackground` (Task 2), existing `registerEchartsThemes`, `useEchartsTheme().resolvedThemeName`.
- Produces: extended `UseEchartOptions` — `{ onClick?, exportName?, disableDownload? }`. Return type stays `void`. Consumed by Task 4 and available to all other chart components.

**Why no unit test here:** this task is DOM + live-ECharts wiring (`echarts.init` needs a sized canvas), which the `node --test` runner can't exercise. The extractable logic (filename, background) is already unit-tested in Tasks 1–2. This task is verified manually in Step 3 via the running app.

- [ ] **Step 1: Replace `app/composables/useEchart.ts` in full**

```ts
import * as echarts from 'echarts'
import type { ComputedRef, Ref } from 'vue'
import type { ECharts, EChartsOption } from 'echarts'
import { registerEchartsThemes, getEchartThemeBackground } from '~/utils/echartsThemes'
import { chartExportFilename } from '~/utils/chartExport'

interface UseEchartOptions {
  // Fired when a series element (e.g. a bar) is clicked. Receives the
  // x-axis category for category-bucketed series — for our charts that's
  // the lot_cd, since xAxis.data is built from lot labels.
  onClick?: (name: string) => void
  // Preferred base name for the downloaded PNG (before the date stamp). Falls
  // back to the chart's title text, then 'chart'.
  exportName?: string
  // Opt out of the hover download button — for charts whose own corner controls
  // would collide with the overlay (e.g. skewvoir/WaferMap.vue).
  disableDownload?: boolean
}

const DOWNLOAD_STYLE_ID = 'sk-chart-dl-style'

// Injected once for the whole app. The button is invisible until its chart host
// is hovered or the button itself is keyboard-focused.
const ensureDownloadStyles = () => {
  if (!import.meta.client) return
  if (document.getElementById(DOWNLOAD_STYLE_ID)) return
  const style = document.createElement('style')
  style.id = DOWNLOAD_STYLE_ID
  style.textContent = `
.sk-chart-host { position: relative; }
.sk-chart-dl-btn {
  position: absolute; top: 6px; right: 6px; z-index: 5;
  display: inline-flex; align-items: center; justify-content: center;
  width: 26px; height: 26px; padding: 0; margin: 0;
  border: none; border-radius: 6px;
  background: rgba(127, 127, 127, 0.14); color: currentColor;
  cursor: pointer; opacity: 0;
  transition: opacity 0.15s ease, background 0.15s ease;
}
.sk-chart-host:hover .sk-chart-dl-btn,
.sk-chart-dl-btn:focus-visible { opacity: 1; }
.sk-chart-dl-btn:hover { background: rgba(127, 127, 127, 0.28); }
.sk-chart-dl-btn svg { width: 15px; height: 15px; display: block; }
`
  document.head.appendChild(style)
}

const DOWNLOAD_ICON_SVG = `
<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
     stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
  <path d="M12 3v12"/><path d="m7 10 5 5 5-5"/><path d="M5 21h14"/>
</svg>`

export const useEchart = (
  elRef: Ref<HTMLDivElement | null>,
  optionRef: ComputedRef<EChartsOption>,
  options: UseEchartOptions = {}
) => {
  registerEchartsThemes(echarts)

  const { resolvedThemeName } = useEchartsTheme()

  let chart: ECharts | null = null
  let resizeHandler: (() => void) | null = null
  let dlButton: HTMLButtonElement | null = null

  const bindClick = () => {
    const callback = options.onClick
    if (!chart || !callback) return
    chart.on('click', (params) => {
      if (params.componentType !== 'series') return
      const name = (params as { name?: string }).name
      if (typeof name === 'string' && name.length > 0) callback(name)
    })
  }

  const downloadChartImage = () => {
    if (!chart) return
    const url = chart.getDataURL({
      type: 'png',
      pixelRatio: 2,
      backgroundColor: getEchartThemeBackground(resolvedThemeName.value)
    })
    const title = (optionRef.value.title as { text?: string } | undefined)?.text
    const filename = chartExportFilename(options.exportName, title, new Date())
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
  }

  const mountDownloadButton = () => {
    if (options.disableDownload || !import.meta.client) return
    if (dlButton || !elRef.value) return
    ensureDownloadStyles()
    elRef.value.classList.add('sk-chart-host')
    const button = document.createElement('button')
    button.type = 'button'
    button.className = 'sk-chart-dl-btn'
    button.title = 'Download chart image'
    button.setAttribute('aria-label', 'Download chart image')
    button.innerHTML = DOWNLOAD_ICON_SVG
    button.addEventListener('click', downloadChartImage)
    elRef.value.appendChild(button)
    dlButton = button
  }

  const unmountDownloadButton = () => {
    if (!dlButton) return
    dlButton.removeEventListener('click', downloadChartImage)
    dlButton.remove()
    dlButton = null
  }

  const ensureChart = () => {
    if (chart || !elRef.value) return
    chart = echarts.init(elRef.value, resolvedThemeName.value)
    chart.setOption(optionRef.value)
    bindClick()
    mountDownloadButton()
    if (!resizeHandler) {
      resizeHandler = () => chart?.resize()
      window.addEventListener('resize', resizeHandler)
    }
  }

  onMounted(() => {
    ensureChart()
  })

  // Containers may be inside a v-if and toggle on/off. When the previous
  // element unmounts, dispose the instance bound to it (and drop its detached
  // button); when a fresh element mounts, init against the new node.
  watch(elRef, (next, prev) => {
    if (prev && prev !== next) {
      chart?.dispose()
      chart = null
      unmountDownloadButton()
    }
    if (next) ensureChart()
  })

  watch(optionRef, (next) => {
    chart?.setOption(next, true)
  })

  // ECharts binds a theme at init time; swapping themes requires dispose +
  // re-init on the same DOM node. The host div and its download button persist
  // across this (same node), so ensureChart()'s mountDownloadButton() no-ops and
  // the button's click closure reads the freshly-assigned `chart`.
  watch(resolvedThemeName, () => {
    if (!elRef.value) return
    chart?.dispose()
    chart = null
    ensureChart()
  })

  onBeforeUnmount(() => {
    if (resizeHandler) {
      window.removeEventListener('resize', resizeHandler)
      resizeHandler = null
    }
    unmountDownloadButton()
    chart?.dispose()
    chart = null
  })
}
```

- [ ] **Step 2: Typecheck**

Run: `cd front-dev-home && npm run typecheck`
Expected: no new errors referencing `useEchart.ts`, `chartExport.ts`, or `echartsThemes.ts`. (Pre-existing unrelated errors, if any, are out of scope — confirm none are in these three files.)

- [ ] **Step 3: Manual verification in the running app**

Use the `verify` skill (or `npm run dev` from `front-dev-home` with `NUXT_API_TARGET=http://localhost:5050` and the Flask mock up). Then, in the app:

1. Open any chart page (e.g. an ebeam recipe-status tab). Hover a chart → a small download button fades in at the top-right corner.
2. Click it → the browser downloads a `*.png` whose background is solid (not transparent) and matches the current theme.
3. Switch the ECharts theme (theme picker) and repeat → still exactly one button per chart (no duplicates), background color tracks the new theme.
4. Navigate away and back (container remount) → still exactly one button, download still works.

Expected: all four hold. If a duplicate button appears after theme switch, the `mountDownloadButton` no-op guard (`if (dlButton ...) return`) regressed — fix before committing.

- [ ] **Step 4: Commit**

```bash
git add front-dev-home/app/composables/useEchart.ts
git commit -m "feat(charts): hover-reveal PNG download on every chart via useEchart"
```

---

### Task 4: Distinguish and align the two TAT-tab charts

**Files:**

- Modify: `app/components/ebeam/RecipeTatView.vue`
  - trend chart: `trendOption` (~lines 455–494), `useEchart(trendEl, ...)` (~line 496)
  - bar chart: `barOption` (~lines 590–634), `useEchart(barEl, ...)` (~line 636)

**Interfaces:**

- Consumes: `useEchart(..., { exportName })` (Task 3); `useEchartsTheme().palette` (existing composable).
- Produces: nothing downstream.

**Why no unit test here:** the change is chart-option styling in a `.vue` SFC (no extractable pure logic); verified visually in Step 6.

- [ ] **Step 1: Add the theme palette to the script**

In `RecipeTatView.vue`, just above `const trendEl = ref<HTMLDivElement | null>(null)` (currently ~line 453), add:

```ts
// Shared theme palette so the two TAT charts read as distinct hues while
// staying theme-aware: bar = palette[0], trend = palette[1].
const { palette } = useEchartsTheme()
```

- [ ] **Step 2: Recolor + regrid the trend line**

In `trendOption`, replace the `grid` line (currently `grid: { left: 8, right: 16, top: 12, bottom: 28, containLabel: true },`) with the shared grid, and replace the `series` block to add `palette[1]` coloring:

```ts
  grid: { left: 8, right: 24, top: 12, bottom: 28, containLabel: true },
```

```ts
  series: [{
    type: 'line',
    smooth: true,
    showSymbol: false,
    itemStyle: { color: palette.value[1] },
    lineStyle: { color: palette.value[1] },
    areaStyle: { color: palette.value[1], opacity: 0.18 },
    data: trendPoints.value.map(p => p.total_meastime)
  }]
```

- [ ] **Step 3: Pass the trend export name**

Replace `useEchart(trendEl, trendOption)` (~line 496) with:

```ts
useEchart(trendEl, trendOption, { exportName: 'daily-tat-trend' })
```

- [ ] **Step 4: Recolor + regrid the bar chart**

In `barOption`, replace the `grid` line (currently `grid: { left: 8, right: 24, top: 8, bottom: 24, containLabel: true },`) with the shared grid, and replace the `series` block to add `palette[0]` coloring:

```ts
    grid: { left: 8, right: 24, top: 12, bottom: 28, containLabel: true },
```

```ts
    series: [{
      type: 'bar',
      data: reversed.map(r => r[metric.id]),
      barMaxWidth: 18,
      itemStyle: { color: palette.value[0], borderRadius: [0, 4, 4, 0] }
    }]
```

- [ ] **Step 5: Pass the bar export name**

Replace `useEchart(barEl, barOption)` (~line 636) with:

```ts
useEchart(barEl, barOption, { exportName: 'top-recipe-by-tat' })
```

- [ ] **Step 6: Typecheck + manual verification**

Run: `cd front-dev-home && npm run typecheck`
Expected: no new errors in `RecipeTatView.vue`.

Then in the running app open `ebeam/cd-sem/<fab>/recipe-status?tab=tat`:

1. "Top recipe by TAT" bars and "Daily TAT trend" line are visibly **different colors** (theme's palette[0] vs palette[1]), while both cards are the same height and the plots share the same insets/padding.
2. Hover each → download button appears; downloads are named `top-recipe-by-tat-<date>.png` and `daily-tat-trend-<date>.png`.
3. Switch ECharts theme → both charts recolor to the new theme's palette[0]/[1] and remain distinct.

- [ ] **Step 7: Commit**

```bash
git add front-dev-home/app/components/ebeam/RecipeTatView.vue
git commit -m "feat(recipe-tat): align TAT chart layout, split colors, name exports"
```

---

## Self-Review

**Spec coverage:**

- Part A (universal download, one file `useEchart.ts`) → Tasks 1, 2, 3. ✅ hover-reveal button, PNG, `pixelRatio: 2`, theme background, `exportName`/`disableDownload`, singleton style, lifecycle teardown all covered.
- Part B (TAT colors + identical layout + exportName) → Task 4. ✅ grid unified, palette[0]/[1], export names.
- Testing section: unit test for `chartExportFilename` → Task 1; theme background → Task 2 (added beyond spec since it is also pure/testable); manual verify of auto-coverage + TAT tab → Tasks 3 & 4 Steps. ✅
- Scope guard (PNG only, no SVG/bulk/menu) → honored; nothing beyond a single button added. ✅

**Placeholder scan:** No TBD/TODO; every code step shows complete code; every command shows expected output. ✅

**Type consistency:** `chartExportFilename(exportName?, titleText?, date)` defined in Task 1 and called identically in Task 3. `getEchartThemeBackground(name)` defined in Task 2, called in Task 3. `UseEchartOptions` gains `exportName`/`disableDownload` in Task 3, used by Task 4's calls. `palette.value[0]`/`[1]` — `palette` is the `ComputedRef` returned by `useEchartsTheme()`, so `.value` indexing inside a `computed()` is correct and reactive. ✅
