<template>
  <tr class="border-t border-(--sk-border) transition-colors hover:bg-(--sk-accent-tint)/40">
    <td class="px-3 py-1 text-left whitespace-nowrap">
      <div class="flex items-center gap-2">
        <template v-if="vehicle.main">
          <span class="text-[12.5px] font-medium text-(--sk-ink)">{{ vehicle.main }}</span>
          <span
            v-if="vehicle.hint"
            class="text-[11px] text-(--sk-ink-subtle)"
          >{{ vehicle.hint }}</span>
        </template>
        <span
          v-else
          class="text-[12.5px] text-(--sk-ink-subtle)"
        >기본</span>
        <span
          v-if="memory"
          class="inline-flex h-5 items-center rounded px-1.5 font-mono text-[10px] font-semibold ring-1"
          :class="memory === 'NAND'
            ? 'bg-amber-50 text-amber-700 ring-amber-200 dark:bg-amber-950/40 dark:text-amber-300 dark:ring-amber-900/60'
            : 'bg-sky-50 text-sky-700 ring-sky-200 dark:bg-sky-950/40 dark:text-sky-300 dark:ring-sky-900/60'"
        >{{ memory }}</span>
      </div>
    </td>
    <td
      v-for="column in columns"
      :key="column.key"
      class="px-2 py-1 text-center"
    >
      <EbeamRulesCapCell
        :value="capValue(cell, column.key)"
        :emphasis="expanded && column.key !== '_other'"
      />
    </td>
  </tr>
</template>

<script setup lang="ts">
import type { RuleCell } from '~/utils/ruleEngine'
import type { CapColumn } from '~/utils/ruleMatrix'
import { capValue, isExpandedCell, memoryOf, vehicleLabel } from '~/utils/ruleMatrix'

// One rule cell as a matrix row (D13). The family header lives in the group
// header (Matrix); this row carries the vehicle/yield axis + memory pill.
// Expanded cells (TV 포함 이후 · 수율 후) highlight their EDGE/EDGE_EX caps.
const props = defineProps<{
  cell: RuleCell
  columns: readonly CapColumn[]
}>()

const vehicle = computed(() => vehicleLabel(props.cell))
const memory = computed(() => memoryOf(props.cell))
const expanded = computed(() => isExpandedCell(props.cell))
</script>
