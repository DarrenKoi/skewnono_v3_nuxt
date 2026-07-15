<template>
  <EbeamSkewvoirPanelFrame
    v-model="tab"
    :title="tab === '조건' ? '측정 조건 & 정렬' : tab === 'SEM' ? 'SEM Image' : 'Distribution'"
    :meta="meta"
    :toggles="['Distribution', 'SEM', '조건']"
    icon="i-lucide-bar-chart-3"
    body-class="flex flex-col"
  >
    <!-- Contextual sub-mode control for the active tab -->
    <template #actions>
      <div
        v-if="tab === 'Distribution'"
        class="inline-flex items-center gap-0.5 rounded-(--sk-r-chip) bg-(--sk-chip-bg) p-0.5"
      >
        <button
          v-for="opt in ['Hist', 'Box', 'Violin']"
          :key="opt"
          type="button"
          class="rounded-[6px] px-2 py-0.5 font-mono text-[10.5px] font-medium transition-colors"
          :class="opt === distMode
            ? 'bg-(--sk-surface) text-zinc-900 shadow-sm dark:text-zinc-100'
            : 'text-(--sk-ink-subtle) hover:text-zinc-700 dark:hover:text-zinc-200'"
          @click="distMode = opt"
        >
          {{ opt }}
        </button>
      </div>
      <div
        v-else-if="tab === 'SEM'"
        class="inline-flex items-center gap-0.5 rounded-(--sk-r-chip) bg-(--sk-chip-bg) p-0.5"
      >
        <button
          v-for="opt in ['Single', '4-up']"
          :key="opt"
          type="button"
          class="rounded-[6px] px-2 py-0.5 font-mono text-[10.5px] font-medium transition-colors"
          :class="opt === semMode
            ? 'bg-(--sk-surface) text-zinc-900 shadow-sm dark:text-zinc-100'
            : 'text-(--sk-ink-subtle) hover:text-zinc-700 dark:hover:text-zinc-200'"
          @click="semMode = opt"
        >
          {{ opt }}
        </button>
      </div>
    </template>

    <!-- Loading -->
    <div
      v-if="analysis.focusPending.value"
      class="flex flex-1 items-center justify-center gap-2 text-[12px] text-(--sk-ink-muted)"
    >
      <UIcon
        name="i-lucide-loader-circle"
        class="h-4 w-4 animate-spin"
      />
      불러오는 중…
    </div>

    <!-- Distribution -->
    <template v-else-if="tab === 'Distribution'">
      <EbeamSkewvoirDistributionChart
        v-if="distHasData"
        :rows="analysis.siteRows.value"
        :parameter="analysis.activeParam.value"
        :unit="analysis.activeUnit.value"
        :mode="distMode"
      />
      <div
        v-else
        class="flex flex-1 items-center justify-center text-[12px] text-(--sk-ink-subtle)"
      >
        {{ analysis.activeParam.value }} 데이터가 없습니다.
      </div>
    </template>

    <!-- SEM Image -->
    <template v-else-if="tab === 'SEM'">
      <div
        v-if="!images.length"
        class="flex flex-1 items-center justify-center text-[12px] text-(--sk-ink-subtle)"
      >
        이미지가 없습니다.
      </div>
      <div
        v-else-if="semMode === 'Single'"
        class="flex flex-1 items-center justify-center overflow-hidden"
      >
        <img
          :src="msrImageUrl(images[0]!)"
          :alt="images[0]"
          class="max-h-full max-w-full rounded-(--sk-r-chip) border border-(--sk-border)"
        >
      </div>
      <div
        v-else
        class="grid min-h-0 flex-1 grid-cols-2 content-start gap-1.5 overflow-auto"
      >
        <img
          v-for="img in images.slice(0, 4)"
          :key="img"
          :src="msrImageUrl(img)"
          :alt="img"
          class="w-full rounded-(--sk-r-chip) border border-(--sk-border)"
        >
      </div>
    </template>

    <!-- 측정 조건 & 정렬 -->
    <div
      v-else
      class="min-h-0 flex-1 space-y-3 overflow-auto"
    >
      <dl class="space-y-1.5 text-[11.5px]">
        <div
          v-for="f in conditionFields"
          :key="f.label"
          class="flex items-baseline justify-between gap-2 border-b border-(--sk-border-soft) pb-1"
        >
          <dt class="text-(--sk-ink-muted)">
            {{ f.label }}
          </dt>
          <dd class="truncate font-mono text-zinc-800 dark:text-zinc-200">
            {{ f.value }}
          </dd>
        </div>
      </dl>
      <div class="space-y-1.5 text-[11.5px]">
        <div
          v-for="a in alignRows"
          :key="a.key"
          class="flex items-baseline justify-between gap-2 border-b border-(--sk-border-soft) pb-1"
        >
          <dt class="font-mono text-(--sk-ink-muted)">
            {{ a.key }}
          </dt>
          <dd class="truncate font-mono text-zinc-800 dark:text-zinc-200">
            {{ a.method }} · {{ a.offset }} <span class="text-(--sk-ink-subtle)">[{{ a.score }}]</span>
          </dd>
        </div>
        <p class="pt-0.5 font-mono text-[10px] text-(--sk-ink-subtle)">
          score: 모니터링만 · 비교 불가
        </p>
      </div>
    </div>
  </EbeamSkewvoirPanelFrame>
</template>

<script setup lang="ts">
import type { SkewvoirAnalysis } from '~/composables/useSkewvoirAnalysis'
import { isMeasuredRow, measuredRows } from '~/utils/msrRows'

const props = defineProps<{ analysis: SkewvoirAnalysis }>()

const { msrImageUrl } = useMsrFileApi()

const tab = ref<'Distribution' | 'SEM' | '조건'>('Distribution')
const distMode = ref('Hist')
const semMode = ref('Single')

// --- Distribution ---
const distHasData = computed(() =>
  props.analysis.siteRows.value.some(r => r.parameter === props.analysis.activeParam.value && isMeasuredRow(r))
)

// --- SEM image — reorders so a focused point's micrograph leads (Single view) ---
const images = computed(() => {
  const rows = measuredRows(props.analysis.siteRows.value).filter(r => r.parameter === props.analysis.activeParam.value)
  const focused = props.analysis.focusedSequence.value
  const ordered = focused != null
    ? [...rows].sort((a, b) => (a.sequence === focused ? -1 : 0) - (b.sequence === focused ? -1 : 0))
    : rows
  const seen = new Set<string>()
  const out: string[] = []
  for (const r of ordered) {
    const name = r.mp_image_name_01
    if (name && !seen.has(name)) {
      seen.add(name)
      out.push(name)
    }
  }
  return out
})

// --- 측정 조건 & 정렬 ---
const info = computed(() => props.analysis.focusFile.value?.exe_detail_info ?? null)
const cond = computed(() =>
  measuredRows(props.analysis.siteRows.value).find(r => r.parameter === props.analysis.activeParam.value) ?? null
)
const conditionFields = computed(() => [
  { label: 'Wafer', value: info.value?.wafer_id ?? '—' },
  { label: 'Process', value: info.value?.process ?? '—' },
  { label: 'Mag', value: cond.value ? `${cond.value.meas_condition_mag.toLocaleString()} ×` : '—' },
  { label: 'Vacc', value: cond.value ? `${cond.value.meas_condition_vac} V` : '—' },
  { label: 'Pixel', value: cond.value?.meas_condition_pixel ?? '—' }
])
const alignRows = computed(() => {
  const a = props.analysis.focusFile.value?.alignment
  if (!a) return []
  return Object.entries(a.offset).map(([key, tuple]) => ({
    key: `ALIGN ${key}`,
    method: tuple[0],
    offset: `${tuple[1]}, ${tuple[2]}`,
    score: a.score[key] ?? '—'
  }))
})

// Tab-specific meta line in the panel header.
const meta = computed(() => {
  if (tab.value === 'Distribution') {
    const s = props.analysis.activeSummary.value
    return s ? `μ ${s.mean.toFixed(3)} · 3σ ${(s.std * 3).toFixed(3)}` : props.analysis.activeParam.value
  }
  if (tab.value === 'SEM') {
    const seq = props.analysis.focusedSequence.value
    return seq != null ? `seq ${seq}` : `${images.value.length} images`
  }
  return props.analysis.focusFile.value?.exe_detail_info?.recipe_name ?? '—'
})
</script>
