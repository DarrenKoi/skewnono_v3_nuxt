<template>
  <UCard
    class="dashboard-surface rounded-2xl"
    :ui="{ body: 'p-0', header: 'px-4 sm:px-5 py-3' }"
  >
    <template #header>
      <div class="flex flex-wrap items-center justify-between gap-3">
        <div class="flex items-center gap-2">
          <UIcon
            name="i-lucide-target"
            class="h-4 w-4 text-zinc-500"
          />
          <h2 class="text-sm font-semibold">
            Measurement points
          </h2>
          <span class="text-[11px] text-zinc-400 tabular-nums">
            ({{ filteredRows.length }} / {{ data.length }})
          </span>
        </div>
        <div class="flex flex-wrap items-center gap-1.5">
          <button
            v-for="point in availablePoints"
            :key="point"
            type="button"
            class="inline-flex h-6 items-center rounded-md px-2 text-[11px] font-medium ring-1 transition-colors"
            :class="chipClass(selectedPoint === point)"
            @click="$emit('update:selectedPoint', point)"
          >
            {{ point }}
          </button>
          <button
            v-if="selectedPoint"
            type="button"
            class="inline-flex h-6 items-center gap-1 rounded-full px-2 text-[11px] text-zinc-500 ring-1 ring-zinc-200 hover:bg-zinc-50 dark:ring-zinc-700 dark:hover:bg-zinc-800"
            @click="$emit('update:selectedPoint', '')"
          >
            <UIcon
              name="i-lucide-x"
              class="h-3 w-3"
            />
            All
          </button>
        </div>
      </div>
    </template>

    <div
      v-if="filteredRows.length === 0"
      class="px-4 py-10 text-center text-sm text-zinc-500"
    >
      No measurement rows
    </div>
    <div
      v-else
      class="max-h-[480px] overflow-auto"
    >
      <table class="w-full text-[12px] font-mono">
        <thead class="sticky top-0 z-10 bg-zinc-50/95 text-zinc-500 backdrop-blur dark:bg-zinc-900/90">
          <tr>
            <th
              v-for="col in columns"
              :key="col.key"
              class="px-2.5 py-1.5 text-right font-medium first:text-left"
            >
              {{ col.label }}
            </th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="(row, i) in filteredRows"
            :key="i"
            class="border-t border-zinc-100 transition-colors hover:bg-zinc-50/80 dark:border-zinc-800/60 dark:hover:bg-zinc-800/30"
          >
            <td
              v-for="col in columns"
              :key="col.key"
              class="px-2.5 py-1 text-right tabular-nums first:text-left"
            >
              {{ formatCell(row[col.key]) }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </UCard>
</template>

<script setup lang="ts">
import type { AfmDetailRow } from '~/composables/useAfmDetailApi'
import { chipClass } from '~/utils/chipClass'

const props = defineProps<{
  data: AfmDetailRow[]
  availablePoints: string[]
  selectedPoint: string
}>()

defineEmits<{
  (event: 'update:selectedPoint', point: string): void
}>()

const columns: ReadonlyArray<{ key: keyof AfmDetailRow, label: string }> = [
  { key: 'measurement_point', label: 'Site' },
  { key: 'Point No', label: '#' },
  { key: 'X (um)', label: 'X (μm)' },
  { key: 'Y (um)', label: 'Y (μm)' },
  { key: 'Left_H (nm)', label: 'Left_H' },
  { key: 'Right_H (nm)', label: 'Right_H' },
  { key: 'Ref_H (nm)', label: 'Ref_H' },
  { key: 'State', label: 'State' }
]

const filteredRows = computed(() => {
  if (!props.selectedPoint) return props.data
  return props.data.filter(r => r.measurement_point === props.selectedPoint)
})

const formatCell = (v: unknown) => {
  if (v === null || v === undefined || v === '') return '–'
  if (typeof v === 'number') return Number.isInteger(v) ? String(v) : v.toFixed(2)
  return String(v)
}
</script>
