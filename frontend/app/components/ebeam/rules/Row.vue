<template>
  <tr class="border-t border-(--sk-border-soft) transition-colors hover:bg-(--sk-accent-soft)">
    <td class="border-r border-(--sk-border-soft) px-3 py-1.5 text-left whitespace-nowrap">
      <div class="flex items-center gap-2">
        <template v-if="vehicle.main">
          <span class="sk-value">{{ vehicle.main }}</span>
          <span
            v-if="vehicle.hint"
            class="sk-label"
          >{{ vehicle.hint }}</span>
        </template>
        <span
          v-else
          class="sk-value text-(--sk-ink-muted)"
        >기본</span>
        <EbeamRulesMemoryChip
          v-if="memory"
          :memory="memory"
        />
      </div>
    </td>
    <td
      v-for="column in columns"
      :key="column.key"
      class="px-2 py-1.5 text-center"
    >
      <EbeamRulesCapCell
        :value="capValue(cell, column.key)"
        :emphasis="expanded && column.key !== '_other'"
      />
    </td>
    <td />
  </tr>
</template>

<script setup lang="ts">
import type { RuleCell } from '~/utils/ruleEngine'
import type { CapColumn } from '~/utils/ruleMatrix'
import { capValue, isExpandedCell, memoryOf, vehicleLabel } from '~/utils/ruleMatrix'

// One rule cell as a matrix row (D13). The family header lives in the group
// header (Matrix); this row carries the vehicle/yield axis + memory pill.
// Expanded cells (TV 포함 이후 · 수율 후) highlight their EDGE/EDGE_EX caps.
// The trailing empty <td> pairs with Matrix's spacer <col>: it absorbs the
// slack so the caps sit beside their row label instead of ~600px away.
const props = defineProps<{
  cell: RuleCell
  columns: readonly CapColumn[]
}>()

const vehicle = computed(() => vehicleLabel(props.cell))
const memory = computed(() => memoryOf(props.cell))
const expanded = computed(() => isExpandedCell(props.cell))
</script>
