<template>
  <div class="flex items-start gap-2.5">
    <UIcon
      :name="icon"
      :class="['text-xl mt-0.5 shrink-0', color]"
    />
    <div class="min-w-0">
      <div class="text-xl font-semibold tabular-nums truncate">
        {{ value }}<span
          v-if="unit"
          class="text-sm font-normal text-zinc-500 ml-0.5"
        >{{ unit }}</span>
      </div>
      <div class="text-xs text-zinc-500 dark:text-zinc-400 truncate">
        {{ label }}
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  icon: string
  color?: string
  value: string | number
  label: string
  unit?: string
}>()
</script>
