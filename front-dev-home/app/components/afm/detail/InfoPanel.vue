<template>
  <UCard
    class="dashboard-surface rounded-2xl"
    :ui="{ body: 'p-4 sm:p-5', header: 'px-4 sm:px-5 py-3' }"
  >
    <template #header>
      <div class="flex items-center gap-2">
        <UIcon
          name="i-lucide-info"
          class="h-4 w-4 text-zinc-500"
        />
        <h2 class="text-sm font-semibold">
          Information
        </h2>
      </div>
    </template>

    <dl class="grid grid-cols-1 gap-x-6 gap-y-2 sm:grid-cols-2">
      <div
        v-for="entry in informationEntries"
        :key="entry.key"
        class="flex items-baseline justify-between gap-3 border-b border-zinc-100 pb-1.5 last:border-0 dark:border-zinc-800/60"
      >
        <dt class="text-[11px] uppercase tracking-wider text-zinc-500">
          {{ entry.key }}
        </dt>
        <dd class="font-mono text-[12.5px] text-zinc-800 dark:text-zinc-100 text-right truncate">
          {{ entry.value }}
        </dd>
      </div>
    </dl>

    <div
      v-if="summarySites.length > 0"
      class="mt-5"
    >
      <p class="mb-2 text-[11px] uppercase tracking-wider text-zinc-500">
        Summary by site (MEAN)
      </p>
      <div class="overflow-x-auto rounded-lg ring-1 ring-zinc-200 dark:ring-zinc-800">
        <table class="w-full text-[12px] font-mono">
          <thead class="bg-zinc-50/70 text-zinc-500 dark:bg-zinc-900/50">
            <tr>
              <th class="px-2 py-1.5 text-left font-medium">
                Site
              </th>
              <th
                v-for="col in measurementColumns"
                :key="col"
                class="px-2 py-1.5 text-right font-medium"
              >
                {{ col }}
              </th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="site in summarySites"
              :key="site.site"
              class="border-t border-zinc-100 dark:border-zinc-800/60"
            >
              <td class="px-2 py-1 text-left">
                {{ site.site }}
              </td>
              <td
                v-for="col in measurementColumns"
                :key="col"
                class="px-2 py-1 text-right tabular-nums"
              >
                {{ site.values[col] ?? '–' }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </UCard>
</template>

<script setup lang="ts">
import type { AfmInformation, AfmSummaryRow } from '~/composables/useAfmDetailApi'

const props = defineProps<{
  information: AfmInformation
  summary: AfmSummaryRow[]
}>()

const informationEntries = computed(() =>
  Object.entries(props.information ?? {}).map(([key, value]) => ({
    key,
    value: value === null || value === undefined || value === '' ? '–' : String(value)
  }))
)

const measurementColumns = computed(() => {
  if (!props.summary?.length) return []
  const first = props.summary[0]!
  return Object.keys(first).filter(k => k !== 'Site' && k !== 'ITEM')
})

const summarySites = computed(() => {
  const bySite = new Map<string, Record<string, string>>()
  for (const row of props.summary ?? []) {
    if (row.ITEM !== 'MEAN') continue
    const values: Record<string, string> = {}
    for (const col of measurementColumns.value) {
      const v = row[col]
      values[col] = typeof v === 'number' ? v.toFixed(2) : String(v ?? '–')
    }
    bySite.set(row.Site, values)
  }
  return Array.from(bySite, ([site, values]) => ({ site, values }))
})
</script>
