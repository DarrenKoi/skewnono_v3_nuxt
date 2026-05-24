<template>
  <div class="space-y-3">
    <!-- Parameter selector + state -->
    <div class="dashboard-surface flex flex-wrap items-center gap-2 rounded-2xl px-3.5 py-2.5">
      <span class="font-mono text-[10px] text-zinc-400">parameter</span>
      <USelect
        v-model="selectedParam"
        size="xs"
        :items="paramItems"
        class="min-w-[10rem]"
        :disabled="paramItems.length === 0"
      />
      <span class="ml-auto font-mono text-[10px] text-(--sk-ink-muted)">
        {{ selectedRows.length }} MSR · {{ loadedCount }} loaded
      </span>
    </div>

    <div
      v-if="pending"
      class="dashboard-surface flex items-center justify-center gap-2 rounded-2xl px-4 py-12 text-sm text-(--sk-ink-muted)"
    >
      <UIcon
        name="i-lucide-loader-circle"
        class="h-4 w-4 animate-spin"
      />
      MSR raw 데이터를 불러오는 중입니다.
    </div>

    <div
      v-else-if="loadError"
      class="dashboard-surface rounded-2xl px-4 py-12 text-center text-sm text-rose-600 dark:text-rose-300"
    >
      MSR 데이터를 불러오지 못했습니다.
    </div>

    <template v-else>
      <!-- Time-series trend across the selected MSRs -->
      <UCard
        class="dashboard-surface rounded-2xl"
        :ui="{ body: 'p-3 sm:p-3', header: 'px-4 py-3 sm:px-4' }"
      >
        <template #header>
          <div class="flex items-center justify-between gap-3">
            <p class="text-[12.5px] font-semibold text-zinc-900 dark:text-zinc-100">
              시계열 추이 · {{ selectedParam || '—' }}
            </p>
            <span class="text-[10.5px] text-zinc-400">mean ± min/max band, 시간순</span>
          </div>
        </template>
        <EbeamSkewvoirTimeSeriesChart
          v-if="timeSeriesPoints.length > 0"
          :points="timeSeriesPoints"
          :parameter="selectedParam"
          :unit="selectedUnit"
        />
        <p
          v-else
          class="px-2 py-10 text-center text-sm text-(--sk-ink-muted)"
        >
          선택한 parameter에 대한 시계열 데이터가 없습니다.
        </p>
      </UCard>

      <!-- Single-MSR focus detail -->
      <UCard
        class="dashboard-surface rounded-2xl"
        :ui="{ body: 'p-3 sm:p-3', header: 'px-4 py-3 sm:px-4' }"
      >
        <template #header>
          <div class="flex flex-wrap items-center justify-between gap-2">
            <p class="text-[12.5px] font-semibold text-zinc-900 dark:text-zinc-100">
              단일 MSR 상세
            </p>
            <USelect
              v-model="focusMsrLocal"
              size="xs"
              :items="focusItems"
              class="min-w-[16rem]"
            />
          </div>
        </template>

        <div
          v-if="!focusFile"
          class="px-2 py-10 text-center text-sm text-(--sk-ink-muted)"
        >
          상세를 볼 MSR을 선택하세요.
        </div>
        <div
          v-else-if="!focusHasParam"
          class="px-2 py-10 text-center text-sm text-(--sk-ink-muted)"
        >
          이 MSR에는 {{ selectedParam }} parameter가 없습니다.
        </div>
        <div
          v-else
          class="grid grid-cols-1 gap-3 xl:grid-cols-2"
        >
          <div class="rounded-xl ring-1 ring-zinc-200 dark:ring-zinc-800">
            <p class="border-b border-zinc-100 px-3 py-2 text-[11.5px] font-medium text-(--sk-ink-muted) dark:border-zinc-800">
              Wafer map (mean per chip)
            </p>
            <EbeamSkewvoirWaferMap
              :rows="focusFile.rows"
              :parameter="selectedParam"
              :unit="selectedUnit"
            />
          </div>
          <div class="rounded-xl ring-1 ring-zinc-200 dark:ring-zinc-800">
            <p class="border-b border-zinc-100 px-3 py-2 text-[11.5px] font-medium text-(--sk-ink-muted) dark:border-zinc-800">
              CD 분포
            </p>
            <EbeamSkewvoirCdDistribution
              :rows="focusFile.rows"
              :parameter="selectedParam"
              :unit="selectedUnit"
            />
          </div>
          <div class="rounded-xl ring-1 ring-zinc-200 dark:ring-zinc-800 xl:col-span-2">
            <p class="border-b border-zinc-100 px-3 py-2 text-[11.5px] font-medium text-(--sk-ink-muted) dark:border-zinc-800">
              Sequence 추이
            </p>
            <EbeamSkewvoirSequenceTrend
              :rows="focusFile.rows"
              :parameter="selectedParam"
              :unit="selectedUnit"
            />
          </div>
        </div>
      </UCard>
    </template>
  </div>
</template>

<script setup lang="ts">
import type { MeasHistRow } from '~/composables/useMeasHistApi'
import type { MsrFileResponse } from '~/composables/useMsrFileApi'
import type { TimeSeriesPoint } from '~/components/ebeam/skewvoir/TimeSeriesChart.vue'
import { formatRecipeTimestamp } from '~/utils/recipeView'

const props = defineProps<{
  selectedRows: MeasHistRow[]
}>()

const { fetchMsrFiles } = useMsrFileApi()

const files = ref<Map<string, MsrFileResponse>>(new Map())
const pending = ref(false)
const loadError = ref(false)
const selectedParam = ref('')
const focusMsrLocal = ref('')

const selectionKey = computed(() =>
  props.selectedRows.map(r => r.msr).sort().join('|')
)

const load = async () => {
  if (props.selectedRows.length === 0) {
    files.value = new Map()
    return
  }
  pending.value = true
  loadError.value = false
  try {
    const responses = await fetchMsrFiles(
      props.selectedRows.map(r => ({
        msr: r.msr,
        className: r.class_name,
        totalImages: r.total_images
      }))
    )
    files.value = new Map(responses.map(res => [res.msr, res]))
  } catch {
    loadError.value = true
  } finally {
    pending.value = false
  }
}

watch(selectionKey, load, { immediate: true })

const loadedCount = computed(() => files.value.size)

// Union of parameters across all loaded MSR files.
const availableParams = computed(() => {
  const set = new Set<string>()
  for (const file of files.value.values()) {
    for (const summary of file.parameters) set.add(summary.parameter)
  }
  return [...set].sort()
})

const paramItems = computed(() => availableParams.value.map(p => ({ label: p, value: p })))

watch(availableParams, (params) => {
  if (params.length > 0 && !params.includes(selectedParam.value)) {
    selectedParam.value = params[0]!
  }
}, { immediate: true })

const selectedUnit = computed(() => {
  for (const file of files.value.values()) {
    const summary = file.parameters.find(p => p.parameter === selectedParam.value)
    if (summary) return summary.unit
  }
  return ''
})

// One trend point per selected MSR (at its meas_hist timestamp) for the chosen parameter.
const timeSeriesPoints = computed<TimeSeriesPoint[]>(() => {
  const points: (TimeSeriesPoint & { ts: number })[] = []
  for (const row of props.selectedRows) {
    const file = files.value.get(row.msr)
    const summary = file?.parameters.find(p => p.parameter === selectedParam.value)
    if (!summary) continue
    points.push({
      ts: new Date(row.timestamp).getTime(),
      msr: row.msr,
      label: formatRecipeTimestamp(row.timestamp),
      eqpId: row.eqp_id,
      mean: summary.mean,
      min: summary.min,
      max: summary.max,
      std: summary.std
    })
  }
  points.sort((a, b) => a.ts - b.ts)
  return points.map(({ ts: _ts, ...rest }) => rest)
})

const focusItems = computed(() =>
  props.selectedRows.map(r => ({
    label: `${formatRecipeTimestamp(r.timestamp)} · ${r.eqp_id} · ${r.lot_id}`,
    value: r.msr
  }))
)

// Keep the focus selection valid as the selection set changes.
watch(() => props.selectedRows, (rows) => {
  if (rows.length === 0) {
    focusMsrLocal.value = ''
    return
  }
  if (!rows.some(r => r.msr === focusMsrLocal.value)) {
    focusMsrLocal.value = rows[0]!.msr
  }
}, { immediate: true })

const focusFile = computed(() => files.value.get(focusMsrLocal.value) ?? null)
const focusHasParam = computed(() =>
  !!focusFile.value?.parameters.some(p => p.parameter === selectedParam.value)
)
</script>
