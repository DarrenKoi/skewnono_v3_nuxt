<template>
  <section class="dashboard-surface flex flex-col rounded-(--sk-r-card) p-3">
    <div class="mb-2 flex items-center justify-between gap-2">
      <h2 class="text-[12.5px] font-semibold text-zinc-900 dark:text-zinc-100">
        {{ title }}
      </h2>
      <span class="font-mono text-[10.5px] text-zinc-400">{{ meta }}</span>
    </div>
    <div
      class="flex flex-1 items-center justify-center rounded-(--sk-r-chip) border border-dashed border-(--sk-border) text-zinc-300 dark:text-zinc-600"
      :class="height"
    >
      <UIcon
        :name="icon"
        class="h-7 w-7"
      />
    </div>
  </section>
</template>

<script setup lang="ts">
defineProps<{
  title: string
  meta: string
  icon: string
  height: string
}>()
</script>
