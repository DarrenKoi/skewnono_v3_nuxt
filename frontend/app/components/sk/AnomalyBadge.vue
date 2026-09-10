<template>
  <UTooltip
    v-if="show"
    :text="tooltip"
  >
    <span class="inline-flex items-center gap-1 align-middle">
      <span
        class="inline-block rounded-full"
        :class="compact ? 'h-2 w-2' : 'h-2.5 w-2.5'"
        :style="{ backgroundColor: colorVar }"
      />
      <span
        v-if="!compact && label"
        class="text-xs font-medium"
        :style="{ color: colorVar }"
      >{{ label }}</span>
    </span>
  </UTooltip>
</template>

<script setup lang="ts">
import type { AnomalyVerdict, CombinedVerdict } from '~/utils/anomaly'

const props = withDefaults(defineProps<{
  verdict: CombinedVerdict | AnomalyVerdict | null
  compact?: boolean
}>(), { compact: false })

const isCombined = (v: CombinedVerdict | AnomalyVerdict): v is CombinedVerdict => 'verdicts' in v

const status = computed(() => props.verdict?.status ?? 'evaluated')
const severity = computed(() => props.verdict?.severity ?? 'normal')

// status first, then severity. Silence (render nothing) for evaluated-normal.
const show = computed(() =>
  !!props.verdict && (status.value === 'insufficient' || severity.value !== 'normal')
)

const reasons = computed<string[]>(() => {
  const v = props.verdict
  if (!v) return []
  return isCombined(v) ? v.verdicts.map(x => x.reason) : [v.reason]
})
const tooltip = computed(() => reasons.value.join(' · '))

const label = computed(() =>
  status.value === 'insufficient'
    ? '미평가'
    : severity.value === 'abnormal' ? '이상' : severity.value === 'watch' ? '주의' : ''
)

const colorVar = computed(() =>
  status.value === 'insufficient'
    ? 'var(--sk-ink-subtle)'
    : severity.value === 'abnormal' ? 'var(--sk-bad)' : severity.value === 'watch' ? 'var(--sk-warn)' : 'transparent'
)
</script>
