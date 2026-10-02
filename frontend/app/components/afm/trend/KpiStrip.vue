<template>
  <div class="grid grid-cols-2 gap-2.5 md:grid-cols-3 xl:grid-cols-6">
    <div
      v-for="k in kpis"
      :key="k.label"
      class="flex flex-col gap-0.5 rounded-(--sk-r-nav) bg-(--sk-muted-surface) px-3.5 py-3"
      :class="k.alert ? 'ring-1 ring-(--sk-bad-border) ring-inset' : ''"
    >
      <span class="sk-label">{{ k.label }}</span>
      <span
        class="font-mono text-xl font-semibold tracking-tight tabular-nums"
        :class="k.alert ? 'text-(--sk-brand)' : 'text-(--sk-ink)'"
      >{{ k.value }}</span>
      <span class="truncate sk-meta">{{ k.sub }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
export interface TrendKpi {
  label: string
  value: string
  sub: string
  // Something to look at: terracotta value, red ring.
  alert?: boolean
}

defineProps<{ kpis: TrendKpi[] }>()
</script>
