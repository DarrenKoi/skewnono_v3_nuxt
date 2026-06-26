<template>
  <div class="overflow-x-auto">
    <table class="w-full border-collapse">
      <thead>
        <tr class="border-b border-(--sk-border)">
          <th class="px-3 py-1.5 text-left font-mono text-[11px] font-semibold tracking-wide text-(--sk-ink-muted) uppercase">
            룰 셀
          </th>
          <th
            v-for="column in CAP_COLUMNS"
            :key="column.key"
            class="px-2 py-1.5 text-center font-mono text-[11px] font-semibold tracking-wide text-(--sk-ink-muted) uppercase"
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
              class="px-3 pt-2.5 pb-0.5 text-left font-mono text-[11px] font-bold tracking-wide text-(--sk-ink-muted) uppercase"
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
              class="px-3 py-1 pl-6 text-left text-[11.5px] text-(--sk-ink-subtle)"
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
import { CAP_COLUMNS, familyLabel, overrideLabel } from '~/utils/ruleMatrix'

// Editable matrix (D13) — read-only for step 2. Rows = rule cells grouped by
// family (R3) or recipe_class (M-fab, D15); columns = parameter types.
const props = defineProps<{
  cells: RuleCell[]
  // M-fab collapses family/phase axes — group by recipe_class instead (D15).
  mfab: boolean
}>()

interface RuleGroup {
  key: string
  label: string
  cells: RuleCell[]
  overrides: NameOverride[]
}

const groupKeyOf = (cell: RuleCell): string => {
  if (cell.selector.recipe_class === 'Sample') return 'Sample'
  if (props.mfab) return 'Main'
  return cell.selector.family ?? 'Main'
}

const groupLabelOf = (key: string): string => {
  if (key === 'Sample') return 'Sample'
  if (key === 'Main') return 'Main'
  return familyLabel(key)
}

// Group order is fixed so the matrix layout is stable regardless of cell order.
const GROUP_ORDER_R3 = ['Core', 'Pool', 'VG_RTC_Cubic', 'Sample']
const GROUP_ORDER_MFAB = ['Main', 'Sample']

// Collect every distinct name-override across a group's cells (by signature),
// rather than trusting cells[0] — robust if a group ever holds mixed overrides.
const collectOverrides = (cells: RuleCell[]): NameOverride[] => {
  const seen = new Set<string>()
  const out: NameOverride[] = []
  for (const cell of cells) {
    for (const ov of cell.name_overrides ?? []) {
      const sig = JSON.stringify(ov)
      if (seen.has(sig)) continue
      seen.add(sig)
      out.push(ov)
    }
  }
  return out
}

const groups = computed<RuleGroup[]>(() => {
  const byKey = new Map<string, RuleCell[]>()
  // Guard against a malformed payload (truthy but missing/!array cells, or a
  // cell with no selector) — degrade to an empty matrix instead of throwing.
  for (const cell of props.cells ?? []) {
    if (!cell?.selector) continue
    const key = groupKeyOf(cell)
    const bucket = byKey.get(key)
    if (bucket) bucket.push(cell)
    else byKey.set(key, [cell])
  }

  const order = props.mfab ? GROUP_ORDER_MFAB : GROUP_ORDER_R3
  const orderedKeys = [
    ...order.filter(key => byKey.has(key)),
    ...[...byKey.keys()].filter(key => !order.includes(key))
  ]

  return orderedKeys.map((key) => {
    const cells = byKey.get(key) ?? []
    // Name-overrides surface once per group (D9/D11), deduped across its cells.
    return {
      key,
      label: groupLabelOf(key),
      cells,
      overrides: collectOverrides(cells)
    }
  })
})
</script>
