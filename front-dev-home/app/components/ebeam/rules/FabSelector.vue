<template>
  <div
    role="radiogroup"
    aria-label="Fab"
    class="inline-flex flex-wrap items-center gap-1 rounded-lg bg-zinc-100/70 p-1 dark:bg-zinc-800/60"
  >
    <button
      v-for="fab in fabs"
      :key="fab"
      type="button"
      role="radio"
      :aria-checked="modelValue === fab"
      class="inline-flex h-9 items-center rounded-md px-4 font-mono text-sm font-semibold transition-colors"
      :class="modelValue === fab
        ? 'bg-white text-zinc-900 shadow-sm ring-1 ring-zinc-200/80 dark:bg-zinc-900 dark:text-zinc-50 dark:ring-zinc-700/80'
        : 'text-zinc-500 hover:text-zinc-800 dark:text-zinc-400 dark:hover:text-zinc-200'"
      @click="emit('update:modelValue', fab)"
    >
      {{ fab }}
    </button>
  </div>
</template>

<script setup lang="ts">
// Fab switcher for the rule matrix (D13). R3 first (full dev matrix), then
// M-fabs newest-first to match the device-statistics fab order.
defineProps<{
  modelValue: string
  fabs: string[]
}>()

const emit = defineEmits<{
  'update:modelValue': [fab: string]
}>()
</script>
