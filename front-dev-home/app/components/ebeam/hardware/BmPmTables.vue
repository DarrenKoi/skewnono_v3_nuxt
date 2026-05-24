<template>
  <div class="mt-3 flex flex-col gap-4">
    <section
      v-for="section in tables"
      :key="section.key"
      class="overflow-hidden rounded-xl bg-(--sk-surface) ring-1 ring-(--sk-border-soft)"
    >
      <div class="flex items-center justify-between border-b border-(--sk-border-soft) px-3 py-2">
        <span class="text-xs font-bold text-(--sk-ink)">{{ section.title }}</span>
        <span class="font-mono text-[11px] text-(--sk-ink-muted)">{{ section.rows.length }} rows</span>
      </div>

      <div class="overflow-x-auto">
        <table class="min-w-full text-left text-xs">
          <thead class="bg-zinc-100 text-zinc-500 dark:bg-zinc-900 dark:text-zinc-400">
            <tr>
              <th
                v-for="column in section.columns"
                :key="column.key"
                class="whitespace-nowrap px-3 py-2 font-mono text-[10px] uppercase tracking-[0.05em]"
                :class="column.expandable ? 'w-full' : ''"
              >
                {{ column.label }}
              </th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="(row, rowIndex) in section.rows"
              :key="rowIndex"
              class="border-t border-(--sk-border-soft) align-top"
            >
              <td
                v-for="column in section.columns"
                :key="column.key"
                class="px-3 py-2"
                :class="column.expandable ? 'min-w-[16rem]' : 'whitespace-nowrap'"
              >
                <!-- BM/PM category chip -->
                <span
                  v-if="column.key === 'category'"
                  class="inline-flex items-center rounded-md px-1.5 py-0.5 font-mono text-[10px] font-bold"
                  :class="row[column.key] === 'PM'
                    ? 'bg-(--sk-ok-soft) text-(--sk-ok)'
                    : 'bg-(--sk-bad-soft) text-(--sk-bad)'"
                >
                  {{ row[column.key] }}
                </span>

                <!-- Expandable free-text note: truncate + click to toggle -->
                <button
                  v-else-if="column.expandable"
                  type="button"
                  class="flex w-full items-start gap-1.5 text-left text-(--sk-ink) transition-colors hover:text-(--sk-ink-muted)"
                  @click="toggle(section.key, rowIndex)"
                >
                  <UIcon
                    :name="isExpanded(section.key, rowIndex) ? 'i-lucide-chevron-down' : 'i-lucide-chevron-right'"
                    class="mt-0.5 h-3.5 w-3.5 shrink-0 text-(--sk-ink-subtle)"
                  />
                  <span :class="isExpanded(section.key, rowIndex) ? 'whitespace-pre-line' : 'line-clamp-1'">
                    {{ formatValue(row[column.key]) }}
                  </span>
                </button>

                <!-- Default: mono date / id cell -->
                <span
                  v-else
                  class="font-mono text-(--sk-ink)"
                >{{ formatValue(row[column.key]) }}</span>
              </td>
            </tr>

            <tr v-if="section.rows.length === 0">
              <td
                :colspan="section.columns.length"
                class="px-3 py-6 text-center text-(--sk-ink-muted)"
              >
                표시할 작업이 없습니다.
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import type { HardwareMetricValue, HardwareTableSection } from '~/composables/useHardwareApi'

defineProps<{
  tables: HardwareTableSection[]
}>()

// Per-row expand state, keyed by section + row index so the two tables don't
// collide. A Set keeps the template checks O(1) and resets on remount.
const expanded = reactive(new Set<string>())

const rowKey = (sectionKey: string, rowIndex: number) => `${sectionKey}:${rowIndex}`

const isExpanded = (sectionKey: string, rowIndex: number) =>
  expanded.has(rowKey(sectionKey, rowIndex))

const toggle = (sectionKey: string, rowIndex: number) => {
  const key = rowKey(sectionKey, rowIndex)
  if (expanded.has(key)) expanded.delete(key)
  else expanded.add(key)
}

const formatValue = (value: HardwareMetricValue | undefined) => {
  if (value === undefined || value === null || value === '') return '-'
  return String(value)
}
</script>
