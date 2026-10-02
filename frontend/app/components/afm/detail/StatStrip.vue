<template>
  <dl class="flex flex-wrap items-baseline gap-x-4 gap-y-1 rounded-(--sk-r-chip) bg-(--sk-muted-surface) px-3 py-2">
    <div
      v-for="item in items"
      :key="item.label"
      class="flex items-baseline gap-1.5"
    >
      <dt class="text-xs text-(--sk-ink-muted)">
        {{ item.label }}
      </dt>
      <dd class="font-mono text-[13px] font-semibold tabular-nums text-(--sk-ink)">
        {{ item.value }}
      </dd>
    </div>
    <slot />
  </dl>
</template>

<script setup lang="ts">
// The summary numbers above a point chart (분포, 히트맵), as one inset row:
// muted label, full-ink mono value. Both charts use it so their stats sit in the
// same place and type.
defineProps<{
  items: { label: string, value: string }[]
}>()
</script>
