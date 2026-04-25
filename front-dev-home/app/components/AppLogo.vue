<template>
  <div class="flex items-center gap-3">
    <svg
      class="w-9 h-9"
      viewBox="0 0 32 32"
      shape-rendering="geometricPrecision"
      aria-hidden="true"
    >
      <rect
        width="32"
        height="32"
        rx="5"
        class="fill-zinc-50 dark:fill-zinc-900"
      />
      <rect
        x="0.8"
        y="0.8"
        width="30.4"
        height="30.4"
        rx="4.5"
        fill="none"
        class="stroke-zinc-900 dark:stroke-zinc-100"
        stroke-width="1.6"
      />
      <line
        x1="9"
        y1="24"
        x2="18"
        y2="8"
        class="stroke-zinc-900 dark:stroke-zinc-100"
        stroke-width="3.2"
        stroke-linecap="square"
      />
      <line
        x1="16"
        y1="24"
        x2="25"
        y2="8"
        stroke="var(--sk-accent)"
        stroke-width="3.2"
        stroke-linecap="square"
      />
    </svg>
    <span class="font-semibold text-lg tracking-tight text-zinc-900 dark:text-zinc-100">SKEWNONO</span>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  size?: 'sm' | 'md' | 'lg'
}>()
</script>
