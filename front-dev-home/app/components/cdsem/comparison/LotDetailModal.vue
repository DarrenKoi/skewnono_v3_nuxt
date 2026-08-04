<template>
  <UModal
    v-model:open="open"
    :title="row?.lot_cd ?? ''"
    :ui="modalUi"
  >
    <template #body>
      <div
        v-if="row"
        class="space-y-4"
      >
        <!-- 헤더 3줄. 예전에는 lot · stage · health · violations · recipe ·
             description 이 mono 11px 한 줄에 모두 들어가 있었습니다. -->
        <div class="flex items-stretch gap-3">
          <span
            class="w-[5px] flex-none rounded-[2px]"
            :style="{ background: healthStripeColor(row.verdict.health) }"
            aria-hidden="true"
          />
          <div class="min-w-0 flex-1">
            <div class="flex flex-wrap items-center gap-2">
              <span class="font-mono text-[22px] font-extrabold leading-tight tracking-tight tabular-nums text-(--sk-ink)">{{ row.lot_cd }}</span>
              <span
                v-if="row.verdict.health"
                class="sk-badge sk-badge-lg font-bold"
                :style="healthBadgeStyle(row.verdict.health, isDark)"
              >{{ row.verdict.health }}</span>
              <span
                v-else
                class="sk-badge sk-badge-lg bg-(--sk-muted-surface) text-(--sk-ink-subtle) ring-1 ring-(--sk-border) ring-inset"
              >{{ text.noRules }}</span>
              <CdsemComparisonStageChip
                :stage="row.dev_stage"
                :inferred="row.stage_inferred"
                large
              />
              <span class="sk-badge sk-badge-lg bg-(--sk-accent-tint) text-(--sk-accent) ring-1 ring-(--sk-accent-border) ring-inset">{{ bucket }}</span>
            </div>

            <p class="mt-1.5 sk-card-desc">
              {{ row.ctn_desc || '—' }}
            </p>

            <div class="mt-2 flex flex-wrap gap-x-5 gap-y-0.5">
              <span class="sk-field-label">
                {{ text.violations }}
                <span
                  v-if="row.verdict.kind === 'judged'"
                  class="sk-field-value font-semibold text-(--sk-ink)"
                >{{ row.verdict.violation_recipes }} / {{ row.verdict.judged_recipes }} recipe</span>
                <span
                  v-else
                  class="sk-field-value"
                >—</span>
              </span>
              <span
                v-if="row.verdict.gray_recipes > 0"
                class="sk-field-label"
              >
                {{ text.grayRecipes }}
                <span class="sk-field-value">{{ row.verdict.gray_recipes }}</span>
              </span>
              <span class="sk-field-label">
                {{ text.recipeRatio }}
                <span class="sk-field-value">{{ row.avail_recipe }} / {{ row.total_recipe }}</span>
              </span>
            </div>
          </div>
        </div>

        <div class="space-y-2">
          <div class="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
            <span class="sk-field-label">{{ text.paraDist }}</span>
            <div class="flex flex-wrap items-center gap-3">
              <span
                v-for="key in paraOrder"
                :key="key"
                class="inline-flex items-center gap-1.5 font-mono text-[13px] text-(--sk-ink-muted)"
              >
                <span
                  class="h-2.5 w-2.5 rounded-[3px]"
                  :style="{ background: paraPalette[key] }"
                />
                {{ key }}
              </span>
            </div>
          </div>
          <CdsemComparisonStackedBar
            :row="row"
            :label="row.lot_cd"
            :height="26"
            :show-values="true"
          />
        </div>

        <CdsemComparisonTrendChart
          :trend="trend"
          :bucket="bucket"
          :focused-lot="row.lot_cd"
        />

        <div class="space-y-2">
          <div class="flex flex-wrap items-baseline gap-x-2.5 gap-y-1">
            <p class="sk-panel-title">
              recipe
            </p>
            <span class="sk-field-name">{{ row.lot_cd }}</span>
            <span class="sk-field-label">{{ lotRecipes.length }}건</span>
          </div>

          <div
            v-if="sortedRecipes.length > 0"
            class="space-y-2"
          >
            <!-- 10열 표를 카드로. recipe_id 가 제목, oper_desc 는 잘리지 않고,
                 seq 는 라벨 달린 메타 줄, para 분포는 오른쪽 블록입니다. -->
            <div
              v-for="recipe in sortedRecipes"
              :key="recipe.recipe_id"
              class="flex flex-wrap items-start gap-x-5 gap-y-3 rounded-xl bg-(--sk-surface) px-4 py-3 ring-1 ring-(--sk-border-soft)"
              :class="{ 'opacity-60': recipe.para_all === 0 }"
            >
              <div class="min-w-0 flex-1">
                <div class="flex flex-wrap items-center gap-2">
                  <span class="font-mono text-[17px] font-bold leading-tight tracking-tight text-(--sk-ink)">{{ recipe.recipe_id }}</span>
                  <span class="sk-badge bg-(--sk-muted-surface) text-(--sk-ink-muted) ring-1 ring-(--sk-border) ring-inset">{{ recipe.oper_id }}</span>
                </div>
                <p class="mt-1.5 sk-card-desc">
                  {{ recipe.oper_desc || '—' }}
                </p>
                <div class="mt-2 flex flex-wrap gap-x-5 gap-y-0.5">
                  <span class="sk-field-label">
                    oper_seq <span class="sk-field-value">{{ recipe.oper_seq }}</span>
                  </span>
                  <span class="sk-field-label">
                    samp_seq <span class="sk-field-value">{{ recipe.samp_seq }}</span>
                  </span>
                </div>
              </div>

              <div class="w-50 flex-none">
                <div class="mb-1.5 flex items-baseline justify-between gap-2">
                  <span class="sk-field-label">{{ text.paraDist }}</span>
                  <span class="sk-field-value text-[15px] font-semibold text-(--sk-ink)">{{ recipe.para_all }}</span>
                </div>
                <CdsemComparisonStackedBar
                  v-if="recipe.para_all > 0"
                  :row="recipe"
                  :label="recipe.recipe_id"
                  :height="18"
                  :normalize="false"
                  :max-total="maxRecipeParaTotal"
                />
                <p
                  v-else
                  class="sk-field-label"
                >
                  {{ text.noParams }}
                </p>
              </div>
            </div>

            <p class="sk-caption px-1">
              {{ text.seqCaveat }}
            </p>
          </div>
          <p
            v-else
            class="py-2 text-center sk-body text-(--sk-ink-muted)"
          >
            {{ text.recipeEmpty }}
          </p>
        </div>
      </div>
    </template>
  </UModal>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useColorMode } from '#imports'
import type { HealthAugmentedRow } from '~/utils/lotHealth'
import type {
  RecipeInfoRow,
  RecipeTrendResponse,
  SummaryBucketKey
} from '~/composables/useRecipeStatisticsApi'

import { healthBadgeStyle, healthStripeColor, paraColors, paraColorsDark, paraOrder } from './healthTokens'

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
  noParams: '파라미터 없음',
  violations: '위반',
  grayRecipes: '판정 제외',
  recipeRatio: '운용 / 전체 recipe',
  paraDist: 'para 분포',
  // M 계열은 원천에 순서 field 가 없어 oper_seq/samp_seq 를 공정 접두사 순위로
  // 합성합니다 — 화면 표기 의무 (docs/datatables/ebeam_tas_lot_hist.txt ★).
  seqCaveat: 'M 계열 fab 의 oper_seq · samp_seq 는 합성값으로, 실제 운영 공정 순서를 반영하지 않습니다.'
} as const

// title 은 prop 으로 계속 넘깁니다 — Reka 의 DialogTitle 이 대화상자의 접근
// 가능한 이름이라, 지우면 스크린 리더에 이름 없는 창이 열립니다. 다만 화면
// 에서는 감춥니다: 바로 아래 본문 헤더가 같은 lot 코드를 22px 로 다시 씁니다.
const modalUi = {
  content: 'w-[95vw] sm:max-w-[1400px] sm:max-h-[calc(100dvh-2rem)]',
  title: 'sr-only'
} as const

const colorMode = useColorMode()
const isDark = computed(() => colorMode.value === 'dark')
const paraPalette = computed(() => isDark.value ? paraColorsDark : paraColors)

const lotRecipes = computed<RecipeInfoRow[]>(() => {
  const lotCd = props.row?.lot_cd
  if (!lotCd) return []
  return props.recipeRows.filter(r => r.lot_cd === lotCd)
})

// 표가 정렬 헤더로 하던 일을 카드에서는 기본 순서 하나가 대신합니다 —
// 파라미터가 많은 recipe 가 먼저입니다(표의 기본 정렬과 같습니다).
const sortedRecipes = computed(() =>
  [...lotRecipes.value].sort((a, b) => b.para_all - a.para_all || a.recipe_id.localeCompare(b.recipe_id))
)

// 카드마다 막대를 제 합계로 정규화하면 파라미터 3개짜리 recipe 와 40개짜리
// recipe 의 막대가 똑같이 꽉 차 보입니다. lot 안에서 서로 비교되도록 최대값을
// 공유합니다.
const maxRecipeParaTotal = computed(() => Math.max(0, ...lotRecipes.value.map(r => r.para_all)))
</script>
