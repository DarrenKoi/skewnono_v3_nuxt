<template>
  <span
    class="inline-flex h-[18px] items-center rounded-[6px] px-1.5 font-mono text-[10px] font-semibold tracking-wide tabular-nums ring-1"
    :class="chipClass"
    :title="inferred ? 'stage 추출 실패 — EV cap 적용 중' : `stage: ${stage}`"
  >
    <span
      v-if="inferred"
      class="opacity-70"
    >?</span>
    <span v-else>{{ stage }}</span>
  </span>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { DevStage } from '~/composables/useLotHealthMock'

const props = defineProps<{
  stage: DevStage
  inferred?: boolean
}>()

const chipClass = computed(() => {
  if (props.inferred) {
    return 'bg-zinc-100/70 text-(--sk-ink-muted) ring-zinc-200 dark:bg-zinc-800/70 dark:text-zinc-400 dark:ring-zinc-700'
  }
  switch (props.stage) {
    case 'EV':
      return 'bg-(--sk-brand-soft) text-(--sk-brand-ink) ring-(--sk-accent-border)'
    case 'TV':
      return 'bg-amber-100/80 text-amber-800 ring-amber-200 dark:bg-amber-900/30 dark:text-amber-200 dark:ring-amber-800/50'
    case 'PV':
      return 'bg-emerald-100/70 text-emerald-800 ring-emerald-200 dark:bg-emerald-900/30 dark:text-emerald-200 dark:ring-emerald-800/50'
    case 'Pool':
      return 'bg-sky-100/70 text-sky-800 ring-sky-200 dark:bg-sky-900/30 dark:text-sky-200 dark:ring-sky-800/50'
    default:
      return 'bg-zinc-100 text-(--sk-ink-muted) ring-zinc-200 dark:bg-zinc-800 dark:text-zinc-400 dark:ring-zinc-700'
  }
})
</script>
