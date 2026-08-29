<template>
  <div>
    <div class="flex items-baseline justify-between gap-2">
      <label
        :for="id"
        class="sk-label"
      >TOLERANCE</label>
      <span class="font-mono text-sm font-semibold tabular-nums text-(--sk-ink)">
        {{ modelValue.toFixed(3) }} nm · {{ toleranceIndex.toFixed(2) }}×
      </span>
    </div>

    <input
      :id="id"
      type="range"
      :min="range.min"
      :max="range.max"
      :step="range.step"
      :value="modelValue"
      :disabled="disabled"
      class="mt-2 w-full accent-(--sk-brand) disabled:opacity-50"
      @input="onInput"
      @change="onCommit"
    >
    <!-- 12px, not the 11px micro-label tier: these are the knob's endpoints —
         data values — and DESIGN.md's floor is that a value never renders
         below 12px. -->
    <div class="flex justify-between font-mono text-xs tabular-nums text-(--sk-ink-subtle)">
      <span>{{ range.min.toFixed(2) }}</span>
      <span>{{ range.max.toFixed(2) }}</span>
    </div>

    <!-- The knob reads in nm because the server's tolerance_range does, but the
         grouping is CD-relative. Without this line the same slider position
         would silently mean different things per cell and the screen would
         never say so. -->
    <p class="mt-2 sk-field-label leading-relaxed">
      모니터 wafer {{ MONITOR_WAFER_CD_NM }} nm 기준.
      <EbeamTttmCaptionMore>
        N배화 판정은 셀마다 그 셀의 CD로 환산해서 적용하므로, 패턴이 크면 허용치도
        같은 비율로 넓어집니다 — 예: CD 68 nm 셀에서는
        {{ effectiveToleranceNm(toleranceIndex, 68).toFixed(3) }} nm.
      </EbeamTttmCaptionMore>
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
  /** No scope to judge yet — the slider stays visible so the step reads, but inert. */
  disabled?: boolean
}>()
const emit = defineEmits<{
  'update:modelValue': [value: number]
  /**
   * The drag finished. Split from `update:modelValue` because the two have
   * different costs: the model updates on every frame so the results follow the
   * thumb, while THIS is the one worth writing to the persisted scope.
   */
  'commit': [value: number]
}>()

// The label and the slider are stacked now rather than side by side, so they
// need an explicit pairing — a wrapping <label> would put the slider inside its
// own caption's hit area.
const id = useId()

const onInput = (e: Event) => {
  emit('update:modelValue', Number((e.target as HTMLInputElement).value))
}

const onCommit = (e: Event) => {
  emit('commit', Number((e.target as HTMLInputElement).value))
}
</script>
