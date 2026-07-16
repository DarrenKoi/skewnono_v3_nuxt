<template>
  <button
    v-if="target.ready"
    type="button"
    class="inline-flex items-center gap-1.5 rounded-(--sk-r-chip) border border-(--sk-accent)/40 bg-(--sk-accent)/10 px-2.5 py-1 font-mono text-[11px] font-medium text-(--sk-accent) transition-colors duration-200 hover:bg-(--sk-accent)/20"
    @click="emit('go')"
  >
    <UIcon
      :name="icon"
      class="h-3.5 w-3.5"
    />
    {{ target.label }}
    <UIcon
      name="i-lucide-arrow-right"
      class="h-3 w-3 opacity-70"
    />
  </button>
  <span
    v-else
    class="inline-flex cursor-not-allowed items-center gap-1.5 rounded-(--sk-r-chip) border border-(--sk-border-soft) px-2.5 py-1 font-mono text-[11px] text-(--sk-ink-subtle)"
    :title="target.reason ?? undefined"
  >
    <UIcon
      :name="icon"
      class="h-3.5 w-3.5 opacity-60"
    />
    {{ target.label }}
  </span>
</template>

<script setup lang="ts">
import type { HandoffKey, HandoffTarget } from '~/utils/skewvoirAnalysis/handoffs'

const props = defineProps<{ target: HandoffTarget }>()
const emit = defineEmits<{ go: [] }>()

const ICONS: Record<HandoffKey, string> = {
  position: 'i-lucide-grid-3x3',
  sequence: 'i-lucide-activity',
  paired: 'i-lucide-scatter-chart',
  gallery: 'i-lucide-images'
}

const icon = computed(() => ICONS[props.target.key])
</script>
