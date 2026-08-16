<template>
  <div class="space-y-1">
    <div class="flex items-center gap-3">
      <label class="text-sm text-(--sk-ink-muted)">tolerance</label>
      <input
        type="range"
        :min="range.min"
        :max="range.max"
        :step="range.step"
        :value="modelValue"
        class="accent-(--sk-accent)"
        @input="onInput"
      >
      <span class="tabular-nums text-sm font-medium text-(--sk-ink)">
        {{ modelValue.toFixed(3) }} nm
      </span>
      <span class="tabular-nums text-sm text-(--sk-ink-muted)">
        = CD 대비 {{ toleranceIndex.toFixed(2) }}×
      </span>
    </div>
    <!-- The knob reads in nm because the server's tolerance_range does, but the
         grouping is CD-relative. Without this line the same slider position
         would silently mean different things per cell and the screen would
         never say so. -->
    <p class="text-[11px] text-(--sk-ink-subtle)">
      슬라이더 값은 모니터 wafer {{ MONITOR_WAFER_CD_NM }} nm 기준입니다. N배화 판정은
      셀마다 그 셀의 CD로 환산해서 적용하므로, 패턴이 크면 허용치도 같은 비율로
      넓어집니다 — 예: CD 68 nm 셀에서는
      {{ effectiveToleranceNm(toleranceIndex, 68).toFixed(3) }} nm.
    </p>
  </div>
</template>

<script setup lang="ts">
import { effectiveToleranceNm, MONITOR_WAFER_CD_NM } from '~/utils/tttmLimits'

defineProps<{
  modelValue: number
  range: { min: number, max: number, step: number }
  /** The nm value read as a fraction of CD's 1% — what grouping actually uses. */
  toleranceIndex: number
}>()
const emit = defineEmits<{ 'update:modelValue': [value: number] }>()

const onInput = (e: Event) => {
  emit('update:modelValue', Number((e.target as HTMLInputElement).value))
}
</script>
