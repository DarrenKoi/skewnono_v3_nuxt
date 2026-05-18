<template>
  <div class="lot-cards">
    <header class="lot-cards__head">
      <div class="lot-cards__heading">
        <span
          class="lot-cards__bar"
          aria-hidden="true"
        />
        <div>
          <h2 class="lot-cards__title">
            Lot Brief Atlas
          </h2>
          <p class="lot-cards__subtitle">
            한 카드 = 한 lot. 카드를 클릭하면 그 자리에 펼쳐져 recipe 와 trend 가 함께 나옵니다.
          </p>
        </div>
      </div>
      <div class="lot-cards__legend">
        <span class="lot-cards__legend-item" data-health="red">
          <span class="lot-cards__legend-dot" /> {{ counts.red }} red
        </span>
        <span class="lot-cards__legend-item" data-health="yellow">
          <span class="lot-cards__legend-dot" /> {{ counts.yellow }} yellow
        </span>
        <span class="lot-cards__legend-item" data-health="green">
          <span class="lot-cards__legend-dot" /> {{ counts.green }} green
        </span>
      </div>
    </header>

    <div class="lot-cards__grid">
      <article
        v-for="row in sortedRows"
        :key="row.lot_cd"
        class="lot-cards__card"
        :class="{ 'lot-cards__card--open': expandedLot === row.lot_cd }"
        :data-health="row.health"
        :aria-expanded="expandedLot === row.lot_cd"
        @click="toggleCard(row.lot_cd)"
      >
        <header class="lot-cards__card-head">
          <div class="lot-cards__card-id">
            <span class="lot-cards__card-lot">{{ row.lot_cd }}</span>
            <CdsemComparisonStageChip :stage="row.dev_stage" :inferred="row.stage_inferred" />
          </div>
          <span class="lot-cards__card-vio">
            <span class="lot-cards__card-vio-num">{{ row.violations }}</span>
            <span class="lot-cards__card-vio-of">/ 4</span>
          </span>
        </header>

        <div class="lot-cards__card-meta">
          <span class="lot-cards__card-avail">
            <span class="lot-cards__card-avail-num">{{ row.avail_recipe }}</span>
            <span class="lot-cards__card-avail-lbl">recipes</span>
          </span>
          <span class="lot-cards__card-ctn" :title="row.ctn_desc">{{ row.ctn_desc || '—' }}</span>
        </div>

        <div class="lot-cards__card-bar">
          <CdsemComparisonStackedBar :row="row" :height="20" :show-values="true" />
        </div>

        <footer class="lot-cards__card-foot">
          <CdsemComparisonTrendChart
            :trend="trend"
            :bucket="bucket"
            :focused-lot="row.lot_cd"
            :compact="true"
            default-mode="lines"
            class="lot-cards__card-spark"
          />
        </footer>

        <!-- Expanded detail -->
        <section v-if="expandedLot === row.lot_cd" class="lot-cards__card-expand" @click.stop>
          <div class="lot-cards__card-expand-head">
            <h3 class="lot-cards__card-expand-title">
              recipe · {{ row.lot_cd }}
            </h3>
            <UButton
              size="xs"
              color="neutral"
              variant="ghost"
              icon="i-lucide-x"
              @click.stop="expandedLot = null"
            />
          </div>
          <div class="lot-cards__recipe-table-wrap">
            <table
              v-if="recipesFor(row.lot_cd).length > 0"
              class="lot-cards__recipe-table"
            >
              <thead>
                <tr>
                  <th
                    v-for="column in recipeColumns"
                    :key="column.key"
                    :aria-sort="ariaSort(column.key)"
                    :class="{ 'lot-cards__recipe-th--numeric': column.numeric }"
                    scope="col"
                  >
                    <button
                      type="button"
                      class="lot-cards__recipe-sort"
                      :class="{ 'lot-cards__recipe-sort--active': recipeSort.key === column.key }"
                      @click="toggleRecipeSort(column.key)"
                    >
                      <span>{{ column.label }}</span>
                      <UIcon
                        :name="recipeSort.key === column.key && recipeSort.dir === 'asc' ? 'i-lucide-arrow-up' : 'i-lucide-arrow-down'"
                        class="lot-cards__recipe-sort-icon"
                        :class="{ 'lot-cards__recipe-sort-icon--muted': recipeSort.key !== column.key }"
                      />
                    </button>
                  </th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="r in sortedRecipesFor(row.lot_cd)"
                  :key="`${r.recipe_id}-${r.oper_id}-${r.oper_seq}`"
                >
                  <td class="lot-cards__recipe-id">
                    {{ r.recipe_id }}
                  </td>
                  <td class="lot-cards__recipe-oper">
                    {{ r.oper_id }}
                  </td>
                  <td class="lot-cards__recipe-number">
                    {{ r.para_16 }}
                  </td>
                  <td class="lot-cards__recipe-number">
                    {{ r.para_13 }}
                  </td>
                  <td class="lot-cards__recipe-number">
                    {{ r.para_9 }}
                  </td>
                  <td class="lot-cards__recipe-number">
                    {{ r.para_5 }}
                  </td>
                  <td class="lot-cards__recipe-total">
                    {{ recipeParamTotal(r) }}
                  </td>
                </tr>
              </tbody>
            </table>
            <p v-else class="lot-cards__recipe-empty">
              이 lot 의 recipe 가 현재 bucket 에 없습니다.
            </p>
          </div>
        </section>
      </article>

      <p v-if="rows.length === 0" class="lot-cards__empty">
        표시할 lot 이 없습니다. 다른 bucket 을 선택해 보세요.
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import type { HealthAugmentedRow } from '~/composables/useLotHealthMock'
import type {
  RecipeInfoRow,
  RecipeTrendResponse,
  SummaryBucketKey
} from '~/composables/useRecipeStatisticsApi'
import { healthOrder, healthSwatches } from './healthTokens'

const props = defineProps<{
  rows: HealthAugmentedRow[]
  bucket: SummaryBucketKey
  recipeRows: RecipeInfoRow[]
  trend: RecipeTrendResponse | null
}>()

const expandedLot = ref<string | null>(null)

type RecipeSortKey = 'recipe_id' | 'oper_id' | 'para_16' | 'para_13' | 'para_9' | 'para_5' | 'para_all'
type SortDirection = 'asc' | 'desc'

const recipeColumns = [
  { key: 'recipe_id', label: 'recipe_id', numeric: false },
  { key: 'oper_id', label: 'oper_id', numeric: false },
  { key: 'para_16', label: 'para_16', numeric: true },
  { key: 'para_13', label: 'para_13', numeric: true },
  { key: 'para_9', label: 'para_9', numeric: true },
  { key: 'para_5', label: 'para_5', numeric: true },
  { key: 'para_all', label: 'param_total', numeric: true }
] as const satisfies readonly { key: RecipeSortKey, label: string, numeric: boolean }[]

const recipeSort = ref<{ key: RecipeSortKey, dir: SortDirection }>({
  key: 'para_all',
  dir: 'desc'
})

const sortedRows = computed(() =>
  [...props.rows].sort((a, b) => {
    const da = healthOrder[a.health] - healthOrder[b.health]
    if (da !== 0) return da
    return b.violation_ratio - a.violation_ratio
  })
)

const counts = computed(() => ({
  red: props.rows.filter(r => r.health === 'red').length,
  yellow: props.rows.filter(r => r.health === 'yellow').length,
  green: props.rows.filter(r => r.health === 'green').length
}))

const recipesByLot = computed(() => {
  const map = new Map<string, RecipeInfoRow[]>()
  for (const r of props.recipeRows) {
    const list = map.get(r.lot_cd)
    if (list) list.push(r)
    else map.set(r.lot_cd, [r])
  }
  return map
})

const toggleCard = (lotCd: string) => {
  expandedLot.value = expandedLot.value === lotCd ? null : lotCd
}

const recipesFor = (lotCd: string): RecipeInfoRow[] => recipesByLot.value.get(lotCd) ?? []

const defaultRecipeSortDir = (key: RecipeSortKey): SortDirection =>
  recipeColumns.find(column => column.key === key)?.numeric ? 'desc' : 'asc'

const recipeParamTotal = (row: RecipeInfoRow): number =>
  row.para_16 + row.para_13 + row.para_9 + row.para_5

const recipeSortValue = (row: RecipeInfoRow, key: RecipeSortKey): string | number => {
  if (key === 'para_all') return recipeParamTotal(row)
  return row[key]
}

const sortedRecipesFor = (lotCd: string): RecipeInfoRow[] => {
  const { key, dir } = recipeSort.value
  const direction = dir === 'asc' ? 1 : -1

  return [...recipesFor(lotCd)].sort((a, b) => {
    const av = recipeSortValue(a, key)
    const bv = recipeSortValue(b, key)

    if (typeof av === 'number' && typeof bv === 'number') {
      const diff = av - bv
      if (diff !== 0) return diff * direction
    } else {
      const diff = String(av).localeCompare(String(bv), undefined, { numeric: true })
      if (diff !== 0) return diff * direction
    }

    return a.recipe_id.localeCompare(b.recipe_id, undefined, { numeric: true })
      || a.oper_id.localeCompare(b.oper_id, undefined, { numeric: true })
      || a.oper_seq - b.oper_seq
  })
}

const toggleRecipeSort = (key: RecipeSortKey) => {
  recipeSort.value = recipeSort.value.key === key
    ? { key, dir: recipeSort.value.dir === 'asc' ? 'desc' : 'asc' }
    : { key, dir: defaultRecipeSortDir(key) }
}

const ariaSort = (key: RecipeSortKey): 'ascending' | 'descending' | 'none' => {
  if (recipeSort.value.key !== key) return 'none'
  return recipeSort.value.dir === 'asc' ? 'ascending' : 'descending'
}
</script>

<style scoped>
.lot-cards {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.lot-cards__head {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  gap: 12px;
  padding: 0 4px;
}

.lot-cards__heading {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  min-width: 0;
}

.lot-cards__bar {
  flex: none;
  width: 4px;
  height: 44px;
  margin-top: 4px;
  border-radius: 2px;
  background: var(--sk-accent);
}

.lot-cards__title {
  font: 700 22px/1.05 var(--font-sans);
  letter-spacing: -0.012em;
  color: var(--sk-ink);
  margin-top: 4px;
}

.lot-cards__subtitle {
  font: 500 12px/1.4 var(--font-sans);
  color: var(--sk-ink-muted);
  margin-top: 2px;
}

.lot-cards__legend {
  display: flex;
  gap: 10px;
}

.lot-cards__legend-item {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 4px 10px;
  border-radius: 999px;
  background: var(--sk-muted-surface);
  font: 600 10.5px/1 var(--font-mono);
  letter-spacing: 0.06em;
  color: var(--sk-ink-muted);
  box-shadow: inset 0 0 0 1px var(--sk-border);
}

.lot-cards__legend-dot {
  width: 7px;
  height: 7px;
  border-radius: 999px;
}

.lot-cards__legend-item[data-health="red"]    .lot-cards__legend-dot { background: v-bind('healthSwatches.red.dot'); }
.lot-cards__legend-item[data-health="yellow"] .lot-cards__legend-dot { background: v-bind('healthSwatches.yellow.dot'); }
.lot-cards__legend-item[data-health="green"]  .lot-cards__legend-dot { background: v-bind('healthSwatches.green.dot'); }

.lot-cards__grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 14px;
}

.lot-cards__card {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 14px 14px 12px;
  border-radius: 14px;
  border: 1px solid var(--sk-border);
  background: var(--sk-surface);
  cursor: pointer;
  text-align: left;
  transition: transform 160ms ease, box-shadow 160ms ease, border-color 160ms ease;
  overflow: hidden;
}

.lot-cards__card::before {
  content: '';
  position: absolute;
  top: 0; left: 0;
  width: 100%;
  height: 4px;
  background: var(--health-edge, transparent);
  opacity: 0.85;
}

.lot-cards__card[data-health="red"]    { --health-edge: v-bind('healthSwatches.red.edge'); }
.lot-cards__card[data-health="yellow"] { --health-edge: v-bind('healthSwatches.yellow.edge'); }
.lot-cards__card[data-health="green"]  { --health-edge: v-bind('healthSwatches.green.edge'); }

.lot-cards__card:hover {
  transform: translateY(-1px);
  box-shadow:
    0 12px 24px -16px rgba(0, 0, 0, 0.2),
    0 2px 0 rgba(0, 0, 0, 0.02);
  border-color: var(--sk-accent-border);
}

.lot-cards__card--open {
  grid-column: 1 / -1;
  cursor: default;
}

.lot-cards__card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.lot-cards__card-id {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.lot-cards__card-lot {
  font: 700 15px/1 var(--font-mono);
  letter-spacing: -0.01em;
  color: var(--sk-ink);
  font-variant-numeric: tabular-nums;
}

.lot-cards__card-vio {
  display: inline-flex;
  align-items: baseline;
  padding: 3px 9px;
  border-radius: 9px;
  background: var(--sk-surface);
  box-shadow: inset 0 0 0 1px var(--sk-border);
  font: 600 11px/1 var(--font-mono);
  color: var(--sk-ink-muted);
}

.lot-cards__card[data-health="red"]    .lot-cards__card-vio { color: oklch(0.42 0.13 30); box-shadow: inset 0 0 0 1px oklch(0.62 0.16 30 / 0.4); }
.lot-cards__card[data-health="yellow"] .lot-cards__card-vio { color: oklch(0.46 0.10 70); box-shadow: inset 0 0 0 1px oklch(0.66 0.13 75 / 0.4); }

.lot-cards__card-vio-num {
  font-size: 14px;
  font-weight: 700;
}

.lot-cards__card-vio-of {
  opacity: 0.66;
  font-size: 10.5px;
  margin-left: 1px;
}

.lot-cards__card-meta {
  display: flex;
  align-items: baseline;
  gap: 8px;
}

.lot-cards__card-avail {
  display: inline-flex;
  align-items: baseline;
  gap: 3px;
  white-space: nowrap;
}

.lot-cards__card-avail-num {
  font: 700 13px/1 var(--font-mono);
  font-variant-numeric: tabular-nums;
  color: var(--sk-ink);
}

.lot-cards__card-avail-lbl {
  font: 500 9.5px/1 var(--font-mono);
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--sk-ink-subtle);
}

.lot-cards__card-ctn {
  font: 400 10.5px/1.3 var(--font-sans);
  color: var(--sk-ink-subtle);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  min-width: 0;
  flex: 1;
}

.lot-cards__card-foot {
  margin-top: 2px;
}

.lot-cards__card-expand {
  margin-top: 6px;
  padding: 10px;
  border-radius: 10px;
  background: var(--sk-muted-surface);
  box-shadow: inset 0 0 0 1px var(--sk-border-soft);
  animation: lot-cards-fade 200ms ease-out;
}

@keyframes lot-cards-fade {
  from { opacity: 0; transform: translateY(-2px); }
  to   { opacity: 1; transform: translateY(0); }
}

.lot-cards__card-expand-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}

.lot-cards__card-expand-title {
  font: 600 11.5px/1 var(--font-sans);
  color: var(--sk-ink);
}

.lot-cards__recipe-table-wrap {
  overflow-x: auto;
  border-radius: 8px;
  background: var(--sk-surface);
  box-shadow: inset 0 0 0 1px var(--sk-border-soft);
}

.lot-cards__recipe-table {
  width: 100%;
  min-width: 760px;
  border-collapse: collapse;
  font: 500 11px/1.2 var(--font-mono);
  font-variant-numeric: tabular-nums;
}

.lot-cards__recipe-table th,
.lot-cards__recipe-table td {
  padding: 7px 9px;
  border-bottom: 1px solid var(--sk-border-soft);
  white-space: nowrap;
}

.lot-cards__recipe-table th {
  background: color-mix(in oklch, var(--sk-muted-surface), var(--sk-surface) 42%);
  color: var(--sk-ink-muted);
  font-weight: 700;
  text-align: left;
}

.lot-cards__recipe-table tbody tr:last-child td {
  border-bottom: 0;
}

.lot-cards__recipe-table tbody tr:hover {
  background: var(--sk-muted-surface);
}

.lot-cards__recipe-th--numeric,
.lot-cards__recipe-number,
.lot-cards__recipe-total {
  text-align: right;
}

.lot-cards__recipe-sort {
  display: inline-flex;
  width: 100%;
  align-items: center;
  justify-content: flex-start;
  gap: 4px;
  padding: 0;
  border: 0;
  background: transparent;
  color: inherit;
  cursor: pointer;
  font: inherit;
  text-align: inherit;
}

.lot-cards__recipe-th--numeric .lot-cards__recipe-sort {
  justify-content: flex-end;
}

.lot-cards__recipe-sort--active {
  color: var(--sk-ink);
}

.lot-cards__recipe-sort-icon {
  width: 12px;
  height: 12px;
  flex: none;
}

.lot-cards__recipe-sort-icon--muted {
  opacity: 0.28;
}

.lot-cards__recipe-id {
  color: var(--sk-ink);
  font-weight: 600;
}

.lot-cards__recipe-oper {
  color: var(--sk-ink-muted);
}

.lot-cards__recipe-number {
  color: var(--sk-ink-muted);
}

.lot-cards__recipe-total {
  color: var(--sk-ink);
  font-weight: 700;
}

.lot-cards__recipe-empty {
  font: 500 11px/1.4 var(--font-sans);
  color: var(--sk-ink-subtle);
  text-align: center;
  padding: 6px 0;
}

.lot-cards__empty {
  grid-column: 1 / -1;
  padding: 28px 14px;
  font: 500 13px/1.5 var(--font-sans);
  color: var(--sk-ink-subtle);
  text-align: center;
}
</style>
