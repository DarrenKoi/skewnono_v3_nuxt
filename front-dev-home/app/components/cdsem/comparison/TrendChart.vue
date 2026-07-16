<template>
  <div
    class="trend-chart"
    :class="compact ? 'trend-chart--compact' : ''"
  >
    <header
      v-if="!compact"
      class="trend-chart__head"
    >
      <div>
        <p class="trend-chart__eyebrow">
          trend · {{ focusedLot ? focusedLot : '-' }}
        </p>
        <h4 class="trend-chart__title">
          {{ title }}
        </h4>
      </div>
      <div
        class="trend-chart__toggle"
        role="tablist"
        aria-label="trend mode"
      >
        <button
          type="button"
          role="tab"
          :aria-selected="mode === 'health'"
          class="trend-chart__tab"
          :class="mode === 'health' ? 'trend-chart__tab--on' : ''"
          @click="mode = 'health'"
        >
          T-A · health
        </button>
        <button
          type="button"
          role="tab"
          :aria-selected="mode === 'composition'"
          class="trend-chart__tab"
          :class="mode === 'composition' ? 'trend-chart__tab--on' : ''"
          @click="mode = 'composition'"
        >
          T-B · composition
        </button>
        <button
          type="button"
          role="tab"
          :aria-selected="mode === 'lines'"
          class="trend-chart__tab"
          :class="mode === 'lines' ? 'trend-chart__tab--on' : ''"
          @click="mode = 'lines'"
        >
          T-C · paras
        </button>
      </div>
    </header>

    <div
      v-if="!hasData"
      class="trend-chart__empty"
    >
      <UIcon
        name="i-lucide-line-chart"
        class="h-4 w-4"
      />
      <span>lot 을 선택하면 추이가 표시됩니다</span>
    </div>

    <svg
      v-else
      ref="svgEl"
      class="trend-chart__svg"
      :viewBox="`0 0 ${vbW} ${vbH}`"
      preserveAspectRatio="none"
      :aria-label="`${focusedLot} ${mode} trend`"
    >
      <!-- Y zone bands for health mode (red / yellow / green visual reference) -->
      <template v-if="mode === 'health'">
        <rect
          x="0"
          :y="bandRedY"
          :width="vbW"
          :height="bandRedH"
          :fill="healthSwatches.red.tint"
          opacity="0.55"
        />
        <rect
          x="0"
          :y="bandYellowY"
          :width="vbW"
          :height="bandYellowH"
          :fill="healthSwatches.yellow.tint"
          opacity="0.55"
        />
        <rect
          x="0"
          :y="bandGreenY"
          :width="vbW"
          :height="bandGreenH"
          :fill="healthSwatches.green.tint"
          opacity="0.55"
        />
      </template>

      <!-- Composition stacked area -->
      <template v-if="mode === 'composition'">
        <path
          v-for="seg in compositionPaths"
          :key="seg.key"
          :d="seg.d"
          :fill="seg.color"
          opacity="0.85"
        />
      </template>

      <!-- Per-para lines (normalised, 0 → per-line max) -->
      <template v-if="mode === 'lines'">
        <polyline
          v-for="line in paraLines"
          :key="line.key"
          :points="line.points"
          fill="none"
          :stroke="line.color"
          stroke-width="1.5"
          stroke-linejoin="round"
          stroke-linecap="round"
          opacity="0.95"
        />
        <g v-if="!compact">
          <text
            v-for="line in paraLines"
            :key="`label-${line.key}`"
            :x="vbW - 4"
            :y="line.labelY"
            class="trend-chart__line-label"
            text-anchor="end"
            :fill="line.color"
          >{{ line.label }}</text>
        </g>
      </template>

      <!-- Health trajectory line + dots -->
      <template v-if="mode === 'health'">
        <polyline
          :points="healthLinePoints"
          fill="none"
          :stroke="lineColor"
          stroke-width="1.8"
          stroke-linejoin="round"
          stroke-linecap="round"
        />
        <g>
          <circle
            v-for="(p, idx) in healthDots"
            :key="`dot-${idx}`"
            :cx="p.x"
            :cy="p.y"
            r="3.4"
            :fill="p.color"
            stroke="white"
            stroke-width="1.2"
          />
        </g>
      </template>

      <!-- x-axis date ticks -->
      <g>
        <text
          v-for="(d, idx) in displayDates"
          :key="d"
          :x="xForIndex(idx)"
          :y="vbH - 4"
          class="trend-chart__tick"
          text-anchor="middle"
        >{{ formatTick(d) }}</text>
      </g>
    </svg>

    <footer
      v-if="!compact && (mode === 'composition' || mode === 'lines')"
      class="trend-chart__legend"
    >
      <span
        v-for="(c, key) in legendColors"
        :key="key"
        class="trend-chart__legend-item"
      >
        <span
          class="trend-chart__swatch"
          :style="{ background: c }"
        />
        {{ key }}
      </span>
    </footer>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useColorMode } from '#imports'
import { paraColors, paraColorsDark, paraOrder, classifyHealth, healthSwatches } from './healthTokens'
import type { SummaryBucketKey, SummaryRow, RecipeTrendResponse } from '~/composables/useRecipeStatisticsApi'
import { augmentSummaryRow } from '~/composables/useLotHealthMock'

type TrendMode = 'health' | 'composition' | 'lines'

const props = withDefaults(defineProps<{
  trend: RecipeTrendResponse | null | undefined
  bucket: SummaryBucketKey
  focusedLot: string | null
  title?: string
  compact?: boolean
  defaultMode?: TrendMode
}>(), {
  title: '추이',
  compact: false,
  defaultMode: 'health'
})

const colorMode = useColorMode()
const palette = computed(() => colorMode.value === 'dark' ? paraColorsDark : paraColors)

const mode = ref<TrendMode>(props.defaultMode)

const svgEl = ref<SVGElement | null>(null)
// Full mode renders in wide containers (detail modal); a wider viewBox keeps
// tick/label text at its designed optical size instead of scaling up 2-3x.
const vbW = computed(() => props.compact ? 320 : 640)
const vbH = computed(() => props.compact ? 60 : 110)

const displayDates = computed(() => props.trend?.dates ?? [])

const focusedSeries = computed<Array<SummaryRow | null>>(() => {
  if (!props.trend || !props.focusedLot) return []
  return displayDates.value.map((date) => {
    const bucket = props.trend!.trend[date]
    if (!bucket) return null
    const list = bucket[props.bucket]
    return list?.find(r => r.lot_cd === props.focusedLot) ?? null
  })
})

const hasData = computed(() => focusedSeries.value.some(Boolean))

// HEALTH MODE — violation_ratio over time as a polyline
const healthValues = computed<Array<number | null>>(() => {
  return focusedSeries.value.map((row) => {
    if (!row) return null
    const aug = augmentSummaryRow(row, props.bucket)
    return aug.violation_ratio
  })
})

const xForIndex = (idx: number) => {
  const n = displayDates.value.length
  if (n <= 1) return vbW.value / 2
  return 14 + (vbW.value - 28) * (idx / (n - 1))
}

const yForRatio = (ratio: number) => {
  // y range: 0 (top) = ratio 1.0, full height = ratio 0
  const usableTop = 8
  const usableBot = vbH.value - 18
  return usableTop + (usableBot - usableTop) * (1 - Math.min(1, Math.max(0, ratio)))
}

const healthLinePoints = computed(() => {
  return healthValues.value
    .map((v, idx) => v === null ? null : `${xForIndex(idx)},${yForRatio(v)}`)
    .filter(Boolean)
    .join(' ')
})

const healthDots = computed(() => {
  return healthValues.value.flatMap((v, idx) => {
    if (v === null) return []
    const level = classifyHealth(v)
    return [{ x: xForIndex(idx), y: yForRatio(v), color: healthSwatches[level].dot }]
  })
})

// Y bands for health zones
const bandRedY = computed(() => yForRatio(1.0))
const bandRedH = computed(() => yForRatio(0.20) - yForRatio(1.0))
const bandYellowY = computed(() => yForRatio(0.20))
const bandYellowH = computed(() => yForRatio(0.10) - yForRatio(0.20))
const bandGreenY = computed(() => yForRatio(0.10))
const bandGreenH = computed(() => yForRatio(0) - yForRatio(0.10))

const lineColor = computed(() => colorMode.value === 'dark' ? '#F4EFE6' : '#15110D')

// COMPOSITION MODE — para_16/13/9/5 stacked area
const compositionPaths = computed(() => {
  const series = focusedSeries.value
  if (series.length === 0) return []
  // Compute per-date stack max so we can normalise to relative %
  const maxes = series.map(s => s ? s.para_16 + s.para_13 + s.para_9 + s.para_5 : 0)

  // Cumulative offsets — bottom upward
  let bottom = paraOrder.map(() => 0) as number[]
  const paths: Array<{ key: string, d: string, color: string }> = []

  for (let i = paraOrder.length - 1; i >= 0; i--) {
    const key = paraOrder[i] as typeof paraOrder[number]
    const top = bottom.map((b, idx) => {
      const total = maxes[idx]
      if (!total) return b
      const val = series[idx]?.[key] ?? 0
      return b + (val / total)
    })
    const upper = top.map((t, idx) => `${xForIndex(idx)},${yForRatio(t)}`).join(' L ')
    const lowerReverse = bottom.map((b, idx) => `${xForIndex(idx)},${yForRatio(b)}`).reverse().join(' L ')
    const d = `M ${upper} L ${lowerReverse} Z`
    paths.push({ key, d, color: palette.value[key] })
    bottom = top
  }
  return paths.reverse()
})

// LINES MODE — one polyline per para, each normalised to its own 0→max so all
// four lines fill the card height regardless of absolute magnitude (p5 stays
// readable next to a much larger p16). Pinning min to 0 keeps "growth from zero"
// intuition honest within each line's own band.
const paraLines = computed(() => {
  const series = focusedSeries.value
  if (series.length === 0) return []
  const usableTop = 6
  const usableBot = vbH.value - 18
  return paraOrder.map((key) => {
    const values = series.map(s => s ? (s[key] as number) : null)
    const present = values.filter((v): v is number => v !== null)
    const max = present.length ? Math.max(...present, 1) : 1
    const points = values
      .map((v, idx) => {
        if (v === null) return null
        const norm = v / max
        const y = usableTop + (usableBot - usableTop) * (1 - norm)
        return `${xForIndex(idx)},${y}`
      })
      .filter(Boolean)
      .join(' ')
    const lastIdx = [...values].reverse().findIndex(v => v !== null)
    const lastVal = lastIdx === -1 ? 0 : (values[values.length - 1 - lastIdx] as number)
    const labelY = usableTop + (usableBot - usableTop) * (1 - lastVal / max)
    return {
      key,
      label: key.replace('para_', 'p'),
      color: palette.value[key],
      points,
      labelY
    }
  })
})

const legendColors = computed(() => {
  const out: Record<string, string> = {}
  for (const k of paraOrder) {
    out[k] = palette.value[k]
  }
  return out
})

const formatTick = (date: string) => {
  // YYYY-MM-DD → MM/DD
  const parts = date.split('-')
  return parts.length === 3 ? `${parts[1]}/${parts[2]}` : date
}
</script>

<style scoped>
.trend-chart {
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 100%;
}

.trend-chart--compact {
  gap: 2px;
}

.trend-chart__head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 8px;
}

.trend-chart__eyebrow {
  font: 500 9.5px/1.2 var(--font-mono);
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--sk-ink-subtle);
}

.trend-chart__title {
  font: 600 12.5px/1.2 var(--font-sans);
  color: var(--sk-ink);
  margin-top: 2px;
}

.trend-chart__toggle {
  display: inline-flex;
  background: var(--sk-muted-surface);
  border-radius: 7px;
  padding: 2px;
  box-shadow: inset 0 0 0 1px var(--sk-border);
}

.trend-chart__tab {
  font: 600 10.5px/1 var(--font-sans);
  padding: 4px 8px;
  border-radius: 5px;
  color: var(--sk-ink-muted);
  cursor: pointer;
  transition: all 120ms ease;
}

.trend-chart__tab--on {
  background: var(--sk-surface);
  color: var(--sk-ink);
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04);
}

.trend-chart__svg {
  width: 100%;
  height: auto;
  display: block;
}

.trend-chart__tick {
  font: 500 8.5px/1 var(--font-mono);
  fill: var(--sk-ink-subtle);
  font-variant-numeric: tabular-nums;
}

.trend-chart__line-label {
  font: 600 8.5px/1 var(--font-mono);
  font-variant-numeric: tabular-nums;
}

.trend-chart__empty {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 20px 12px;
  font: 500 11px/1.4 var(--font-sans);
  color: var(--sk-ink-subtle);
}

.trend-chart__legend {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  font: 500 10px/1 var(--font-mono);
  color: var(--sk-ink-muted);
}

.trend-chart__legend-item {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.trend-chart__swatch {
  display: inline-block;
  width: 9px;
  height: 9px;
  border-radius: 2px;
}
</style>
