<template>
  <UCard class="dashboard-surface">
    <div class="flex items-center gap-4">
      <div :class="['flex h-12 w-12 items-center justify-center rounded-xl bg-zinc-100 dark:bg-zinc-800', color]">
        <UIcon
          :name="icon"
          class="text-2xl"
        />
      </div>
      <div class="min-w-0 flex-1">
        <div class="text-xs uppercase tracking-wider text-zinc-500">
          {{ label }}
        </div>
        <div class="text-3xl font-bold tabular-nums leading-tight">
          {{ value }}
        </div>
        <div
          v-if="hint"
          class="text-xs text-zinc-500 dark:text-zinc-400 truncate"
        >
          {{ hint }}
        </div>
      </div>
    </div>
  </UCard>
</template>

<script setup lang="ts">
defineProps<{
  label: string
  value: number | string
  hint?: string
  icon: string
  color?: string
}>()
</script>
