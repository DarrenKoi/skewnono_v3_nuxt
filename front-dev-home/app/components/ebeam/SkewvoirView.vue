<template>
  <div class="space-y-4">
    <EbeamFeatureHeader
      :eyebrow="`${toolLabel} · 스큐보아`"
      :stats="headerStats"
      subtitle="측정 이력에서 MSR을 다중 선택하면 parameter별 시계열 추이를 분석합니다. 단일 MSR을 선택하면 wafer map·분포·sequence 추이를 확인할 수 있습니다."
      title="스큐보아 (Skewvoir)"
    />

    <div
      v-if="pending"
      class="dashboard-surface flex items-center justify-center gap-2 rounded-2xl px-4 py-12 text-sm text-(--sk-ink-muted)"
    >
      <UIcon
        name="i-lucide-loader-circle"
        class="h-4 w-4 animate-spin"
      />
      측정 이력을 불러오는 중입니다.
    </div>
    <div
      v-else-if="error"
      class="dashboard-surface rounded-2xl px-4 py-12 text-center"
    >
      <p class="text-sm font-medium text-rose-600 dark:text-rose-300">
        측정 이력을 불러오지 못했습니다.
      </p>
      <UButton
        class="mt-3"
        size="sm"
        color="neutral"
        variant="outline"
        icon="i-lucide-refresh-cw"
        label="Retry"
        @click="refresh()"
      />
    </div>

    <template v-else>
      <EbeamSkewvoirMsrPicker
        v-model="selectedMsrs"
        :rows="rows"
      />

      <EbeamSkewvoirAnalyzePanel
        v-if="selectedRows.length > 0"
        :selected-rows="selectedRows"
      />
      <div
        v-else
        class="dashboard-surface rounded-2xl px-6 py-12 text-center"
      >
        <UIcon
          name="i-lucide-mouse-pointer-click"
          class="mx-auto h-6 w-6 text-zinc-400"
        />
        <p class="mt-2 text-sm font-medium text-zinc-700 dark:text-zinc-200">
          분석할 MSR을 선택하세요.
        </p>
        <p class="mt-1 text-[12px] text-(--sk-ink-muted)">
          여러 건을 선택하면 시계열 추이가, 한 건을 선택하면 상세 분석이 표시됩니다.
        </p>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import type { MeasHistResponse, MeasHistRow, MeasHistToolType } from '~/composables/useMeasHistApi'

const props = defineProps<{
  toolLabel: string
  toolType: MeasHistToolType
}>()

const { fetchMeasHist } = useMeasHistApi()

const selectedMsrs = ref<string[]>([])

const cacheKey = computed(() => `skewvoir-meas-hist:${props.toolType}`)

const { data, pending, error, refresh } = await useAsyncData<MeasHistResponse>(
  () => cacheKey.value,
  () => fetchMeasHist({ toolType: props.toolType }),
  {
    watch: [cacheKey],
    default: () => ({ tool_type: props.toolType, fab_name: null, recipe_name: null, total: 0, rows: [] }),
    getCachedData: (key, nuxtApp) => nuxtApp.payload.data[key] ?? nuxtApp.static.data[key]
  }
)

// Only MSRs with raw data present are analyzable (msr_check === 'Yes').
const rows = computed<MeasHistRow[]>(() =>
  (data.value?.rows ?? []).filter(row => row.msr_check === 'Yes')
)

const rowByMsr = computed(() => new Map(rows.value.map(row => [row.msr, row])))

const selectedRows = computed<MeasHistRow[]>(() =>
  selectedMsrs.value
    .map(msr => rowByMsr.value.get(msr))
    .filter((row): row is MeasHistRow => row != null)
)

// Drop selections that no longer exist when the tool's row set changes.
watch(rows, (next) => {
  const available = new Set(next.map(row => row.msr))
  const pruned = selectedMsrs.value.filter(msr => available.has(msr))
  if (pruned.length !== selectedMsrs.value.length) {
    selectedMsrs.value = pruned
  }
})

const headerStats = computed(() => [
  { label: '분석 가능 MSR', value: rows.value.length.toLocaleString(), tone: 'neutral' as const },
  { label: '선택', value: selectedRows.value.length.toLocaleString(), tone: 'neutral' as const }
])
</script>
