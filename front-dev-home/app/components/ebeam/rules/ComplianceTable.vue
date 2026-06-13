<template>
  <div class="dashboard-surface rounded-2xl p-4">
    <div class="mb-3 flex flex-wrap items-center justify-between gap-2">
      <h3 class="text-[12.5px] font-semibold text-(--sk-ink)">
        {{ text.title }}
      </h3>
      <span class="text-[11px] text-(--sk-ink-muted)">
        {{ text.legend }}
      </span>
    </div>

    <div
      v-if="r3Lots.length === 0"
      class="px-4 py-12 text-center text-sm text-(--sk-ink-muted)"
    >
      {{ text.empty }}
    </div>
    <div
      v-else-if="pending"
      class="flex items-center justify-center gap-2 py-12 text-sm text-(--sk-ink-muted)"
    >
      <UIcon
        name="i-lucide-loader-circle"
        class="h-4 w-4 animate-spin"
      />
      {{ text.loading }}
    </div>
    <div
      v-else-if="error"
      class="py-12 text-center text-sm text-rose-600 dark:text-rose-300"
    >
      {{ text.loadError }}
    </div>
    <table
      v-else
      class="w-full border-collapse"
    >
      <thead>
        <tr class="border-b border-(--sk-border)">
          <th class="px-3 py-2 text-left font-mono text-[11px] font-semibold uppercase tracking-wide text-(--sk-ink-muted)">
            디바이스
          </th>
          <th class="px-2 py-2 text-right font-mono text-[11px] font-semibold uppercase tracking-wide text-(--sk-ink-muted)">
            recipe
          </th>
          <th class="px-2 py-2 text-right font-mono text-[11px] font-semibold uppercase tracking-wide text-(--sk-ink-muted)">
            위반 recipe
          </th>
          <th class="px-2 py-2" />
        </tr>
      </thead>
      <tbody>
        <tr
          v-for="dev in deviceRows"
          :key="dev.lot_cd"
          class="border-t border-(--sk-border) transition-colors hover:bg-(--sk-accent-tint)/40"
        >
          <td class="px-3 py-1.5 font-mono text-[12.5px] text-(--sk-ink)">
            {{ dev.lot_cd }}
          </td>
          <td class="px-2 py-1.5 text-right font-mono text-[12.5px] tabular-nums text-(--sk-ink-muted)">
            {{ dev.recipe_count }}
          </td>
          <td class="px-2 py-1.5 text-right">
            <span
              class="inline-flex h-5 min-w-7 items-center justify-center rounded px-1.5 font-mono text-[11px] font-semibold tabular-nums"
              :class="dev.violation_count > 0
                ? 'bg-rose-100 text-rose-700 dark:bg-rose-950/50 dark:text-rose-300'
                : 'bg-(--sk-surface) text-(--sk-ink-subtle)'"
            >{{ dev.violation_count }}</span>
          </td>
          <td class="px-2 py-1.5 text-right">
            <UButton
              size="xs"
              color="neutral"
              variant="outline"
              :label="text.details"
              @click="openDrill(dev.lot_cd)"
            />
          </td>
        </tr>
      </tbody>
    </table>

    <EbeamDevstatDrillSlideover
      v-model:open="drillOpen"
      :device="activeDrill"
      highlight-label="위반"
    />
  </div>
</template>

<script setup lang="ts">
import type { RecipeInput, RuleCell } from '~/utils/ruleEngine'
import { evaluateLot } from '~/utils/ruleEngine'
import { toViolationDrill, type DrillDevice } from '~/utils/deviceDrill'

const props = defineProps<{ cells: RuleCell[] }>()

const { fetchRecipeParams } = useDeviceStatisticsApi()
const { selectedDeviceLots } = useDeviceCart()

// Compliance is R3-only (D22). Filter the cart to R3 lots (lot_cd starts with 'R').
const r3Lots = computed(() => selectedDeviceLots.value.filter(lot => lot.startsWith('R')))

const text = {
  title: 'R3 룰 준수',
  legend: '선택한 R3 디바이스의 recipe 별 cap 준수 결과 · 위반 recipe 수',
  details: '자세히',
  empty: '디바이스 통계에서 R3 디바이스를 선택하면 룰 준수 결과가 표시됩니다.',
  loading: '로딩 중',
  loadError: '데이터를 불러오지 못했습니다.'
} as const

const { data, pending, error } = await useAsyncData<RecipeInput[]>(
  'r3-compliance',
  () => r3Lots.value.length ? fetchRecipeParams(r3Lots.value) : Promise.resolve([]),
  { watch: [r3Lots] }
)

const recipesByLot = computed(() => {
  const map = new Map<string, RecipeInput[]>()
  for (const r of data.value ?? []) {
    const bucket = map.get(r.lot_cd)
    if (bucket) bucket.push(r)
    else map.set(r.lot_cd, [r])
  }
  return map
})

interface ComplianceRow { lot_cd: string, recipe_count: number, violation_count: number }

const deviceRows = computed<ComplianceRow[]>(() => {
  const rows: ComplianceRow[] = []
  for (const lot_cd of r3Lots.value) {
    const recipes = recipesByLot.value.get(lot_cd) ?? []
    const health = evaluateLot(lot_cd, recipes, props.cells)
    rows.push({ lot_cd, recipe_count: recipes.length, violation_count: health.violation_recipes })
  }
  return rows.sort((a, b) => b.violation_count - a.violation_count)
})

const drillOpen = ref(false)
const activeDrill = ref<DrillDevice | null>(null)

const openDrill = (lot_cd: string) => {
  const recipes = recipesByLot.value.get(lot_cd) ?? []
  const health = evaluateLot(lot_cd, recipes, props.cells)
  activeDrill.value = toViolationDrill(lot_cd, recipes[0]?.ctn_desc ?? '', health)
  drillOpen.value = true
}
</script>
