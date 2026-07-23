<template>
  <div class="mt-3 space-y-3">
    <!-- Filter row: beam condition (SEM_Cond_No · Vacc) as segmented buttons -->
    <div class="flex flex-wrap items-center justify-between gap-2">
      <div class="flex items-center gap-2">
        <span class="sk-label">Beam Condition</span>
        <div class="flex overflow-hidden rounded-lg border border-(--sk-border)">
          <button
            v-for="[value, label] in conditions"
            :key="value"
            type="button"
            class="px-2.5 py-1 text-[11px] font-semibold transition-colors"
            :class="value === condition
              ? 'bg-(--sk-ink) text-white dark:text-zinc-900'
              : 'text-(--sk-ink-muted) hover:bg-(--sk-muted-surface)'"
            @click="condition = value"
          >
            {{ label }}
          </button>
        </div>
        <span class="font-mono text-[11px] text-(--sk-ink-muted)">{{ filteredDocs.length }} docs</span>
      </div>
      <div class="flex items-center gap-2">
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
    </div>

    <!-- summ_beam scalar trend over time: one chart, category picked here -->
    <div class="rounded-xl bg-(--sk-surface) p-2 ring-1 ring-(--sk-border-soft)">
      <div class="mb-1 flex items-center justify-between gap-2 px-1">
        <div class="sk-title">
          Beam Summary Trend
        </div>
        <USelect
          v-model="trendMetric"
          :items="scalarItems"
          size="xs"
          icon="i-lucide-activity"
          class="w-44"
        />
      </div>
      <EbeamHardwareBsmTrendChart
        :label="trendMetric"
        :points="trendPoints(trendMetric)"
        :selected="selectedTs"
        :events="maintenanceEvents"
        :y-options="TREND_Y_OPTIONS"
        @select="selectedTs = $event"
      />
    </div>

    <!-- All three per-degree profiles of the selected measurement, together:
         reso_eb / noise as radars, reso_detector as a 0~360° line chart. -->
    <div class="rounded-xl bg-(--sk-surface) p-2 ring-1 ring-(--sk-border-soft)">
      <div class="mb-1 flex items-center justify-between gap-2 px-1">
        <div class="sk-title">
          360° 빔 형상
        </div>
        <USelect
          v-model="selectedTs"
          :items="timestampItems"
          size="xs"
          icon="i-lucide-clock"
          placeholder="측정 시각 선택"
          class="w-56"
        />
      </div>
      <div class="grid gap-2 lg:grid-cols-3">
        <EbeamHardwareBsmRadarChart
          v-for="(key, i) in radarKeys"
          :key="key"
          :title="key"
          :color-index="i"
          :angles="angles"
          :values="profileValues(key)"
          :min="profileRange(key).min"
          :max="profileRange(key).max"
        />
        <EbeamHardwareSharpnessProfileChart
          v-if="hasDetector"
          title="reso_detector"
          :color-index="2"
          :angles="angles"
          :values="profileValues('reso_detector')"
          :min="profileRange('reso_detector').min"
          :max="profileRange('reso_detector').max"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { copyTableToClipboard, downloadCsv } from '~/utils/csvDownload'
import { stableRadialRange, type StableYRangeOptions } from '~/utils/chartRange'
import type { BmPmEvent } from '~/utils/bmPmMarkers'

const props = defineProps<{
  docs: Record<string, unknown>[]
  maintenanceEvents?: BmPmEvent[]
}>()

// The three per-degree fields (dicts keyed "0.0".."337.5"), all shown at once:
// reso_eb and noise read well as radar shapes; reso_detector's tiny magnitudes
// read better on a cartesian 0~360° axis.
const RADAR_KEYS = ['reso_eb', 'noise'] as const
const DETECTOR_KEY = 'reso_detector'

// The profiles wobble a fraction of a percent around a stable operating point;
// the stable-range default (minSpanRatio 0.25) reserves a quarter of the
// magnitude and flattens that wobble to invisibility. A small floor keeps the
// axis hugging the data while still padding degenerate near-flat profiles.
const PROFILE_RANGE_OPTIONS: StableYRangeOptions = { minSpanRatio: 0.02 }
const TREND_Y_OPTIONS: StableYRangeOptions = { minSpanRatio: 0.05 }

const tsOf = (d: Record<string, unknown>) => String(d.timestamp ?? '')
const numOf = (v: unknown): number => {
  const n = typeof v === 'number' ? v : Number(v)
  return Number.isFinite(n) ? n : NaN
}
const asRecord = (v: unknown): Record<string, unknown> =>
  (v && typeof v === 'object' && !Array.isArray(v)) ? v as Record<string, unknown> : {}

// beam_condition is an object; group by the paired (SEM_Cond_No, Vacc).
const condKeyOf = (d: Record<string, unknown>): string => {
  const bc = asRecord(d.beam_condition)
  return `${String(bc.SEM_Cond_No ?? '')}_${String(bc.Vacc ?? '')}`
}
const condLabelOf = (d: Record<string, unknown>): string => {
  const bc = asRecord(d.beam_condition)
  return `Cond ${String(bc.SEM_Cond_No ?? '—')} · ${String(bc.Vacc ?? '—')}V`
}

// Condition options (data-driven, stable order) — usually just two, so they
// render as segmented buttons rather than a dropdown.
const conditions = computed(() => {
  const seen = new Map<string, string>()
  for (const d of props.docs) {
    const key = condKeyOf(d)
    if (!seen.has(key)) seen.set(key, condLabelOf(d))
  }
  return [...seen.entries()].sort((a, b) => a[0].localeCompare(b[0]))
})

// Default to the 800V condition (matched on the label so it tracks whatever
// SEM_Cond_No the office index pairs it with — Cond 6 in practice).
const condition = ref('')
watch(conditions, (conds) => {
  if (conds.some(([key]) => key === condition.value)) return
  const preferred = conds.find(([, label]) => label.includes('800V'))
  condition.value = (preferred ?? conds[0])?.[0] ?? ''
}, { immediate: true })

const filteredDocs = computed(() => props.docs.filter(d => condKeyOf(d) === condition.value))

// summ_beam scalar keys discovered off the first doc (office and mock differ).
const scalarKeys = computed(() => Object.keys(asRecord(props.docs[0]?.summ_beam)))
const scalarItems = computed(() => scalarKeys.value.map(k => ({ label: k, value: k })))

const radarKeys = computed<string[]>(() =>
  RADAR_KEYS.filter(k => Object.keys(asRecord(props.docs[0]?.[k])).length > 0)
)
const hasDetector = computed(() =>
  Object.keys(asRecord(props.docs[0]?.[DETECTOR_KEY])).length > 0
)

// Degree axis: numerically-sorted keys of a per-degree dict ("0.0".."337.5").
const angles = computed(() => {
  const source = [...RADAR_KEYS, DETECTOR_KEY]
    .map(k => asRecord(props.docs.find(d => Object.keys(asRecord(d[k])).length)?.[k]))
    .find(dict => Object.keys(dict).length > 0) ?? {}
  return Object.keys(source).sort((a, b) => Number(a) - Number(b))
})

// Trend metric, seeded from a known key when present.
const trendMetric = ref('')
watch(scalarKeys, (keys) => {
  if (keys.includes(trendMetric.value)) return
  trendMetric.value = keys.includes('Ellipticity') ? 'Ellipticity' : (keys[0] ?? '')
}, { immediate: true })

// Trend points (ascending time) for a summ_beam scalar key.
const trendPoints = (key: string) =>
  filteredDocs.value
    .map(d => ({ ts: tsOf(d), key, value: numOf(asRecord(d.summ_beam)[key]) }))
    .filter(p => p.ts && Number.isFinite(p.value))
    .sort((a, b) => a.ts.localeCompare(b.ts))

// Timestamps (desc, newest first) for the profile selector dropdown.
const timestampItems = computed(() =>
  Array.from(new Set(filteredDocs.value.map(tsOf).filter(Boolean))).sort((a, b) => b.localeCompare(a))
)

const selectedTs = ref('')
watch(timestampItems, (items) => {
  if (!items.includes(selectedTs.value)) selectedTs.value = items[0] ?? ''
}, { immediate: true })

const selectedDoc = computed(() => filteredDocs.value.find(d => tsOf(d) === selectedTs.value))

// Per-degree dict -> values in degree order.
const profileValues = (key: string): number[] => {
  const dict = asRecord(selectedDoc.value?.[key])
  return angles.value.map(a => numOf(dict[a]))
}

// Fixed scale per metric across the filtered docs, so switching timestamps
// doesn't rescale the chart under the reader.
const profileRange = (key: string): { min: number, max: number } => {
  const vals: number[] = []
  for (const d of filteredDocs.value) {
    const dict = asRecord(d[key])
    for (const a of angles.value) vals.push(numOf(dict[a]))
  }
  return stableRadialRange(vals, PROFILE_RANGE_OPTIONS) ?? { min: 0, max: 1 }
}

const toast = useToast()

const scalarsTable = () => {
  const keys = scalarKeys.value
  const headers = ['timestamp', 'condition', ...keys]
  const rows = [...filteredDocs.value]
    .sort((a, b) => tsOf(a).localeCompare(tsOf(b)))
    .map((d) => {
      const sb = asRecord(d.summ_beam)
      return [tsOf(d), condKeyOf(d), ...keys.map(k => numOf(sb[k]))]
    })
  return { headers, rows }
}

const downloadScalarsCsv = () => {
  const { headers, rows } = scalarsTable()
  const date = new Date().toISOString().slice(0, 10)
  downloadCsv(`sharpness-${condition.value}-${date}.csv`, headers, rows)
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
