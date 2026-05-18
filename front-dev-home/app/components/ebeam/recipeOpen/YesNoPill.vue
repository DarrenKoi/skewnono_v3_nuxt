<template>
  <span
    class="inline-block rounded px-1.5 py-px font-mono text-[10px] font-bold"
    :class="isYes
      ? 'bg-(--sk-brand-soft) text-(--sk-brand-ink)'
      : 'bg-(--sk-border-soft) text-(--sk-ink-subtle)'"
  >{{ value }}</span>
</template>

<script setup lang="ts">
const props = defineProps<{ value: string }>()
const isYes = computed(() => props.value === 'Yes')
</script>
