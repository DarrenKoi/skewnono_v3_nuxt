<template>
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
        <template
          v-for="group in groups"
          :key="group.key"
        >
          <tr>
            <td
              :colspan="CAP_COLUMNS.length + 1"
              class="px-3 pt-2.5 pb-0.5 text-left sk-eyebrow"
            >
              {{ group.label }}
            </td>
          </tr>
          <EbeamRulesRow
            v-for="cell in group.cells"
            :key="cell.id"
            :cell="cell"
            :columns="CAP_COLUMNS"
          />
          <tr
            v-for="(ov, index) in group.overrides"
            :key="`${group.key}-ov-${index}`"
            class="bg-(--sk-accent-tint)/30"
          >
            <td
              :colspan="CAP_COLUMNS.length + 1"
              class="px-3 py-1 pl-6 text-left text-xs text-(--sk-ink-subtle)"
            >
              ▸ 이름 예외 (기타 파라 전용):
              <code class="font-mono text-(--sk-ink-muted)">{{ overrideLabel(ov) }}</code>
            </td>
          </tr>
        </template>
      </tbody>
    </table>
  </div>
</template>

<script setup lang="ts">
import type { NameOverride, RuleCell } from '~/utils/ruleEngine'
import { CAP_COLUMNS, collectOverrides, familyLabel, overrideLabel } from '~/utils/ruleMatrix'

// Main-rule matrix (D13) — read-only for step 2. Rows = rule cells grouped by
// family; columns = the per-cell cap axes (EDGE / EDGE_EX / 기타). Sample rules
// render in their own table (rules/SampleTable); WAFER·LEVEL are fixed fab-wide
// and live in the header strip, not here.
const props = defineProps<{
  cells: RuleCell[]
}>()

interface RuleGroup {
  key: string
  label: string
  cells: RuleCell[]
  overrides: NameOverride[]
}

// Group order is fixed so the matrix layout is stable regardless of cell order.
const GROUP_ORDER = ['Core', 'Pool', 'VG_RTC_Cubic']

const groups = computed<RuleGroup[]>(() => {
  const byKey = new Map<string, RuleCell[]>()
  // Guard against a malformed payload (truthy but missing/!array cells, or a
  // cell with no selector) — degrade to an empty matrix instead of throwing.
  for (const cell of props.cells ?? []) {
    if (!cell?.selector) continue
    const key = cell.selector.family ?? 'Main'
    const bucket = byKey.get(key)
    if (bucket) bucket.push(cell)
    else byKey.set(key, [cell])
  }

  const orderedKeys = [
    ...GROUP_ORDER.filter(key => byKey.has(key)),
    ...[...byKey.keys()].filter(key => !GROUP_ORDER.includes(key))
  ]

  return orderedKeys.map((key) => {
    const cells = byKey.get(key) ?? []
    // Name-overrides surface once per group (D9/D11), deduped across its cells.
    return {
      key,
      label: familyLabel(key) || key,
      cells,
      overrides: collectOverrides(cells)
    }
  })
})
</script>
