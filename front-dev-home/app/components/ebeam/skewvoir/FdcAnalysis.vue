<template>
  <div class="space-y-3">
    <!-- ── FDC drift time-series across the selected MSRs ──────────────── -->
    <UCard
      class="dashboard-surface rounded-2xl"
      :ui="{ body: 'p-3 sm:p-3', header: 'px-4 py-3 sm:px-4' }"
    >
      <template #header>
        <div class="flex flex-wrap items-center justify-between gap-2">
          <div>
            <p class="text-[12.5px] font-semibold text-zinc-900 dark:text-zinc-100">
              FDC 변곡점 추이 · drift (σ)
            </p>
            <p class="text-[10.5px] text-(--sk-ink-muted)">
              장비 이상거동 파라미터를 σ 단위로 정규화 · ±2σ warning · ±3.5σ bad
            </p>
          </div>
          <div class="flex items-center gap-2">
            <span class="font-mono text-[10.5px] text-(--sk-ink-muted)">
              warning {{ healthSummary.warning }} · bad {{ healthSummary.bad }} / {{ timeOrderedRows.length }} MSR
            </span>
          </div>
        </div>
      </template>

      <!-- FDC param toggle chips -->
      <div class="mb-2 flex flex-wrap items-center gap-1.5">
        <button
          v-for="name in fdcNames"
          :key="name"
          type="button"
          class="inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] transition"
          :class="selectedFdcParams.includes(name)
            ? 'border-transparent text-white'
            : 'border-zinc-200 text-(--sk-ink-muted) hover:bg-zinc-500/5 dark:border-zinc-700'"
          :style="selectedFdcParams.includes(name) ? { backgroundColor: colorFor(name) } : {}"
          @click="toggleFdcParam(name)"
        >
          <span
            v-if="!selectedFdcParams.includes(name)"
            class="h-2 w-2 rounded-full"
            :style="{ backgroundColor: colorFor(name) }"
          />
          {{ name }}
        </button>
      </div>

      <EbeamSkewvoirFdcTimeSeriesChart
        v-if="trendSeries.length > 0 && timeOrderedRows.length > 0"
        :points="trendPoints"
        :series="trendSeries"
      />
      <p
        v-else
        class="px-2 py-10 text-center text-sm text-(--sk-ink-muted)"
      >
        표시할 FDC 파라미터를 한 개 이상 선택하세요.
      </p>
    </UCard>

    <!-- ── CD ↔ FDC correlation ───────────────────────────────────────── -->
    <UCard
      class="dashboard-surface rounded-2xl"
      :ui="{ body: 'p-3 sm:p-3', header: 'px-4 py-3 sm:px-4' }"
    >
      <template #header>
        <div class="flex flex-wrap items-center justify-between gap-2">
          <div>
            <p class="text-[12.5px] font-semibold text-zinc-900 dark:text-zinc-100">
              CD ↔ FDC 상관
            </p>
            <p class="text-[10.5px] text-(--sk-ink-muted)">
              MSR별 {{ cdParam || 'CD' }} 평균 vs FDC drift — CD 변동이 장비 상태와 함께 움직이는지 확인
            </p>
          </div>
          <USelect
            v-model="scatterFdcParam"
            size="xs"
            :items="fdcSelectItems"
            class="min-w-[10rem]"
          />
        </div>
      </template>

      <div
        v-if="scatterPoints.length >= 3"
        class="grid grid-cols-1 gap-3 lg:grid-cols-[1fr_auto]"
      >
        <EbeamSkewvoirFdcScatter
          :points="scatterPoints"
          :x-name="cdParam || 'CD'"
          :x-unit="cdUnit"
          :y-name="`${scatterFdcParam} drift`"
          y-unit="σ"
          :fit="scatterFit"
        />
        <div class="flex flex-row gap-4 lg:flex-col lg:justify-center">
          <div>
            <p class="font-mono text-[10px] uppercase tracking-wide text-(--sk-ink-muted)">
              Pearson r
            </p>
            <p
              class="font-mono text-2xl font-semibold tabular-nums"
              :class="correlationTone"
            >
              {{ pearson != null ? pearson.toFixed(2) : '—' }}
            </p>
            <p class="mt-0.5 text-[11px] text-(--sk-ink-muted)">
              {{ correlationLabel }}
            </p>
          </div>
          <div class="text-[11px] text-(--sk-ink-muted)">
            <p>n = {{ scatterPoints.length }} MSR</p>
            <p class="mt-1">
              <span class="inline-block h-2 w-2 rounded-full bg-green-500" /> ok ·
              <span class="inline-block h-2 w-2 rounded-full bg-amber-500" /> warn ·
              <span class="inline-block h-2 w-2 rounded-full bg-red-500" /> bad
            </p>
          </div>
        </div>
      </div>
      <p
        v-else
        class="px-2 py-8 text-center text-sm text-(--sk-ink-muted)"
      >
        상관 분석에는 {{ cdParam || 'CD' }} parameter를 가진 MSR이 3건 이상 필요합니다. 같은 recipe/parameter의 MSR을 함께 선택하세요.
      </p>
    </UCard>

    <!-- ── Per-MSR FDC status + hardware cross-reference ──────────────── -->
    <div class="grid grid-cols-1 gap-3 xl:grid-cols-2">
      <UCard
        class="dashboard-surface rounded-2xl"
        :ui="{ body: 'p-0 sm:p-0', header: 'px-4 py-3 sm:px-4' }"
      >
        <template #header>
          <p class="text-[12.5px] font-semibold text-zinc-900 dark:text-zinc-100">
            MSR별 FDC 상태
          </p>
        </template>
        <div class="max-h-80 overflow-auto">
          <table class="w-full text-[11.5px]">
            <thead class="sticky top-0 bg-(--sk-surface) text-left text-[10px] uppercase tracking-wide text-(--sk-ink-muted)">
              <tr>
                <th class="px-3 py-1.5 font-medium">
                  time
                </th>
                <th class="px-2 py-1.5 font-medium">
                  eqp
                </th>
                <th class="px-2 py-1.5 font-medium">
                  worst FDC
                </th>
                <th class="px-2 py-1.5 text-right font-medium">
                  drift
                </th>
                <th class="px-3 py-1.5 font-medium">
                  status
                </th>
              </tr>
            </thead>
            <tbody class="font-mono tabular-nums">
              <tr
                v-for="r in msrStatusRows"
                :key="r.msr"
                class="border-t border-zinc-100 dark:border-zinc-800"
              >
                <td class="px-3 py-1.5 text-zinc-600 dark:text-zinc-300">
                  {{ r.time }}
                </td>
                <td class="px-2 py-1.5 font-semibold text-zinc-800 dark:text-zinc-100">
                  {{ r.eqpId }}
                </td>
                <td class="px-2 py-1.5 text-zinc-600 dark:text-zinc-300">
                  {{ r.worstName }}
                </td>
                <td class="px-2 py-1.5 text-right text-zinc-600 dark:text-zinc-300">
                  {{ r.worstDrift.toFixed(1) }}σ
                </td>
                <td class="px-3 py-1.5">
                  <UBadge
                    :label="r.status"
                    :color="r.status === 'bad' ? 'error' : r.status === 'warning' ? 'warning' : 'success'"
                    size="xs"
                    variant="subtle"
                  />
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </UCard>

      <UCard
        class="dashboard-surface rounded-2xl"
        :ui="{ body: 'p-3 sm:p-3', header: 'px-4 py-3 sm:px-4' }"
      >
        <template #header>
          <div class="flex flex-wrap items-center justify-between gap-2">
            <p class="text-[12.5px] font-semibold text-zinc-900 dark:text-zinc-100">
              장비 상시 FDC 교차확인
            </p>
            <USelect
              v-model="hardwareEqp"
              size="xs"
              :items="eqpItems"
              class="min-w-[9rem]"
            />
          </div>
        </template>

        <div
          v-if="hwPending"
          class="flex items-center justify-center gap-2 py-10 text-sm text-(--sk-ink-muted)"
        >
          <UIcon
            name="i-lucide-loader-circle"
            class="h-4 w-4 animate-spin"
          />
          장비 FDC 모니터링 조회 중…
        </div>
        <div
          v-else-if="!hardware || hardware.available === false"
          class="py-10 text-center text-sm text-(--sk-ink-muted)"
        >
          {{ hardwareEqp }} 장비의 상시 FDC 데이터가 없습니다.
        </div>
        <div v-else>
          <p class="mb-2 text-[11.5px] text-(--sk-ink-muted)">
            {{ hardware.summary }}
          </p>
          <div class="grid grid-cols-2 gap-2">
            <div
              v-for="card in hardware.cards"
              :key="card.key"
              class="rounded-xl ring-1 ring-zinc-200 px-3 py-2 dark:ring-zinc-800"
            >
              <p class="text-[10px] uppercase tracking-wide text-(--sk-ink-muted)">
                {{ card.label }}
              </p>
              <p class="font-mono text-[13px] font-semibold tabular-nums text-zinc-800 dark:text-zinc-100">
                {{ card.value }}<span
                  v-if="card.unit"
                  class="ml-0.5 text-[10px] font-normal text-(--sk-ink-muted)"
                >{{ card.unit }}</span>
              </p>
            </div>
          </div>
          <p class="mt-2 text-[10.5px] text-(--sk-ink-muted)">
            측정 pickle FDC(이 화면)와 장비 상시 FDC 모니터링을 비교하면, CD 이상이 측정 순간의 문제인지 장비 상시 열화인지 구분할 수 있습니다.
          </p>
        </div>
      </UCard>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { MeasHistRow, MeasHistToolType } from '~/composables/useMeasHistApi'
import type { MsrFileResponse, FdcParamSummary, FdcStatus } from '~/composables/useMsrFileApi'
import type { HardwarePayload } from '~/composables/useHardwareApi'
import type { FdcTrendPoint, FdcTrendSeries } from '~/components/ebeam/skewvoir/FdcTimeSeriesChart.vue'
import type { FdcScatterPoint } from '~/components/ebeam/skewvoir/FdcScatter.vue'
import { formatRecipeTimestamp } from '~/utils/recipeView'
import { pearson as pearsonOf, fitLine } from '~/utils/stats'

const props = defineProps<{
  selectedRows: MeasHistRow[]
  files: Map<string, MsrFileResponse>
  cdParam: string
  cdUnit: string
  toolType: MeasHistToolType
}>()

const PALETTE = [
  '#2563eb', '#dc2626', '#16a34a', '#d97706', '#7c3aed',
  '#0891b2', '#db2777', '#65a30d', '#475569', '#ea580c'
]

// Signed drift in σ: the backend's drift_sigma is unsigned magnitude, but we can
// recover the direction from (mean - nominal). Sign × magnitude = signed σ.
const signedSigma = (summary: FdcParamSummary): number => {
  const dir = Math.sign(summary.mean - summary.nominal) || 1
  return dir * summary.drift_sigma
}

const worstParam = (file: MsrFileResponse): FdcParamSummary | null =>
  file.fdc_params.reduce<FdcParamSummary | null>(
    (worst, p) => (worst == null || p.drift_sigma > worst.drift_sigma ? p : worst),
    null
  )

// MSRs that actually loaded, in time order — the x-axis for every cross-MSR view.
const timeOrderedRows = computed(() =>
  props.selectedRows
    .filter(r => props.files.has(r.msr))
    .slice()
    .sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime())
)

// All FDC param names, in the backend's category order (stable across MSRs).
const fdcNames = computed(() => {
  for (const r of timeOrderedRows.value) {
    const file = props.files.get(r.msr)
    if (file) return file.fdc_params.map(p => p.name)
  }
  return []
})

const colorFor = (name: string): string => {
  const i = fdcNames.value.indexOf(name)
  return PALETTE[i % PALETTE.length] ?? '#64748b'
}

const fdcSelectItems = computed(() => fdcNames.value.map(n => ({ label: n, value: n })))

// Default the trend to the 3 params with the largest drift across the selection,
// so the most actionable signals show without the user hunting for them.
const selectedFdcParams = ref<string[]>([])

const maxDriftByParam = computed(() => {
  const map = new Map<string, number>()
  for (const r of timeOrderedRows.value) {
    const file = props.files.get(r.msr)
    if (!file) continue
    for (const p of file.fdc_params) {
      map.set(p.name, Math.max(map.get(p.name) ?? 0, p.drift_sigma))
    }
  }
  return map
})

watch([fdcNames, maxDriftByParam], () => {
  if (fdcNames.value.length === 0) return
  // Keep any still-valid prior selection; otherwise seed from the worst-3.
  const valid = selectedFdcParams.value.filter(n => fdcNames.value.includes(n))
  if (valid.length > 0) {
    selectedFdcParams.value = valid
    return
  }
  selectedFdcParams.value = [...fdcNames.value]
    .sort((a, b) => (maxDriftByParam.value.get(b) ?? 0) - (maxDriftByParam.value.get(a) ?? 0))
    .slice(0, 3)
}, { immediate: true })

const toggleFdcParam = (name: string) => {
  selectedFdcParams.value = selectedFdcParams.value.includes(name)
    ? selectedFdcParams.value.filter(n => n !== name)
    : [...selectedFdcParams.value, name]
}

const trendPoints = computed<FdcTrendPoint[]>(() =>
  timeOrderedRows.value.map(r => ({
    msr: r.msr,
    label: formatRecipeTimestamp(r.timestamp),
    eqpId: r.eqp_id
  }))
)

const trendSeries = computed<FdcTrendSeries[]>(() =>
  selectedFdcParams.value.map(name => ({
    name,
    color: colorFor(name),
    data: timeOrderedRows.value.map((r) => {
      const file = props.files.get(r.msr)
      const summary = file?.fdc_params.find(p => p.name === name)
      return summary ? Number(signedSigma(summary).toFixed(2)) : null
    })
  }))
)

const healthSummary = computed(() => {
  let warning = 0
  let bad = 0
  for (const r of timeOrderedRows.value) {
    const file = props.files.get(r.msr)
    const worst = file ? worstParam(file) : null
    if (worst?.status === 'bad') bad++
    else if (worst?.status === 'warning') warning++
  }
  return { warning, bad }
})

const msrStatusRows = computed(() =>
  timeOrderedRows.value.map((r) => {
    const file = props.files.get(r.msr)!
    const worst = worstParam(file)
    return {
      msr: r.msr,
      time: formatRecipeTimestamp(r.timestamp),
      eqpId: r.eqp_id,
      worstName: worst?.name ?? '—',
      worstDrift: worst?.drift_sigma ?? 0,
      status: (worst?.status ?? 'ok') as FdcStatus
    }
  })
)

// ── CD ↔ FDC correlation ───────────────────────────────────────────────────
const scatterFdcParam = ref('')
watch(fdcNames, (names) => {
  if (names.length > 0 && !names.includes(scatterFdcParam.value)) {
    // Default to the most-drifting param — the one most worth correlating.
    scatterFdcParam.value = [...names]
      .sort((a, b) => (maxDriftByParam.value.get(b) ?? 0) - (maxDriftByParam.value.get(a) ?? 0))[0]!
  }
}, { immediate: true })

const scatterPoints = computed<FdcScatterPoint[]>(() => {
  const points: FdcScatterPoint[] = []
  for (const r of timeOrderedRows.value) {
    const file = props.files.get(r.msr)
    const cd = file?.parameters.find(p => p.parameter === props.cdParam)
    const fdc = file?.fdc_params.find(p => p.name === scatterFdcParam.value)
    if (!cd || !fdc) continue
    points.push({
      x: cd.mean,
      y: Number(signedSigma(fdc).toFixed(2)),
      label: formatRecipeTimestamp(r.timestamp),
      eqpId: r.eqp_id,
      status: fdc.status
    })
  }
  return points
})

// Shared pearson already floors at n >= 3: with n = 2 Pearson r is trivially
// ±1 (two points are always perfectly collinear), which would overstate a
// non-existent relationship. It returns null (not 0) when undefined.
const pearson = computed<number | null>(() => pearsonOf(scatterPoints.value.map(p => [p.x, p.y])))

const scatterFit = computed<[[number, number], [number, number]] | null>(() =>
  fitLine(scatterPoints.value.map(p => [p.x, p.y]))
)

const correlationTone = computed(() => {
  const r = pearson.value
  if (r == null) return 'text-(--sk-ink-muted)'
  const a = Math.abs(r)
  if (a >= 0.6) return 'text-rose-600 dark:text-rose-400'
  if (a >= 0.3) return 'text-amber-600 dark:text-amber-400'
  return 'text-zinc-600 dark:text-zinc-300'
})

const correlationLabel = computed(() => {
  const r = pearson.value
  if (r == null) return '데이터 부족'
  const a = Math.abs(r)
  const strength = a >= 0.6 ? '강한' : a >= 0.3 ? '약한' : '미미한'
  const dir = r > 0 ? '양' : r < 0 ? '음' : ''
  return a < 0.1 ? '상관 없음' : `${strength} ${dir}의 상관`
})

// ── Hardware cross-reference (tool's standalone FDC monitoring) ─────────────
const hardwareEqp = ref('')
const eqpItems = computed(() => {
  const seen = new Set<string>()
  const items: { label: string, value: string }[] = []
  // Default the eqp to the worst MSR's tool, sorted so abnormal tools surface first.
  const ranked = [...timeOrderedRows.value].sort((a, b) => {
    const fa = worstParam(props.files.get(a.msr)!)?.drift_sigma ?? 0
    const fb = worstParam(props.files.get(b.msr)!)?.drift_sigma ?? 0
    return fb - fa
  })
  for (const r of ranked) {
    if (seen.has(r.eqp_id)) continue
    seen.add(r.eqp_id)
    items.push({ label: r.eqp_id, value: r.eqp_id })
  }
  return items
})

watch(eqpItems, (items) => {
  if (items.length > 0 && !items.some(i => i.value === hardwareEqp.value)) {
    hardwareEqp.value = items[0]!.value
  }
}, { immediate: true })

const fabForEqp = computed(() =>
  props.selectedRows.find(r => r.eqp_id === hardwareEqp.value)?.fab_name ?? undefined
)

const { fetchService } = useHardwareApi()
const hardware = ref<HardwarePayload | null>(null)
const hwPending = ref(false)

watch([hardwareEqp, () => props.toolType], async ([eqp, toolType]) => {
  if (!eqp) {
    hardware.value = null
    return
  }
  hwPending.value = true
  try {
    hardware.value = await fetchService({
      toolType,
      service: 'fdc',
      eqpId: eqp,
      fabName: fabForEqp.value
    })
  } catch {
    hardware.value = null
  } finally {
    hwPending.value = false
  }
}, { immediate: true })
</script>
