<template>
  <div class="flex flex-wrap items-baseline gap-x-2.5 gap-y-1 px-1 pt-3">
    <span class="font-mono text-xs font-semibold text-(--sk-ink-muted)">{{ num }}</span>
    <h2 class="sk-panel-title">
      {{ title }}
    </h2>
    <span class="sk-hint">{{ hint }}</span>
  </div>
</template>

<script setup lang="ts">
// A numbered section eyebrow of 시계열 비교: 01 추세 … 04 장비 건강.
defineProps<{
  num: string
  title: string
  hint: string
}>()
</script>
