<template>
  <div class="flex flex-wrap items-baseline gap-x-3 gap-y-0.5">
    <span
      v-for="f in conditionFields"
      :key="f.label"
      class="max-w-[10rem] truncate sk-value-num"
      :title="f.label"
    >{{ f.value }}<span
      v-if="f.unit"
      class="ml-0.5 sk-label"
    >{{ f.unit }}</span></span>
  </div>
</template>

<script setup lang="ts">
import type { SkewvoirAnalysis } from '~/composables/useSkewvoirAnalysis'
import { measuredRows } from '~/utils/msrRows'

// The measurement's conditions, demoted to one line in the verdict block's
// header. They are demoted by POSITION and by dropping their labels — never by
// shrinking or greying the numbers: DESIGN.md holds a data value at ink and at
// 12px or above, and 800 V is a value however incidental it is to the verdict.
// The field name survives as a `title`, so the strip stays readable to anyone
// who does not already know that W07 is the wafer.
const props = defineProps<{ analysis: SkewvoirAnalysis }>()

const info = computed(() => props.analysis.focusFile.value?.exe_detail_info ?? null)
// Representative measurement conditions: mag/vac/pixel are constant across a run,
// so the first measured row for the active parameter is representative.
const cond = computed(() =>
  measuredRows(props.analysis.siteRows.value).find(r => r.parameter === props.analysis.activeParam.value) ?? null
)

// `unit` is split from `value` rather than concatenated into it so the unit can
// take the muted 11px label tier while the number it qualifies stays ink at 12px.
const conditionFields = computed(() => [
  { label: 'Wafer', value: info.value?.wafer_id ?? '—', unit: '' },
  { label: 'Process', value: info.value?.process ?? '—', unit: '' },
  { label: 'Mag', value: cond.value ? cond.value.meas_condition_mag.toLocaleString() : '—', unit: cond.value ? '×' : '' },
  { label: 'Vacc', value: cond.value ? String(cond.value.meas_condition_vac) : '—', unit: cond.value ? 'V' : '' },
  { label: 'Pixel', value: cond.value?.meas_condition_pixel ?? '—', unit: cond.value ? 'px' : '' }
])
</script>
