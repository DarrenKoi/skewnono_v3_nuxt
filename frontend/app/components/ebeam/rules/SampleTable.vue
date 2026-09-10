<template>
  <div class="dashboard-surface rounded-[var(--sk-r-card)] p-3">
    <div class="mb-2 flex flex-wrap items-center justify-between gap-2">
      <h3 class="sk-title">
        {{ text.title }}
      </h3>
      <span class="sk-meta">
        {{ text.subtitle }}
      </span>
    </div>

    <div class="overflow-x-auto">
      <table class="w-full border-collapse">
        <thead>
          <tr class="border-b border-(--sk-border)">
            <th class="w-[264px] border-r border-(--sk-border-soft) px-3 py-2 text-left whitespace-nowrap sk-label">
              룰 셀
            </th>
            <th
              v-for="column in CAP_COLUMNS"
              :key="column.key"
              class="w-[116px] px-2 py-2 text-center whitespace-nowrap sk-label"
            >
              {{ column.label }}
            </th>
            <th class="w-full" />
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="row in rows"
            :key="row.cell.id"
            class="border-t border-(--sk-border-soft) transition-colors hover:bg-(--sk-accent-soft)"
          >
            <td class="border-r border-(--sk-border-soft) px-3 py-1.5 text-left whitespace-nowrap">
              <div class="flex items-center gap-2">
                <span
                  class="sk-value"
                  :class="row.label === '기본' ? 'text-(--sk-ink-muted)' : 'font-semibold'"
                >{{ row.label }}</span>
                <span
                  v-if="row.hint"
                  class="sk-label"
                >{{ row.hint }}</span>
                <EbeamRulesMemoryChip
                  v-if="row.memory"
                  :memory="row.memory"
                />
              </div>
            </td>
            <td
              v-for="column in CAP_COLUMNS"
              :key="column.key"
              class="px-2 py-1.5 text-center"
            >
              <EbeamRulesCapCell
                :value="capValue(row.cell, column.key)"
                :emphasis="row.expanded && column.key !== '_other'"
              />
            </td>
            <td />
          </tr>
        </tbody>
      </table>
    </div>

    <p
      v-if="overrides.length > 0"
      class="mt-2 border-t border-(--sk-border-soft) px-3 pt-2"
    >
      <span class="sk-label">▸ 이름 예외 (기타 파라 전용)</span>
      <code
        v-for="(ov, index) in overrides"
        :key="index"
        class="ml-1.5 font-mono text-[12px] text-(--sk-ink)"
      >{{ overrideLabel(ov) }}</code>
    </p>
  </div>
</template>

<script setup lang="ts">
import type { RuleCell } from '~/utils/ruleEngine'
import {
  CAP_COLUMNS, capValue, collectOverrides, familyLabel,
  isExpandedCell, memoryOf, overrideLabel, vehicleLabel
} from '~/utils/ruleMatrix'

// Sample rules in their own table (D6/D19), separated from the Main matrix so
// its very different policy (비-WAFER 측정 금지, WF/WAFER 이름 면제) doesn't blur
// the Main story. Base rows first, the Core TV·PV EDGE 상향 예외 (D19) last.
const props = defineProps<{
  cells: RuleCell[]
}>()

const text = {
  title: 'Sample 룰',
  subtitle: 'WAFER·LEVEL 외 파라미터는 측정 금지(0) · WF/WAFER 이름 파라미터는 면제'
} as const

interface SampleRow {
  cell: RuleCell
  label: string
  hint?: string
  memory: 'DRAM' | 'NAND' | null
  expanded: boolean
}

const rows = computed<SampleRow[]>(() =>
  (props.cells ?? [])
    .filter(cell => cell?.selector)
    .map((cell): SampleRow => {
      const vehicle = vehicleLabel(cell)
      const family = familyLabel(cell.selector.family)
      const label = [family, vehicle.main].filter(Boolean).join(' · ') || '기본'
      return { cell, label, hint: vehicle.hint, memory: memoryOf(cell), expanded: isExpandedCell(cell) }
    })
    // stable sort: 기본 셀 먼저, phase-keyed 상향 예외는 마지막
    .sort((a, b) => Number(a.expanded) - Number(b.expanded))
)

const overrides = computed(() => collectOverrides(props.cells ?? []))
</script>
