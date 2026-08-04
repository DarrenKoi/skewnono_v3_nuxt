<template>
  <UModal
    v-model:open="open"
    :title="row?.lot_cd ?? ''"
    :ui="{ content: 'w-[95vw] sm:max-w-[1400px] sm:max-h-[calc(100dvh-2rem)]' }"
  >
    <template #body>
      <div
        v-if="row"
        class="space-y-4"
      >
        <div class="flex flex-wrap items-center gap-x-3 gap-y-2">
          <span class="font-mono text-[15px] font-bold tabular-nums text-(--sk-ink)">{{ row.lot_cd }}</span>
          <CdsemComparisonStageChip
            :stage="row.dev_stage"
            :inferred="row.stage_inferred"
          />
          <span
            v-if="row.verdict.health"
            class="inline-flex items-center gap-1.5"
          >
            <span
              class="h-2 w-2 rounded-full"
              :style="{ background: healthSwatches[row.verdict.health].dot }"
            />
            <span class="font-mono text-[11px] font-semibold text-(--sk-ink-muted)">{{ row.verdict.health }}</span>
          </span>
          <span
            v-else
            class="inline-flex items-center gap-1.5"
          >
            <span class="h-2 w-2 rounded-full bg-(--sk-border)" />
            <span class="font-mono text-[11px] font-medium text-(--sk-ink-subtle)">{{ text.noRules }}</span>
          </span>
          <span
            v-if="row.verdict.kind === 'judged'"
            class="font-mono text-[11px] tabular-nums text-(--sk-ink-muted)"
          >
            violations <span class="font-bold text-(--sk-ink)">{{ row.verdict.violation_recipes }}</span>
            / {{ row.verdict.judged_recipes }} recipe
            <span
              v-if="row.verdict.gray_recipes > 0"
              class="text-(--sk-ink-subtle)"
            >(판정 제외 {{ row.verdict.gray_recipes }})</span>
          </span>
          <span class="font-mono text-[11px] tabular-nums text-(--sk-ink-muted)">
            recipe <span class="font-bold text-(--sk-ink)">{{ row.avail_recipe }}</span> / {{ row.total_recipe }}
          </span>
          <span
            class="min-w-0 flex-1 truncate text-[11px] text-(--sk-ink-subtle)"
            :title="row.ctn_desc"
          >{{ row.ctn_desc || '—' }}</span>
        </div>

        <div class="space-y-1.5">
          <CdsemComparisonStackedBar
            :row="row"
            :height="20"
            :show-values="true"
          />
          <div class="flex flex-wrap items-center gap-3">
            <span
              v-for="key in paraOrder"
              :key="key"
              class="inline-flex items-center gap-1.5 font-mono text-[10px] text-(--sk-ink-muted)"
            >
              <span
                class="h-2 w-2 rounded-[3px]"
                :style="{ background: paraPalette[key] }"
              />
              {{ key }}
            </span>
          </div>
        </div>

        <CdsemComparisonTrendChart
          :trend="trend"
          :bucket="bucket"
          :focused-lot="row.lot_cd"
        />

        <div class="space-y-2">
          <p class="sk-title">
            recipe · {{ row.lot_cd }}
          </p>
          <div
            v-if="lotRecipes.length > 0"
            class="overflow-hidden rounded-lg ring-1 ring-(--sk-border-soft)"
          >
            <UTable
              v-model:sorting="recipeSorting"
              class="max-h-[28rem]"
              :columns="recipeColumns"
              :data="lotRecipes"
              :sorting-options="{ enableMultiSort: false, enableSortingRemoval: false }"
              sticky="header"
              :ui="tableUi"
            >
              <template
                v-for="id in recipeColumnIds"
                :key="id"
                #[`${id}-header`]="{ column }"
              >
                <UButton
                  size="xs"
                  color="neutral"
                  variant="ghost"
                  class="-mx-2 -my-1 h-6 px-2 text-[11px] font-medium text-(--sk-ink-muted) hover:text-(--sk-ink)"
                  :trailing-icon="getSortIcon(column.getIsSorted())"
                  @click="column.toggleSorting(column.getIsSorted() === 'asc')"
                >
                  {{ column.columnDef.header }}
                </UButton>
              </template>

              <template #recipe_id-cell="{ row: r }">
                <span class="font-mono font-semibold text-(--sk-ink)">{{ r.original.recipe_id }}</span>
              </template>

              <template #oper_desc-cell="{ row: r }">
                <span
                  class="block max-w-[200px] truncate text-(--sk-ink-muted)"
                  :title="r.original.oper_desc"
                >{{ r.original.oper_desc || '—' }}</span>
              </template>
            </UTable>
            <p class="border-t border-(--sk-border-soft) px-3 py-1.5 text-[10.5px] text-(--sk-ink-subtle)">
              {{ text.seqCaveat }}
            </p>
          </div>
          <p
            v-else
            class="py-2 text-center text-[11px] font-medium text-(--sk-ink-subtle)"
          >
            {{ text.recipeEmpty }}
          </p>
        </div>
      </div>
    </template>
  </UModal>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useColorMode } from '#imports'
import type { TableColumn } from '@nuxt/ui'
import type { SortingState } from '@tanstack/vue-table'
import type { HealthAugmentedRow } from '~/utils/lotHealth'
import type {
  RecipeInfoRow,
  RecipeTrendResponse,
  SummaryBucketKey
} from '~/composables/useRecipeStatisticsApi'

import { healthSwatches, paraColors, paraColorsDark, paraOrder } from './healthTokens'

const props = defineProps<{
  row: HealthAugmentedRow | null
  bucket: SummaryBucketKey
  recipeRows: RecipeInfoRow[]
  trend: RecipeTrendResponse | null
}>()

const open = defineModel<boolean>('open', { required: true })

const text = {
  recipeEmpty: '이 lot 의 recipe 가 현재 bucket 에 없습니다.',
  noRules: '룰 없음',
  // M 계열은 원천에 순서 field 가 없어 oper_seq/samp_seq 를 공정 접두사 순위로
  // 합성합니다 — 화면 표기 의무 (docs/datatables/ebeam_tas_lot_hist.txt ★).
  seqCaveat: 'M 계열 fab 의 oper_seq · samp_seq 는 합성값으로, 실제 운영 공정 순서를 반영하지 않습니다.'
} as const

const colorMode = useColorMode()
const paraPalette = computed(() => colorMode.value === 'dark' ? paraColorsDark : paraColors)

const lotRecipes = computed<RecipeInfoRow[]>(() => {
  const lotCd = props.row?.lot_cd
  if (!lotCd) return []
  return props.recipeRows.filter(r => r.lot_cd === lotCd)
})

const recipeSorting = ref<SortingState>([{ id: 'para_all', desc: true }])

const recipeColumns: TableColumn<RecipeInfoRow>[] = [
  { accessorKey: 'recipe_id', header: 'recipe_id' },
  { accessorKey: 'oper_id', header: 'oper_id', size: 110 },
  { accessorKey: 'oper_desc', header: 'oper_desc', size: 200 },
  { accessorKey: 'oper_seq', header: 'oper_seq', size: 84 },
  { accessorKey: 'samp_seq', header: 'samp_seq', size: 84 },
  { accessorKey: 'para_16', header: 'para_16', size: 80 },
  { accessorKey: 'para_13', header: 'para_13', size: 80 },
  { accessorKey: 'para_9', header: 'para_9', size: 80 },
  { accessorKey: 'para_5', header: 'para_5', size: 80 },
  { accessorKey: 'para_all', header: 'param_total', size: 96 }
]

const recipeColumnIds = [
  'recipe_id', 'oper_id', 'oper_desc', 'oper_seq', 'samp_seq',
  'para_16', 'para_13', 'para_9', 'para_5', 'para_all'
] as const

const getSortIcon = (direction: false | 'asc' | 'desc') => {
  if (direction === 'asc') return 'i-lucide-arrow-up-narrow-wide'
  if (direction === 'desc') return 'i-lucide-arrow-down-wide-narrow'
  return 'i-lucide-arrow-up-down'
}

const tableUi = {
  tr: 'transition-colors hover:bg-zinc-50 dark:hover:bg-zinc-800/50',
  td: 'py-1.5 px-3 text-[12px] whitespace-nowrap overflow-hidden text-ellipsis tabular-nums text-(--sk-ink)',
  th: 'py-2 px-3 text-[11px] font-medium text-(--sk-ink-muted) bg-zinc-50/60 dark:bg-zinc-900/40'
}
</script>
