<script setup lang="ts">
type HeaderStatTone = 'neutral' | 'accent' | 'ok' | 'bad' | 'muted' | string

type HeaderStatCell = {
  label: string
  value: string | number
  tone?: HeaderStatTone
}

withDefaults(defineProps<{
  eyebrow?: string
  stats?: HeaderStatCell[]
  statSize?: 'sm' | 'md'
  subtitle?: string
  title: string
}>(), {
  eyebrow: '',
  statSize: 'md',
  stats: () => [],
  subtitle: ''
})

const statToneClass = (tone: HeaderStatTone = 'neutral') => {
  const classes: Record<string, string> = {
    neutral: 'text-zinc-900 dark:text-zinc-100',
    accent: 'text-(--sk-accent)',
    ok: 'text-(--sk-ok)',
    bad: 'text-(--sk-bad)',
    muted: 'text-zinc-600 dark:text-zinc-300'
  }

  return classes[tone] ?? tone
}
</script>

<template>
  <div class="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
    <div class="flex min-w-0 items-center gap-3">
      <div class="min-w-0">
        <p
          v-if="eyebrow"
          class="text-sm font-medium text-zinc-500 dark:text-zinc-400"
        >
          {{ eyebrow }}
        </p>
        <h1 class="wrap-break-word text-xl font-bold tracking-tight text-zinc-950 dark:text-zinc-50 md:text-2xl">
          {{ title }}
        </h1>
        <p
          v-if="subtitle"
          class="mt-0.5 text-xs text-zinc-500 dark:text-zinc-400"
        >
          {{ subtitle }}
        </p>
      </div>

      <slot name="meta" />
    </div>

    <div
      v-if="$slots.actions || stats.length"
      class="self-start md:self-auto"
    >
      <slot name="actions">
        <div class="dashboard-surface flex overflow-hidden rounded-2xl">
          <div
            v-for="(cell, index) in stats"
            :key="cell.label"
            class="flex flex-col gap-0.5 px-4 py-2.5"
            :class="[
              statSize === 'sm' ? 'min-w-18' : 'min-w-28',
              { 'border-l border-zinc-200/70 dark:border-zinc-800/70': index > 0 }
            ]"
          >
            <span
              class="font-bold leading-none tabular-nums"
              :class="[statSize === 'sm' ? 'text-xl' : 'text-[22px]', statToneClass(cell.tone)]"
            >
              {{ cell.value }}
            </span>
            <span class="text-[11px] text-zinc-500">{{ cell.label }}</span>
          </div>
        </div>
      </slot>
    </div>
  </div>
</template>
