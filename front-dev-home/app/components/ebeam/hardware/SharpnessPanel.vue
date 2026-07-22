<template>
  <div class="mt-3 space-y-3">
    <!-- Filter row: beam condition (SEM_Cond_No · Vacc) -->
    <div class="flex flex-wrap items-center justify-between gap-2">
      <div class="flex items-center gap-2">
        <span class="sk-label">Beam Condition</span>
        <USelect
          v-model="condition"
          :items="conditionItems"
          size="xs"
          icon="i-lucide-filter"
          class="w-52"
        />
        <span class="font-mono text-[11px] text-(--sk-ink-muted)">{{ filteredDocs.length }} docs</span>
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

    <!-- Header cards: summ_beam scalars of the selected measurement -->
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

    <!-- Two stacked summ_beam trend panes, each its own scalar dropdown -->
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
          :label="pane.metric.value"
          :points="trendPoints(pane.metric.value)"
          :selected="selectedTs"
          :events="maintenanceEvents"
          @select="selectedTs = $event"
        />
      </div>
    </div>

    <!-- Dual 360° radars for the selected measurement (per-degree fields) -->
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
            :title="radar.metric.value"
            :color-index="radar.colorIndex"
            :angles="angles"
            :values="profileValues(radar.metric.value)"
            :min="radialRange(radar.metric.value).min"
            :max="radialRange(radar.metric.value).max"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { copyTableToClipboard, downloadCsv } from '~/utils/csvDownload'
import { stableRadialRange } from '~/utils/chartRange'
import type { BmPmEvent } from '~/utils/bmPmMarkers'

const props = defineProps<{
  docs: Record<string, unknown>[]
  maintenanceEvents?: BmPmEvent[]
}>()

// The three per-degree fields (dicts keyed "0.0".."337.5") usable as radars.
// All three are offered rather than curated down — which profile is the useful
// lever is still an open question, so the engineer picks.
const PROFILE_KEYS = ['reso_eb', 'noise', 'reso_detector'] as const

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

// Condition filter options (data-driven, stable order).
const conditions = computed(() => {
  const seen = new Map<string, string>()
  for (const d of props.docs) {
    const key = condKeyOf(d)
    if (!seen.has(key)) seen.set(key, condLabelOf(d))
  }
  return [...seen.entries()].sort((a, b) => a[0].localeCompare(b[0]))
})
const condition = ref('all')
const conditionItems = computed(() => [
  { label: 'All conditions', value: 'all' },
  ...conditions.value.map(([value, label]) => ({ label, value }))
])

const filteredDocs = computed(() =>
  condition.value === 'all'
    ? props.docs
    : props.docs.filter(d => condKeyOf(d) === condition.value)
)

// summ_beam scalar keys + per-degree profile fields, discovered off the first doc.
const scalarKeys = computed(() => Object.keys(asRecord(props.docs[0]?.summ_beam)))
const profileKeys = computed<string[]>(() =>
  PROFILE_KEYS.filter(k => Object.keys(asRecord(props.docs[0]?.[k])).length > 0)
)
const scalarItems = computed(() => scalarKeys.value.map(k => ({ label: k, value: k })))
const profileItems = computed(() => profileKeys.value.map(k => ({ label: k, value: k })))

// Degree axis: numerically-sorted keys of a per-degree dict ("0.0".."337.5").
const angles = computed(() => {
  const dict = asRecord(props.docs.find(d => Object.keys(asRecord(d[PROFILE_KEYS[0]])).length)?.[PROFILE_KEYS[0]])
  return Object.keys(dict).sort((a, b) => Number(a) - Number(b))
})

// Two trend metrics + two radar metrics, seeded from known keys when present.
const pick = (keys: string[], preferred: string, fallbackIdx: number) =>
  keys.includes(preferred) ? preferred : (keys[fallbackIdx] ?? keys[0] ?? '')

const trendA = ref(pick(scalarKeys.value, 'Ellipticity', 0))
const trendB = ref(pick(scalarKeys.value, 'Tilt', 1))
const radarA = ref(pick([...profileKeys.value], 'reso_eb', 0))
const radarB = ref(pick([...profileKeys.value], 'noise', 1))

const trendPanes = [
  { id: 'a', metric: trendA },
  { id: 'b', metric: trendB }
]
const radarPanes = [
  { id: 'a', metric: radarA, colorIndex: 0 },
  { id: 'b', metric: radarB, colorIndex: 1 }
]

// Trend points (ascending time) for a summ_beam scalar key.
const trendPoints = (key: string) =>
  filteredDocs.value
    .map(d => ({ ts: tsOf(d), key, value: numOf(asRecord(d.summ_beam)[key]) }))
    .filter(p => p.ts && Number.isFinite(p.value))
    .sort((a, b) => a.ts.localeCompare(b.ts))

// Timestamps (desc, newest first) for the radar selector dropdown.
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

// Fixed radial scale per metric across the filtered docs, with a stable
// magnitude-relative span so a near-constant profile reads as a near-circle.
const radialRange = (key: string): { min: number, max: number } => {
  const vals: number[] = []
  for (const d of filteredDocs.value) {
    const dict = asRecord(d[key])
    for (const a of angles.value) vals.push(numOf(dict[a]))
  }
  return stableRadialRange(vals) ?? { min: 0, max: 1 }
}

const selectedScalarCards = computed(() => {
  const sb = asRecord(selectedDoc.value?.summ_beam)
  if (!selectedDoc.value) return []
  return scalarKeys.value.map(k => ({
    key: k,
    label: k,
    value: Number.isFinite(numOf(sb[k])) ? numOf(sb[k]).toFixed(4) : '-'
  }))
})

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
