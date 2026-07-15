<template>
  <div class="dashboard-surface rounded-2xl p-3">
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
            <th class="px-3 py-1.5 text-left sk-eyebrow">
              룰 셀
            </th>
            <th
              v-for="column in CAP_COLUMNS"
              :key="column.key"
              class="px-2 py-1.5 text-center sk-eyebrow"
            >
              {{ column.label }}
            </th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="row in rows"
            :key="row.cell.id"
            class="border-t border-(--sk-border) transition-colors hover:bg-(--sk-accent-tint)/40"
          >
            <td class="px-3 py-1 text-left whitespace-nowrap">
              <div class="flex items-center gap-2">
                <span
                  class="text-[12.5px]"
                  :class="row.label === '기본' ? 'text-(--sk-ink-subtle)' : 'font-medium text-(--sk-ink)'"
                >{{ row.label }}</span>
                <span
                  v-if="row.hint"
                  class="text-[11px] text-(--sk-ink-subtle)"
                >{{ row.hint }}</span>
                <span
                  v-if="row.memory"
                  class="inline-flex h-5 items-center rounded px-1.5 font-mono text-[10px] font-semibold ring-1"
                  :class="row.memory === 'NAND'
                    ? 'bg-amber-50 text-amber-700 ring-amber-200 dark:bg-amber-950/40 dark:text-amber-300 dark:ring-amber-900/60'
                    : 'bg-sky-50 text-sky-700 ring-sky-200 dark:bg-sky-950/40 dark:text-sky-300 dark:ring-sky-900/60'"
                >{{ row.memory }}</span>
              </div>
            </td>
            <td
              v-for="column in CAP_COLUMNS"
              :key="column.key"
              class="px-2 py-1 text-center"
            >
              <EbeamRulesCapCell
                :value="capValue(row.cell, column.key)"
                :emphasis="row.expanded && column.key !== '_other'"
              />
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <p
      v-if="overrides.length > 0"
      class="mt-1.5 px-3 text-xs text-(--sk-ink-subtle)"
    >
      ▸ 이름 예외 (기타 파라 전용):
      <code
        v-for="(ov, index) in overrides"
        :key="index"
        class="font-mono text-(--sk-ink-muted)"
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
