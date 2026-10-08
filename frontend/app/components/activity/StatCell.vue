<template>
  <div class="flex items-start gap-2.5">
    <UIcon
      :name="icon"
      :class="['text-xl mt-0.5 shrink-0', color]"
    />
    <div class="min-w-0">
      <!-- A count stays big on one line; a text value (a feature label, a
           timestamp) is longer than half a card, so it wraps instead of
           ending in "…". leading-7 keeps its first line level with a count's. -->
      <div
        class="font-semibold tabular-nums"
        :class="typeof value === 'number' ? 'text-xl truncate' : 'text-base leading-7 break-keep'"
      >
        {{ value }}<span
          v-if="unit"
          class="text-sm font-normal text-(--sk-ink-muted) ml-0.5"
        >{{ unit }}</span>
      </div>
      <div class="sk-label truncate">
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
