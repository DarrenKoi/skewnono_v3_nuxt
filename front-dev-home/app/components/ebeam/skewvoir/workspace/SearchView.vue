<template>
  <div class="space-y-3">
    <!-- Search bar -->
    <div class="dashboard-surface rounded-(--sk-r-card) p-3">
      <p class="mb-2 px-0.5 text-[11px] text-zinc-400">
        검색 · <span class="font-semibold text-zinc-600 dark:text-zinc-300">Lot / Recipe / Machine</span>
        · Elastic Search · 1.2M scans · last 90d
      </p>
      <div class="flex items-center gap-2">
        <UInput
          v-model="queryText"
          class="flex-1"
          icon="i-lucide-search"
          placeholder="MCD018, RK2W011, VMGTET, lot:RK2A052AN, MP:WAFER…"
          size="md"
        />
        <UButton
          color="neutral"
          variant="outline"
          label="Saved"
          size="md"
        />
        <UButton
          class="bg-(--sk-ink) text-(--sk-ink-fg)"
          label="Search"
          icon="i-lucide-corner-down-left"
          size="md"
        />
      </div>

      <!-- Filters -->
      <div class="mt-3 flex flex-wrap items-center gap-2">
        <span class="font-mono text-[10px] tracking-wide text-zinc-400">FILTERS</span>
        <button
          v-for="opt in dropdownFilters"
          :key="opt.label"
          type="button"
          class="inline-flex h-7 items-center gap-1.5 rounded-(--sk-r-chip) border border-(--sk-border) bg-(--sk-surface) px-2.5 text-[12px] text-zinc-600 hover:bg-zinc-500/5 dark:text-zinc-300"
        >
          <span class="text-zinc-400">{{ opt.label }}:</span>
          <span class="font-medium text-zinc-800 dark:text-zinc-100">{{ opt.value }}</span>
          <UIcon
            name="i-lucide-chevron-down"
            class="h-3 w-3 opacity-50"
          />
        </button>

        <span
          v-for="chip in chipFilters"
          :key="chip"
          class="inline-flex h-7 items-center gap-1.5 rounded-(--sk-r-chip) bg-(--sk-brand) px-2.5 font-mono text-[11.5px] font-medium text-(--sk-brand-fg)"
        >
          {{ chip }}
          <UIcon
            name="i-lucide-x"
            class="h-3 w-3 opacity-70"
          />
        </span>

        <UButton
          class="ml-auto"
          color="neutral"
          variant="outline"
          label="Save query"
          size="xs"
        />
      </div>
    </div>

    <!-- Result timeline + quick stats (data wired in the Landing slice) -->
    <div class="grid grid-cols-1 gap-3 xl:grid-cols-[1fr_22rem]">
      <EbeamSkewvoirWorkspacePanelStub
        title="Result Timeline"
        meta="24 measurements"
        icon="i-lucide-gantt-chart"
        height="h-64"
      />
      <EbeamSkewvoirWorkspacePanelStub
        title="Quick Stats by Recipe"
        meta="recipe rollup"
        icon="i-lucide-table-2"
        height="h-64"
      />
    </div>

    <!-- Latest lots -->
    <EbeamSkewvoirWorkspacePanelStub
      title="Latest Lots"
      meta="8 of 24 · Cards / Table / Compare selected"
      icon="i-lucide-layout-grid"
      height="h-72"
    />
  </div>
</template>

<script setup lang="ts">
import type { SkewvoirWorkspace } from '~/composables/useSkewvoirWorkspace'

const props = defineProps<{ ws: SkewvoirWorkspace }>()

const queryText = ref('')

const f = computed(() => props.ws.pinnedFilters.value)

const dropdownFilters = computed(() => [
  { label: 'Area', value: 'ALL' },
  { label: 'FAB', value: f.value.fab },
  { label: '장비 종류', value: f.value.eqType },
  { label: 'EQ', value: 'ALL' },
  { label: '기간', value: f.value.period }
])

const chipFilters = computed(() => [`MP : ${f.value.mp}`, ...f.value.flags])
</script>
