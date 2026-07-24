<template>
  <div class="mt-3 space-y-3">
    <!-- Filter row: beam_condition -->
    <div class="flex flex-wrap items-center justify-between gap-2">
      <div class="flex items-center gap-2">
        <span class="sk-label">Beam Condition</span>
        <USelect
          v-model="beamCondition"
          :items="beamConditionItems"
          size="xs"
          icon="i-lucide-filter"
          class="w-48"
        />
        <span class="font-mono text-[11px] text-(--sk-ink-muted)">{{ filteredDocs.length }} docs</span>
        <span
          v-if="selectedCategory"
          class="inline-flex items-center gap-1.5 rounded-full bg-(--sk-surface) px-2.5 py-0.5 ring-1 ring-(--sk-border-soft)"
        >
          <span class="sk-eyebrow">Category</span>
          <span class="font-mono text-[11px] font-bold text-(--sk-ink)">{{ selectedCategory }}</span>
        </span>
      </div>
      <UTooltip text="클립보드 복사">
        <UButton
          icon="i-lucide-clipboard"
          size="xs"
          color="neutral"
          variant="outline"
          aria-label="표를 클립보드에 복사"
          :disabled="filteredDocs.length === 0"
          @click="copyScalarsTable"
        />
      </UTooltip>
      <UButton
        icon="i-lucide-download"
        size="xs"
        color="neutral"
        variant="outline"
        :disabled="filteredDocs.length === 0"
        @click="downloadScalarsCsv"
      >
        CSV 다운로드
      </UButton>
    </div>

    <!-- Header cards: scalars of the selected measurement -->
    <dl
      v-if="selectedScalarCards.length"
      class="grid gap-x-6 gap-y-2 sm:grid-cols-3 lg:grid-cols-5"
    >
      <div
        v-for="card in selectedScalarCards"
        :key="card.key"
        class="rounded-xl bg-(--sk-surface) px-3 py-2 ring-1 ring-(--sk-border-soft)"
      >
        <dt class="truncate sk-eyebrow">
          {{ card.label }}
        </dt>
        <dd class="mt-0.5 font-mono text-sm font-bold tabular-nums text-(--sk-ink)">
          {{ card.value }}
        </dd>
      </div>
    </dl>

    <!-- Two stacked scalar trend panes, each its own scalar dropdown -->
    <div class="grid gap-3 lg:grid-cols-2">
      <div
        v-for="pane in trendPanes"
        :key="pane.id"
        class="rounded-xl bg-(--sk-surface) p-2 ring-1 ring-(--sk-border-soft)"
      >
        <div class="mb-1 flex items-center justify-between gap-2 px-1">
          <USelect
            v-model="pane.metric.value"
            :items="scalarItems"
            size="xs"
            class="w-44"
          />
        </div>
        <EbeamHardwareBsmTrendChart
          :label="prettyLabel(pane.metric.value)"
          :points="trendPoints(pane.metric.value)"
          :selected="selectedKey"
          :events="maintenanceEvents"
          @select="selectedKey = $event"
        />
      </div>
    </div>

    <!-- Dual 360° radars for the selected measurement -->
    <div class="rounded-xl bg-(--sk-surface) p-2 ring-1 ring-(--sk-border-soft)">
      <div class="mb-1 flex items-center justify-between gap-2 px-1">
        <div class="sk-title">
          360° 빔 형상
        </div>
        <USelect
          v-model="selectedKey"
          :items="measurementItems"
          size="xs"
          icon="i-lucide-clock"
          placeholder="측정 시각 선택"
          class="w-64"
        />
      </div>
      <div class="grid grid-cols-2 gap-2">
        <div
          v-for="radar in radarPanes"
          :key="radar.id"
          class="flex flex-col"
        >
          <USelect
            v-model="radar.metric.value"
            :items="profileItems"
            size="xs"
            class="mx-auto mb-1 w-44"
          />
          <EbeamHardwareBsmRadarChart
            :title="prettyLabel(radar.metric.value)"
            :color-index="radar.colorIndex"
            :angles="angles"
            :values="profileValues(radar.metric.value)"
            :min="radarRange(radar.metric.value).min"
            :max="radarRange(radar.metric.value).max"
          />
          <EbeamHardwareAxisRangeControl
            :model-value="rangeFor(radar.metric.value)"
            :default-range="defaultRangeFor(radar.metric.value, derivedRange(radar.metric.value))"
            :label="prettyLabel(radar.metric.value)"
            @update:model-value="setRange(radar.metric.value, $event)"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import {
  profileMetricKeys, scalarMetricKeys, radialRange, degreeLabels, prettyLabel
} from '~/utils/beamMetrics'
import { copyTableToClipboard, downloadCsv } from '~/utils/csvDownload'
import { defaultRangeFor, resolveAxisRange } from '~/utils/profileAxisRange'
import type { BmPmEvent } from '~/utils/bmPmMarkers'

const props = defineProps<{
  docs: Record<string, unknown>[]
  maintenanceEvents?: BmPmEvent[]
}>()

const tsOf = (d: Record<string, unknown>) => String(d.timestamp ?? '')
// The mock emits one doc per (timestamp, beam_condition), so timestamp alone is
// ambiguous under "All conditions". Identify a measurement by the composite key.
const condOf = (d: Record<string, unknown>) => String(d.beam_condition ?? '')
// `category` (e.g. "I-diff", "I-diff_hp") is a per-doc classification from
// OpenSearch — measurement metadata like beam_condition, surfaced for the
// selected measurement and exported alongside it.
const catOf = (d: Record<string, unknown>) => String(d.category ?? '')
const keyOf = (d: Record<string, unknown>) => `${tsOf(d)}|${condOf(d)}`
const numOf = (v: unknown): number => {
  const n = typeof v === 'number' ? v : Number(v)
  return Number.isFinite(n) ? n : NaN
}

// beam_condition filter
const beamConditions = computed(() =>
  Array.from(new Set(props.docs.map(d => String(d.beam_condition ?? '')).filter(Boolean))).sort()
)
const beamCondition = ref('all')
const beamConditionItems = computed(() => [
  { label: 'All conditions', value: 'all' },
  ...beamConditions.value.map(c => ({ label: c, value: c }))
])

const filteredDocs = computed(() =>
  beamCondition.value === 'all'
    ? props.docs
    : props.docs.filter(d => String(d.beam_condition ?? '') === beamCondition.value)
)

// Selectors derived from docs (data-driven).
const profileOptions = computed(() => profileMetricKeys(props.docs))
const scalarOptions = computed(() => scalarMetricKeys(props.docs))
const profileItems = computed(() => profileOptions.value.map(o => ({ label: o.label, value: o.key })))
const scalarItems = computed(() => scalarOptions.value.map(o => ({ label: o.label, value: o.key })))
const angles = computed(() => degreeLabels(props.docs))

// Two trend metrics + two radar metrics, seeded from known keys when present.
const pick = (opts: { key: string }[], preferred: string, fallbackIdx: number) =>
  opts.some(o => o.key === preferred) ? preferred : (opts[fallbackIdx]?.key ?? opts[0]?.key ?? '')

const trendA = ref(pick(scalarOptions.value, 'Ellipicity', 0))
const trendB = ref(pick(scalarOptions.value, 'Ave. Noise', 1))
const radarA = ref(pick(profileOptions.value, 'Reso EB', 0))
const radarB = ref(pick(profileOptions.value, 'Reso Detector', 1))

const trendPanes = [
  { id: 'a', metric: trendA },
  { id: 'b', metric: trendB }
]
const radarPanes = [
  { id: 'a', metric: radarA, colorIndex: 0 },
  { id: 'b', metric: radarB, colorIndex: 1 }
]

// Trend points (ascending time) for a scalar key. `key` is the composite
// measurement id so a click selects the exact (timestamp, beam_condition) doc.
const trendPoints = (key: string) =>
  filteredDocs.value
    .map(d => ({ ts: tsOf(d), key: keyOf(d), value: numOf(d[key]) }))
    .filter(p => p.ts && Number.isFinite(p.value))
    .sort((a, b) => a.ts.localeCompare(b.ts))

// Measurements (desc, newest first) for the radar selector dropdown. Under
// "All conditions" the label disambiguates by appending the beam_condition;
// the category (when present) is appended after that. Parts are joined so an
// absent field never leaves a dangling separator.
const measurementItems = computed(() =>
  [...filteredDocs.value]
    .filter(d => tsOf(d))
    .sort((a, b) => keyOf(b).localeCompare(keyOf(a)))
    .map((d) => {
      const parts = [tsOf(d)]
      if (beamCondition.value === 'all') parts.push(condOf(d))
      parts.push(catOf(d))
      return { label: parts.filter(Boolean).join(' · '), value: keyOf(d) }
    })
)

const selectedKey = ref('')
watch(measurementItems, (items) => {
  if (!items.some(i => i.value === selectedKey.value)) selectedKey.value = items[0]?.value ?? ''
}, { immediate: true })

const selectedDoc = computed(() => filteredDocs.value.find(d => keyOf(d) === selectedKey.value))
const selectedCategory = computed(() => (selectedDoc.value ? catOf(selectedDoc.value) : ''))

const profileValues = (key: string): number[] => {
  const v = selectedDoc.value?.[key]
  return Array.isArray(v) ? v.map(numOf) : []
}

// The radial scale the radar draws at: a user override if one is stored, else
// the metric's operating band, else the data-derived range. Overrides are
// keyed by canonical metric, so a range set here on `Reso EB` is the same one
// the 데일리 Sharpness tab uses for `reso_eb` — the same measurement.
const { rangeFor, setRange } = useProfileAxisRange()
const derivedRange = (key: string) => radialRange(filteredDocs.value, key)
const radarRange = (key: string) => resolveAxisRange(key, rangeFor(key), derivedRange(key))

const selectedScalarCards = computed(() => {
  const d = selectedDoc.value
  if (!d) return []
  return scalarOptions.value.map(o => ({
    key: o.key,
    label: o.label,
    value: Number.isFinite(numOf(d[o.key])) ? numOf(d[o.key]).toFixed(4) : '-'
  }))
})

const toast = useToast()

const scalarsTable = () => {
  const keys = scalarOptions.value.map(o => o.key)
  const headers = ['timestamp', 'beam_condition', 'category', ...keys]
  const rows = [...filteredDocs.value]
    .sort((a, b) => tsOf(a).localeCompare(tsOf(b)))
    .map(d => [tsOf(d), condOf(d), catOf(d), ...keys.map(k => numOf(d[k]))])
  return { headers, rows }
}

const downloadScalarsCsv = () => {
  const { headers, rows } = scalarsTable()
  const date = new Date().toISOString().slice(0, 10)
  downloadCsv(`bsm-${beamCondition.value}-${date}.csv`, headers, rows)
}

const copyScalarsTable = async () => {
  const { headers, rows } = scalarsTable()
  const ok = await copyTableToClipboard(headers, rows)
  toast.add(
    ok
      ? { title: '클립보드에 복사됨', icon: 'i-lucide-check', color: 'success' }
      : { title: '복사에 실패했습니다', icon: 'i-lucide-x', color: 'error' }
  )
}
</script>
