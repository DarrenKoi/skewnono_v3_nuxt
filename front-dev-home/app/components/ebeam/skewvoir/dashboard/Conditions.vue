<template>
  <div class="dashboard-surface flex flex-wrap items-center gap-x-4 gap-y-1.5 rounded-(--sk-r-card) px-4 py-2.5">
    <span class="sk-eyebrow">측정 조건</span>
    <div
      v-for="f in conditionFields"
      :key="f.label"
      class="flex flex-col gap-0.5"
    >
      <span class="sk-label">{{ f.label }}</span>
      <span class="sk-value-num max-w-[10rem] truncate">{{ f.value }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { SkewvoirAnalysis } from '~/composables/useSkewvoirAnalysis'
import { measuredRows } from '~/utils/msrRows'

const props = defineProps<{ analysis: SkewvoirAnalysis }>()

const info = computed(() => props.analysis.focusFile.value?.exe_detail_info ?? null)
// Representative measurement conditions: mag/vac/pixel are constant across a run,
// so the first measured row for the active parameter is representative.
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
</script>
