<template>
  <span
    class="inline-block rounded px-1.5 py-px font-mono text-[10px] font-bold tracking-wide"
    :class="isOk
      ? 'bg-(--sk-ok-soft) text-(--sk-ok)'
      : 'bg-(--sk-border-soft) text-(--sk-ink-subtle)'"
  >{{ label }}</span>
</template>

<script setup lang="ts">
const props = withDefaults(defineProps<{
  value: boolean | null
  okWhen?: boolean
}>(), {
  okWhen: true
})

const isOk = computed(() => props.value === props.okWhen)
const label = computed(() => props.value === null
  ? '—'
  : props.value ? 'True' : 'False')
</script>
