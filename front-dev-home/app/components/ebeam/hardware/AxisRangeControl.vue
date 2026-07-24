<template>
  <div class="mt-1 flex items-center justify-center gap-1.5 px-1">
    <span class="sk-eyebrow shrink-0">
      범위
    </span>
    <UInput
      v-model="minText"
      size="xs"
      color="neutral"
      variant="subtle"
      inputmode="decimal"
      :aria-label="`${label} 축 최소값`"
      class="w-16"
      :ui="{ base: 'text-center font-mono tabular-nums' }"
      @change="commit"
      @keyup.enter="commit"
    />
    <span class="text-[11px] text-(--sk-ink-muted)">–</span>
    <UInput
      v-model="maxText"
      size="xs"
      color="neutral"
      variant="subtle"
      inputmode="decimal"
      :aria-label="`${label} 축 최대값`"
      class="w-16"
      :ui="{ base: 'text-center font-mono tabular-nums' }"
      @change="commit"
      @keyup.enter="commit"
    />
    <UTooltip :text="modelValue ? '기본 범위로 되돌리기' : '기본 범위 사용 중'">
      <UButton
        icon="i-lucide-rotate-ccw"
        size="xs"
        color="neutral"
        variant="ghost"
        :disabled="!modelValue"
        :aria-label="`${label} 축 범위 초기화`"
        @click="reset"
      />
    </UTooltip>
  </div>
</template>

<script setup lang="ts">
import { isValidRange, type AxisRange } from '~/utils/profileAxisRange'

const props = defineProps<{
  // null = no override; the chart is drawing at `defaultRange`.
  modelValue: AxisRange | null
  // The range in force without an override — the metric's operating band, or
  // the data-derived range for metrics that have none. Also the reset target.
  defaultRange: AxisRange
  // Metric name, for the screen-reader labels only.
  label: string
}>()

const emit = defineEmits<{ 'update:modelValue': [AxisRange | null] }>()

const effective = computed(() => props.modelValue ?? props.defaultRange)

// Text, not `type="number"` bound straight to the model: a half-typed "7." or a
// momentarily inverted pair must not reach the axis mid-keystroke. The parsed
// pair is committed on blur/Enter, and only when it forms a valid range.
const minText = ref('')
const maxText = ref('')

// The stored numbers are already rounded; toFixed+Number just strips the
// trailing zeros that would otherwise show as "7.5000".
const format = (value: number) => String(Number(value.toFixed(4)))

const seed = (range: AxisRange) => {
  minText.value = format(range.min)
  maxText.value = format(range.max)
}

// Re-seeds when the effective range changes under us — switching the BSM radar
// metric, or resetting — so the inputs always show what the chart is drawing.
watch(effective, seed, { immediate: true, deep: true })

const commit = () => {
  const range = { min: Number(minText.value), max: Number(maxText.value) }
  if (isValidRange(range)) {
    emit('update:modelValue', range)
    return
  }
  // Garbage or inverted input: snap the fields back to what the chart shows
  // rather than leaving the reader with numbers the axis doesn't honor.
  seed(effective.value)
}

const reset = () => {
  emit('update:modelValue', null)
  seed(props.defaultRange)
}
</script>
