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
          <div class="flex flex-wrap items-center justify-between gap-2">
            <p class="text-[12.5px] font-semibold text-zinc-900 dark:text-zinc-100">
              시계열 추이 · {{ selectedParam || '—' }}
            </p>
            <span class="font-mono text-[10.5px] text-(--sk-ink-muted)">
              주의 {{ anomalySummary.watch }} · 이상 {{ anomalySummary.abnormal }} / {{ timeSeriesPoints.length }} MSR
            </span>
          </div>
        </template>
        <div class="mb-2 flex flex-wrap items-center gap-2">
          <USelect
            v-model="anomalyCfg.method"
            size="xs"
            :items="[{ label: '범위(%)', value: 'range' }, { label: '표준편차(σ) · 진단', value: 'stddev' }]"
            class="min-w-[11rem]"
          />
          <template v-if="anomalyCfg.method === 'range'">
            <label class="flex items-center gap-1 font-mono text-[10px] text-(--sk-ink-muted)">
              주의 ±<UInput
                v-model.number="anomalyCfg.range.watchPct"
                type="number"
                size="xs"
                class="w-14"
              />%
            </label>
            <label class="flex items-center gap-1 font-mono text-[10px] text-(--sk-ink-muted)">
              이상 ±<UInput
                v-model.number="anomalyCfg.range.abnormalPct"
                type="number"
                size="xs"
                class="w-14"
              />%
            </label>
          </template>
          <template v-else>
            <label class="flex items-center gap-1 font-mono text-[10px] text-(--sk-ink-muted)">
              주의 ±<UInput
                v-model.number="anomalyCfg.stddev.watchK"
                type="number"
                size="xs"
                class="w-14"
              />σ
            </label>
            <label class="flex items-center gap-1 font-mono text-[10px] text-(--sk-ink-muted)">
              이상 ±<UInput
                v-model.number="anomalyCfg.stddev.abnormalK"
                type="number"
                size="xs"
                class="w-14"
              />σ
            </label>
          </template>
          <SkAnomalyLegend
            class="ml-auto"
            :method="anomalyCfg.method"
            :range="anomalyCfg.range"
            :stddev="anomalyCfg.stddev"
          />
        </div>
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

      <!-- FDC drift, CD↔FDC correlation, per-MSR FDC status + hardware x-ref -->
      <EbeamSkewvoirFdcAnalysis
        v-if="loadedCount > 0"
        :selected-rows="selectedRows"
        :files="files"
        :cd-param="selectedParam"
        :cd-unit="selectedUnit"
        :tool-type="toolType"
      />

      <!-- Single-MSR focus detail -->
      <UCard
        class="dashboard-surface rounded-2xl"
        :ui="{ body: 'p-3 sm:p-3', header: 'px-4 py-3 sm:px-4' }"
      >
        <template #header>
          <div class="flex flex-wrap items-center justify-between gap-2">
            <div class="flex items-center gap-2">
              <p class="text-[12.5px] font-semibold text-zinc-900 dark:text-zinc-100">
                단일 MSR 상세
              </p>
              <SkAnomalyBadge :verdict="focusVerdict" />
            </div>
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
          <div class="rounded-xl ring-1 ring-zinc-200 dark:ring-zinc-800 xl:col-span-2">
            <div class="flex items-center justify-between border-b border-zinc-100 px-3 py-1.5 dark:border-zinc-800">
              <p class="text-[11.5px] font-medium text-(--sk-ink-muted)">
                FDC sequence 추이 (측정 중 장비 거동)
              </p>
              <USelect
                v-model="focusFdcParam"
                size="xs"
                :items="focusFdcItems"
                class="min-w-[10rem]"
              />
            </div>
            <EbeamSkewvoirFdcSequenceTrend
              v-if="focusFdcParam"
              :file="focusFile"
              :param="focusFdcParam"
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
import {
  peerVerdicts, combineVerdicts, DEFAULT_RANGE, DEFAULT_STDDEV,
  type CombinedVerdict, type MethodConfig
} from '~/utils/anomaly'

const props = defineProps<{
  selectedRows: MeasHistRow[]
}>()

// tool_type is uniform across the picked rows (the picker is per-tool), so the
// first row tells the FDC hardware cross-ref which tool family to query.
const toolType = computed(() => props.selectedRows[0]?.tool_type ?? 'cd-sem')

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

// Active scoring method + thresholds. Range is the authoritative default;
// stddev is a diagnostic lens. Persisted across remounts via useState.
const anomalyCfg = useState<MethodConfig>('skewvoir-anomaly-cfg', () => ({
  method: 'range',
  range: { ...DEFAULT_RANGE },
  stddev: { ...DEFAULT_STDDEV }
}))

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

  // Peer verdicts under the active method: level (mean) and spread (std),
  // each judged leave-one-out against the rest of the selection.
  const meanV = peerVerdicts(points.map(p => p.mean), { config: anomalyCfg.value, metric: 'mean' })
  const spreadV = peerVerdicts(points.map(p => p.std), { config: anomalyCfg.value, metric: 'spread', tag: '산포' })

  return points.map(({ ts: _ts, ...rest }, i) => ({
    ...rest,
    verdict: combineVerdicts([meanV[i]!, spreadV[i]!]) as CombinedVerdict
  }))
})

const anomalySummary = computed(() => {
  let watch = 0, abnormal = 0
  for (const p of timeSeriesPoints.value) {
    if (p.verdict?.severity === 'abnormal') abnormal++
    else if (p.verdict?.severity === 'watch') watch++
  }
  return { watch, abnormal }
})

// Verdict for the currently-focused MSR, for the SkAnomalyBadge in the detail card.
const focusVerdict = computed<CombinedVerdict | null>(() =>
  timeSeriesPoints.value.find(p => p.msr === focusMsrLocal.value)?.verdict ?? null
)

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

// FDC param traced across sequences for the focused MSR; defaults to whichever
// param drifted most in that measurement.
const focusFdcParam = ref('')
const focusFdcItems = computed(() =>
  (focusFile.value?.fdc_params ?? []).map(p => ({ label: p.name, value: p.name }))
)
watch(focusFile, (file) => {
  if (!file || file.fdc_params.length === 0) {
    focusFdcParam.value = ''
    return
  }
  if (!file.fdc_params.some(p => p.name === focusFdcParam.value)) {
    focusFdcParam.value = [...file.fdc_params]
      .sort((a, b) => b.drift_sigma - a.drift_sigma)[0]!.name
  }
}, { immediate: true })
</script>
