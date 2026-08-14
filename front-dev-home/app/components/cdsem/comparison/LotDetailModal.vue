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
              <span
                v-if="outlier && outlier.outlier_count > 0"
                class="sk-field-label"
              >
                {{ text.outlierCount }}
                <span class="sk-field-value font-semibold text-(--sk-bad)">{{ outlier.outlier_count }}</span>
              </span>
              <span
                v-if="outlier && outlier.median > 0"
                class="sk-field-label"
                :title="text.baselineHint"
              >
                {{ text.baseline }}
                <span class="sk-field-value">{{ outlier.median }} · &gt; {{ outlier.threshold }}</span>
              </span>
            </div>
          </div>
        </div>

        <div class="space-y-2">
          <div class="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
            <span class="sk-field-label">{{ text.paraDist }}</span>
            <div class="flex flex-wrap items-center gap-3">
              <!-- 이 모달 어디에도 나타나지 않는 구간은 범례에서도 뺍니다
                   (presentParaKeys). 범례가 색을 소개했는데 아래 recipe 카드
                   어느 막대에도 그 색이 없으면, 읽는 사람은 "내가 못 찾은 건가"
                   를 먼저 의심하게 됩니다. para_over_16 처럼 대부분의 recipe 에서
                   비는 구간이 생기고 나서 실제로 문제가 됐습니다. -->
              <span
                v-for="key in presentParaKeys"
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
          <div class="flex flex-wrap items-center gap-x-2.5 gap-y-1">
            <p class="sk-panel-title">
              recipe
            </p>
            <span class="sk-field-name">{{ row.lot_cd }}</span>
            <span class="sk-field-label">{{ visibleCards.length }}건</span>

            <!-- 화면은 recipe 단위 카드지만, 엑셀로 가져가고 싶은 것은 그
                 아래 파라미터까지 편 표입니다 — 스텝·recipe_id·파라미터·측정
                 point 한 줄씩. 그래서 카드를 그대로 옮기지 않고 한 단계 더
                 편 표를 내보냅니다. -->
            <div class="ml-auto flex items-center gap-2">
              <!-- filter === 'flagged' 도 조건에 넣습니다 — 초과 0 인 상태로
                   '초과만' 이 열리면(오늘은 도달 불가하지만) 이 칩이 없으면
                   전체로 돌아올 컨트롤이 사라집니다. -->
              <div
                v-if="flaggedCardCount > 0 || filter === 'flagged'"
                role="radiogroup"
                :aria-label="text.filterLabel"
                class="flex items-center gap-1.5"
              >
                <button
                  v-for="option in filterOptions"
                  :key="option.value"
                  type="button"
                  role="radio"
                  :aria-checked="filter === option.value"
                  :class="[CHIP_BASE, chipClass(filter === option.value)]"
                  @click="filter = option.value"
                >
                  {{ option.label }}
                  <span
                    v-if="option.value === 'flagged'"
                    class="tabular-nums opacity-70"
                  >{{ flaggedCardCount }}</span>
                </button>
              </div>
              <div
                role="radiogroup"
                aria-label="recipe 정렬"
                class="flex items-center gap-1.5"
              >
                <button
                  v-for="option in sortOptions"
                  :key="option.value"
                  type="button"
                  role="radio"
                  :aria-checked="recipeSort === option.value"
                  :class="[CHIP_BASE, chipClass(recipeSort === option.value)]"
                  @click="recipeSort = option.value"
                >
                  {{ option.label }}
                </button>
              </div>
              <span class="sk-field-label">{{ paramRowCount.toLocaleString() }}행</span>
              <UTooltip :text="text.copyHint">
                <UButton
                  color="neutral"
                  variant="outline"
                  icon="i-lucide-clipboard"
                  class="h-[34px] px-3 text-sm font-semibold"
                  :aria-label="text.copyHint"
                  :disabled="paramRowCount === 0"
                  @click="copyParamTable"
                />
              </UTooltip>
              <UButton
                color="neutral"
                variant="outline"
                icon="i-lucide-download"
                class="h-[34px] px-3.5 text-sm font-semibold"
                :label="text.csvDownload"
                :disabled="paramRowCount === 0"
                @click="downloadParamTable"
              />
            </div>
          </div>

          <div
            v-if="visibleCards.length > 0"
            class="space-y-2"
          >
            <CdsemComparisonStepOutlierCard
              v-for="card in visibleCards"
              :key="card.key"
              :card="card"
              :max-total="maxRecipeParaTotal"
              :expanded="expandedSteps.has(card.key)"
              @toggle="toggleStep(card.key)"
            />

            <p class="sk-caption px-1">
              {{ text.seqCaveat }}
            </p>
          </div>
          <p
            v-else
            class="py-2 text-center sk-body text-(--sk-ink-muted)"
          >
            {{ filter === 'flagged' ? text.emptyFlagged : text.recipeEmpty }}
          </p>
        </div>
      </div>
    </template>
  </UModal>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useColorMode, useToast } from '#imports'
import type { HealthAugmentedRow } from '~/utils/lotHealth'
import type { RecipeInput } from '~/utils/ruleEngine'
import { LOT_PARAM_HEADERS, buildLotParamRows, lotParamFileName } from '~/utils/lotParamExport'
import { copyTableToClipboard, downloadCsv } from '~/utils/csvDownload'
import { CHIP_BASE, chipClass } from '~/utils/chipClass'
import { sortSteps, type RecipeSortKey } from '~/utils/recipeStepSort'
import type {
  RecipeInfoRow,
  RecipeTrendResponse,
  SummaryBucketKey
} from '~/composables/useRecipeStatisticsApi'

import { healthBadgeStyle, healthStripeColor } from './healthTokens'
import { buildParameterRamp } from '~/utils/parameterRamp'
import { PARA_KEYS } from '~/utils/paraTrendSeries'
import { buildStepOutliers, filterStepOutliers, flaggedStepCount, type StepFilter } from '~/utils/lotOutlierSteps'
import type { DrillDevice } from '~/utils/deviceDrill'
import type { DeviceOutlierResult } from '~/utils/outlierDetect'

const props = defineProps<{
  row: HealthAugmentedRow | null
  bucket: SummaryBucketKey
  recipeRows: RecipeInfoRow[]
  /**
   * 이 lot 의 recipe-params — **이미 버킷 범위로 좁혀진** 것입니다.
   *
   * 모달이 직접 좁히지 않는 이유는 페이지가 이미 한 번 좁혀 두었기 때문입니다
   * (comparison.vue 의 bucketRecipes). 여기서 또 좁히면 health·outlier 와 이
   * 파일이 서로 다른 모집단을 말할 수 있는 두 번째 경로가 생깁니다.
   */
  recipeParams: RecipeInput[]
  trend: RecipeTrendResponse | null
  /**
   * 이 lot 의 과다 측정 결과 — 페이지가 toOutlierDrill 로 만든 것입니다.
   * 모달이 직접 판정하지 않는 이유는 recipeParams 를 좁히지 않는 이유와
   * 같습니다: 화면 하나가 두 경로로 같은 사실을 계산하면 언젠가 갈립니다.
   */
  drill: DrillDevice | null
  /** 이 lot 의 중앙값·문턱·초과 총계. 초과 개수와 그 기준선은 같은 화면에 있어야 합니다. */
  outlier: DeviceOutlierResult | null
}>()

const open = defineModel<boolean>('open', { required: true })

const text = {
  recipeEmpty: '이 lot 의 recipe 가 현재 bucket 에 없습니다.',
  noRules: '룰 없음',
  violations: '위반',
  grayRecipes: '판정 제외',
  recipeRatio: '운용 / 전체 recipe',
  paraDist: 'para 분포',
  csvDownload: 'CSV 다운로드',
  copyHint: '파라미터 표를 클립보드에 복사 (엑셀에 붙여넣기)',
  // M 계열은 원천에 순서 field 가 없어 oper_seq/samp_seq 를 공정 접두사 순위로
  // 합성합니다 — 화면 표기 의무 (docs/datatables/ebeam_tas_lot_hist.txt ★).
  seqCaveat: 'M 계열 fab 의 oper_seq · samp_seq 는 합성값으로, 실제 운영 공정 순서를 반영하지 않습니다.',
  outlierCount: '과다 측정',
  baseline: '중앙값 · 문턱',
  baselineHint: '이 디바이스가 이 버킷에서 재는 모든 파라미터 point 수의 중앙값과, '
    + '그 2배인 초과 문턱입니다. CDU 계열·FULL/HALF/MTX job 과 선두 Dummy/Align 파라미터는 '
    + '기준선에서도 초과 판정에서도 빠집니다.',
  filterLabel: 'recipe 필터',
  emptyFlagged: '이 lot 에는 초과로 잡힌 recipe 가 없습니다.'
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
const paraOrder = PARA_KEYS
const { resolvedThemeName } = useEchartsTheme()
const paraPalette = computed(() => buildParameterRamp(resolvedThemeName.value))

const lotRecipes = computed<RecipeInfoRow[]>(() => {
  const lotCd = props.row?.lot_cd
  if (!lotCd) return []
  return props.recipeRows.filter(r => r.lot_cd === lotCd)
})

const sortOptions = [
  { label: '공정순', value: 'oper' },
  { label: 'recipe 이름', value: 'recipe' }
] as const satisfies readonly { label: string, value: RecipeSortKey }[]

// 기본은 **공정순(oper_seq)** 입니다. 예전 기본은 para_all 내림차순이었는데,
// 그것은 "어느 recipe 가 제일 무거운가" 라는 질문의 순서입니다. 이 목록을 여는
// 질문은 "이 device 가 공정을 따라가며 무엇을 재는가" 이므로, 순서가 곧 공정
// 흐름이어야 합니다 — 그래야 위에서 아래로 읽는 것이 wafer 가 지나가는 순서와
// 같아집니다. para 가 큰 recipe 는 막대 길이로 이미 눈에 띕니다.
//
// ref 는 모달이 살아 있는 동안 유지됩니다(모달은 v-model:open 으로 감췄다
// 보였다 할 뿐 unmount 되지 않습니다). lot 을 바꿔 가며 볼 때 정렬이 매번
// 기본값으로 튕기지 않는 편이 낫습니다.
const recipeSort = ref<RecipeSortKey>('oper')

// 비교 함수는 utils/recipeStepSort.ts 에 있습니다 — 컴포넌트 안에 두면 단위
// 테스트가 볼 수 없기 때문입니다. 두 정렬의 차이는 집의 mock 에서도 화면으로
// 확인됩니다(그 파일의 주석 참고).
const sortedRecipes = computed(() => sortSteps(lotRecipes.value, recipeSort.value))

// 정렬 -> 조인 순서입니다. buildStepOutliers 는 순서를 보존하므로 정렬 칩이
// 그대로 카드 순서가 됩니다.
const stepCards = computed(() => buildStepOutliers(sortedRecipes.value, props.drill))

// 필터는 **페이지가 갖습니다**. 진입점이 초기 상태를 정하기 때문입니다 — 행을
// 누르면 전체, outlier 배지를 누르면 초과만 (D1). 모달이 자기 안에 두면 배지로
// 들어온 사람에게 한 번 더 클릭을 시키게 됩니다.
const filter = defineModel<StepFilter>('filter', { default: 'all' })

const visibleCards = computed(() => filterStepOutliers(stepCards.value, filter.value))
const flaggedCardCount = computed(() => flaggedStepCount(stepCards.value))

const filterOptions = [
  { label: '전체', value: 'all' },
  { label: '초과만', value: 'flagged' }
] as const satisfies readonly { label: string, value: StepFilter }[]

// 카드마다 막대를 제 합계로 정규화하면 파라미터 3개짜리 recipe 와 40개짜리
// recipe 의 막대가 똑같이 꽉 차 보입니다. lot 안에서 서로 비교되도록 최대값을
// 공유합니다.
const maxRecipeParaTotal = computed(() => Math.max(0, ...lotRecipes.value.map(r => r.para_all)))

// 이 모달에서 실제로 그려지는 구간만. 위 lot 막대와 아래 recipe 카드가 모두
// 이 범례를 씁니다.
//
// lot 행의 값 하나로 판정할 수 있습니다 — lot 값은 recipe 값의 합이고 개수는
// 음수가 될 수 없으므로, `lot > 0` 은 곧 "적어도 한 recipe 가 이 구간을 가진다"
// 입니다. recipe 를 따로 훑을 필요가 없습니다.
//
// 그래서 이 필터가 걸리는 경우는 생각보다 드뭅니다. recipe 100~200 개를 합치면
// 어느 구간이든 하나쯤은 채워지기 때문입니다. 자주 비는 것은 **recipe 카드
// 하나하나**이고, 그쪽은 StackedBar 가 0 인 조각을 아예 그리지 않는 것으로
// 이미 처리됩니다. 여기서 지우는 것은 "이 lot 전체에 16 point 초과 파라미터가
// 한 개도 없다" 는 경우뿐입니다.
const presentParaKeys = computed(() =>
  paraOrder.filter(key => (props.row?.[key] ?? 0) > 0)
)

// 파일은 화면이 보여 주는 것을 그대로 담습니다 — 정렬도, 필터도. 버튼 옆의
// `N행` 이 무엇을 받는지 미리 말해 주고, 파일 이름의 _flagged 가 받은 뒤에도
// 말해 줍니다.
const paramRows = computed(() =>
  buildLotParamRows(visibleCards.value.map(card => card.step), props.recipeParams)
)
const paramRowCount = computed(() => paramRows.value.length)

const headers = [...LOT_PARAM_HEADERS]

const downloadParamTable = () => {
  if (!props.row) return
  downloadCsv(
    lotParamFileName(props.row.lot_cd, props.bucket, filter.value === 'flagged'),
    headers,
    paramRows.value
  )
}

const toast = useToast()

const copyParamTable = async () => {
  const ok = await copyTableToClipboard(headers, paramRows.value)
  toast.add(
    ok
      ? { title: '클립보드에 복사됨', icon: 'i-lucide-check', color: 'success' }
      : { title: '복사에 실패했습니다', icon: 'i-lucide-x', color: 'error' }
  )
}

// 펼침 상태의 키는 카드의 키와 같아야 합니다 — recipe_id 로 잡으면 같은
// recipe 를 쓰는 두 스텝이 함께 펼쳐집니다(그리고 접힙니다).
const expandedSteps = ref<Set<string>>(new Set())

const toggleStep = (key: string) => {
  const next = new Set(expandedSteps.value)
  if (next.has(key)) next.delete(key)
  else next.add(key)
  expandedSteps.value = next
}

// lot 이 바뀌면 모두 접습니다. 모달은 unmount 되지 않으므로 두면 이전 lot 의
// 펼침이 남습니다.
watch(() => props.row?.lot_cd, () => {
  expandedSteps.value = new Set()
})
</script>
