<template>
  <div class="flex flex-wrap items-center gap-x-3 gap-y-1 text-[10.5px] text-(--sk-ink-muted)">
    <span class="inline-flex items-center gap-1">
      <span
        class="h-2 w-2 rounded-full"
        :style="{ backgroundColor: 'var(--sk-warn)' }"
      />
      주의 {{ watchLabel }}
    </span>
    <span class="inline-flex items-center gap-1">
      <span
        class="h-2 w-2 rounded-full"
        :style="{ backgroundColor: 'var(--sk-bad)' }"
      />
      이상 {{ abnormalLabel }}
    </span>
    <span class="inline-flex items-center gap-1">
      <span
        class="h-2 w-2 rounded-full"
        :style="{ backgroundColor: 'var(--sk-ink-subtle)' }"
      />
      미평가
    </span>
    <span class="text-(--sk-ink-subtle)">· 사용자 허용범위 ({{ methodLabel }})</span>
  </div>
</template>

<script setup lang="ts">
import type { RangeConfig, ScoringMethod, StddevConfig } from '~/utils/anomaly'

const props = defineProps<{
  method: ScoringMethod
  range: RangeConfig
  stddev: StddevConfig
}>()

const methodLabel = computed(() => (props.method === 'range' ? '범위' : '표준편차 · 진단'))
const watchLabel = computed(() =>
  props.method === 'range' ? `±${props.range.watchPct}%` : `±${props.stddev.watchK}σ`
)
const abnormalLabel = computed(() =>
  props.method === 'range' ? `±${props.range.abnormalPct}% 초과` : `±${props.stddev.abnormalK}σ 초과`
)
</script>
