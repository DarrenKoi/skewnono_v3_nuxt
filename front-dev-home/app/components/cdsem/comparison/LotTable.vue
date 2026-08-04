<template>
  <section class="space-y-3">
    <header class="flex flex-wrap items-end justify-between gap-3 px-1">
      <div class="flex items-start gap-3">
        <span
          class="mt-0.5 h-10 w-1 flex-none rounded-[2px] bg-(--sk-accent)"
          aria-hidden="true"
        />
        <div>
          <h2 class="text-lg font-bold leading-tight tracking-tight text-(--sk-ink)">
            {{ text.title }}
          </h2>
          <p class="mt-1 sk-caption">
            {{ subtitle }}
          </p>
        </div>
      </div>

      <div class="flex flex-wrap items-center gap-2">
        <div class="flex items-center gap-1.5">
          <span
            v-for="level in healthLevels"
            :key="level"
            class="inline-flex h-8 items-center gap-2 rounded-full bg-(--sk-muted-surface) px-3 text-[13px] font-semibold tabular-nums text-(--sk-ink-muted) ring-1 ring-(--sk-border) ring-inset"
          >
            <span
              class="h-[9px] w-[9px] rounded-full"
              :style="{ background: healthSwatches[level].dot }"
            />
            {{ counts[level] }} {{ level }}
          </span>
          <span
            v-if="noRuleCount > 0"
            class="inline-flex h-8 items-center gap-2 rounded-full bg-(--sk-muted-surface) px-3 text-[13px] font-semibold tabular-nums text-(--sk-ink-subtle) ring-1 ring-(--sk-border) ring-inset"
            title="계측 룰이 없는 fab 의 lot 입니다 — 판정하지 않았습니다"
          >
            <span class="h-[9px] w-[9px] rounded-full bg-(--sk-border)" />
            {{ noRuleCount }} 룰 없음
          </span>
        </div>
        <UTooltip :text="text.copy">
          <UButton
            color="neutral"
            variant="outline"
            icon="i-lucide-clipboard"
            class="h-[34px] px-3 text-sm font-semibold"
            :aria-label="text.copyAria"
            :disabled="rows.length === 0"
            @click="copyLotTable"
          />
        </UTooltip>
        <UButton
          color="neutral"
          variant="outline"
          icon="i-lucide-download"
          class="h-[34px] px-3.5 text-sm font-semibold"
          :label="text.download"
          :disabled="rows.length === 0"
          @click="downloadLotCsv"
        />
        <AppViewToggle
          v-model="view"
          :aria-label="text.viewToggle"
        />
      </div>
    </header>

    <!-- 행 카드. 12열 표에서 옮긴 것: lot · health · stage 는 카드 첫 줄로,
         violations · 판정 범위 · 운용/전체 recipe · 중앙값은 라벨 달린 메타
         줄로, para 분포는 가운데 블록으로, outlier 는 클릭 가능한 배지로. -->
    <div
      v-if="view === 'cards'"
      class="dashboard-surface overflow-hidden rounded-2xl"
    >
      <p
        v-if="orderedRows.length === 0"
        class="px-4 py-12 text-center sk-body text-(--sk-ink-muted)"
      >
        {{ text.empty }}
      </p>
      <div
        v-for="row in orderedRows"
        :key="row.lot_cd"
        role="button"
        tabindex="0"
        class="flex cursor-pointer items-stretch border-b border-(--sk-border-soft) transition-colors last:border-b-0 hover:bg-(--sk-muted-surface) focus-visible:bg-(--sk-muted-surface) focus-visible:outline-none"
        :aria-label="`${row.lot_cd} recipe 상세 열기`"
        @click="emit('select-lot', row)"
        @keydown.enter.prevent="emit('select-lot', row)"
        @keydown.space.prevent="emit('select-lot', row)"
      >
        <span
          class="w-[5px] flex-none"
          :style="{ background: stripeColor(row) }"
          aria-hidden="true"
        />

        <div class="flex min-w-0 flex-1 flex-wrap items-start gap-x-5 gap-y-3 px-4 py-3.5">
          <div class="min-w-0 flex-1">
            <div class="flex flex-wrap items-center gap-2">
              <span class="sk-card-id">{{ row.lot_cd }}</span>
              <span
                v-if="row.verdict.health"
                class="inline-flex h-6 items-center rounded-md px-2.5 font-mono text-[13px] font-bold"
                :style="healthBadgeStyle(row.verdict.health)"
              >{{ row.verdict.health }}</span>
              <span
                v-else
                class="inline-flex h-6 items-center rounded-md bg-(--sk-muted-surface) px-2.5 font-mono text-[13px] font-semibold text-(--sk-ink-subtle) ring-1 ring-(--sk-border) ring-inset"
                :title="coverageTitle(row)"
              >{{ text.noRules }}</span>
              <CdsemComparisonStageChip
                :stage="row.dev_stage"
                :inferred="row.stage_inferred"
              />
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
                >{{ row.verdict.violation_recipes }} / {{ row.verdict.judged_recipes }}</span>
                <span
                  v-else
                  class="sk-field-value"
                >—</span>
              </span>
              <span
                class="sk-field-label"
                :title="coverageTitle(row)"
              >
                {{ text.coverage }}
                <span class="sk-field-value">
                  <template v-if="row.verdict.kind === 'judged'">
                    {{ row.verdict.judged_recipes }} / {{ row.verdict.total_recipes }} ({{ percent(row.verdict.coverage) }})
                  </template>
                  <template v-else>0 / {{ row.verdict.total_recipes }}</template>
                </span>
              </span>
              <span class="sk-field-label">
                {{ text.recipeRatio }}
                <span class="sk-field-value">{{ row.avail_recipe }} / {{ row.total_recipe }}</span>
              </span>
              <span
                class="sk-field-label"
                :title="row.point_median === null ? text.noProfile : undefined"
              >
                {{ text.pointMedian }}
                <span class="sk-field-value">{{ row.point_median ?? '—' }}</span>
              </span>
            </div>
          </div>

          <div class="w-60 flex-none">
            <div class="mb-1.5 flex items-baseline justify-between gap-2">
              <span class="sk-field-label">{{ text.paraDist }}</span>
              <span class="sk-field-value text-[15px] font-semibold text-(--sk-ink)">{{ paraTotal(row) }}</span>
            </div>
            <CdsemComparisonStackedBar
              :row="row"
              :label="row.lot_cd"
              :height="18"
              :normalize="false"
              :max-total="maxParaTotal"
            />
            <div class="mt-1.5 flex flex-wrap gap-x-2.5 gap-y-1">
              <span
                v-for="key in paraOrder"
                :key="key"
                class="inline-flex items-center gap-1 font-mono text-[13px] tabular-nums text-(--sk-ink-muted)"
                :title="key"
              >
                <span
                  class="h-2 w-2 rounded-[2px]"
                  :style="{ background: paraPalette[key] }"
                />
                {{ row[key] }}
              </span>
            </div>
          </div>

          <div class="w-26 flex-none text-right">
            <div class="mb-1 sk-field-label">
              {{ text.outlier }}
            </div>
            <span
              v-if="row.outlier_count === null"
              class="inline-flex h-8 min-w-13 items-center justify-center rounded-lg bg-(--sk-muted-surface) px-2.5 font-mono text-base font-bold text-(--sk-ink-subtle)"
              :title="text.noProfile"
            >—</span>
            <button
              v-else-if="row.outlier_count > 0"
              type="button"
              class="inline-flex h-8 min-w-13 items-center justify-center gap-1 rounded-lg bg-rose-100 px-2.5 font-mono text-base font-bold tabular-nums text-rose-700 transition-colors hover:bg-rose-200 dark:bg-rose-950/50 dark:text-rose-300 dark:hover:bg-rose-950/80"
              :aria-label="`${row.lot_cd} outlier ${row.outlier_count}건 자세히`"
              @click.stop="emit('open-outliers', row.lot_cd)"
            >
              {{ row.outlier_count }}
              <UIcon
                name="i-lucide-chevron-right"
                class="h-4 w-4 opacity-70"
              />
            </button>
            <span
              v-else
              class="inline-flex h-8 min-w-13 items-center justify-center rounded-lg bg-(--sk-muted-surface) px-2.5 font-mono text-base font-bold tabular-nums text-(--sk-ink-subtle)"
            >0</span>
          </div>
        </div>
      </div>

      <div
        v-if="orderedRows.length > 0"
        class="flex flex-wrap items-center justify-between gap-2 px-4 py-3"
      >
        <span class="text-sm tabular-nums text-(--sk-ink-muted)">{{ orderedRows.length }} lots</span>
        <span class="sk-field-label">{{ text.sortNote }}</span>
      </div>
    </div>

    <!-- 표 보기 — 정렬·엑셀 붙여넣기를 하는 사람용. 카드와 CSV 가 모두 이
         `sorting` 을 따르므로 세 표면의 순서가 갈라지지 않습니다. -->
    <div
      v-else
      class="dashboard-surface overflow-hidden rounded-2xl"
    >
      <UTable
        v-model:sorting="sorting"
        class="max-h-136"
        :columns="columns"
        :data="rows"
        :empty="text.empty"
        :sorting-options="{ enableMultiSort: false, enableSortingRemoval: false }"
        sticky="header"
        :ui="tableUi"
        @select="(_, row) => emit('select-lot', row.original)"
      >
        <template
          v-for="id in sortableColumnIds"
          :key="id"
          #[`${id}-header`]="{ column }"
        >
          <UButton
            size="xs"
            color="neutral"
            variant="ghost"
            class="-mx-2 -my-1 h-7 px-2 text-[13px] font-medium text-(--sk-ink-muted) hover:text-(--sk-ink)"
            :trailing-icon="getSortIcon(column.getIsSorted())"
            @click.stop="column.toggleSorting(column.getIsSorted() === 'asc')"
          >
            {{ column.columnDef.header }}
          </UButton>
        </template>

        <template #lot_cd-cell="{ row }">
          <span class="font-mono text-[15px] font-semibold text-(--sk-ink)">{{ row.original.lot_cd }}</span>
        </template>

        <template #stage-cell="{ row }">
          <CdsemComparisonStageChip
            :stage="row.original.dev_stage"
            :inferred="row.original.stage_inferred"
          />
        </template>

        <template #health-cell="{ row }">
          <span
            v-if="row.original.verdict.health"
            class="inline-flex items-center gap-1.5"
          >
            <span
              class="h-2.5 w-2.5 rounded-full"
              :style="{ background: healthSwatches[row.original.verdict.health].dot }"
            />
            <span class="font-mono text-[13px] font-semibold text-(--sk-ink-muted)">{{ row.original.verdict.health }}</span>
          </span>
          <span
            v-else
            class="inline-flex items-center gap-1.5"
            :title="coverageTitle(row.original)"
          >
            <span class="h-2.5 w-2.5 rounded-full bg-(--sk-border)" />
            <span class="font-mono text-[13px] font-medium text-(--sk-ink-subtle)">{{ text.noRules }}</span>
          </span>
        </template>

        <template #violations-cell="{ row }">
          <span
            v-if="row.original.verdict.kind === 'judged'"
            class="tabular-nums"
          >
            <span class="font-semibold text-(--sk-ink)">{{ row.original.verdict.violation_recipes }}</span>
            <span class="text-(--sk-ink-subtle)"> / {{ row.original.verdict.judged_recipes }}</span>
          </span>
          <span
            v-else
            class="text-(--sk-ink-subtle)"
          >—</span>
        </template>

        <template #coverage-cell="{ row }">
          <span
            class="tabular-nums"
            :title="coverageTitle(row.original)"
          >
            <template v-if="row.original.verdict.kind === 'judged'">
              <span class="font-semibold text-(--sk-ink)">{{ row.original.verdict.judged_recipes }}</span>
              <span class="text-(--sk-ink-subtle)"> / {{ row.original.verdict.total_recipes }}</span>
              <span class="ml-1 text-[13px] text-(--sk-ink-subtle)">({{ percent(row.original.verdict.coverage) }})</span>
            </template>
            <span
              v-else
              class="text-(--sk-ink-subtle)"
            >0 / {{ row.original.verdict.total_recipes }}</span>
          </span>
        </template>

        <template #params-cell="{ row }">
          <div class="w-[200px]">
            <CdsemComparisonStackedBar
              :row="row.original"
              :label="row.original.lot_cd"
              :height="16"
              :normalize="false"
              :max-total="maxParaTotal"
            />
          </div>
        </template>

        <template #point_median-cell="{ row }">
          <span
            v-if="row.original.point_median === null"
            class="text-(--sk-ink-subtle)"
            :title="text.noProfile"
          >—</span>
          <span
            v-else
            class="font-mono text-sm text-(--sk-ink-muted)"
          >{{ row.original.point_median }}</span>
        </template>

        <template #outlier_count-cell="{ row }">
          <span
            v-if="row.original.outlier_count === null"
            class="text-(--sk-ink-subtle)"
            :title="text.noProfile"
          >—</span>
          <UButton
            v-else-if="row.original.outlier_count > 0"
            size="xs"
            color="neutral"
            variant="ghost"
            class="-my-1 h-7 gap-1 px-1.5"
            :aria-label="`${row.original.lot_cd} outlier ${row.original.outlier_count}건 자세히`"
            @click.stop="emit('open-outliers', row.original.lot_cd)"
          >
            <span :class="[countPill, 'bg-rose-100 text-rose-700 dark:bg-rose-950/50 dark:text-rose-300']">
              {{ row.original.outlier_count }}
            </span>
            <UIcon
              name="i-lucide-chevron-right"
              class="h-3.5 w-3.5 text-(--sk-ink-subtle)"
            />
          </UButton>
          <span
            v-else
            :class="[countPill, 'bg-(--sk-surface) text-(--sk-ink-subtle)']"
          >0</span>
        </template>

        <template #ctn_desc-cell="{ row }">
          <span
            class="block max-w-md truncate text-(--sk-ink-muted)"
            :title="row.original.ctn_desc"
          >
            {{ row.original.ctn_desc || '—' }}
          </span>
        </template>
      </UTable>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useColorMode } from '#imports'
import type { TableColumn } from '@nuxt/ui'
import type { SortingState } from '@tanstack/vue-table'
import { paraTotal, verdictSortValue, type HealthAugmentedRow } from '~/utils/lotHealth'
import type { HealthLevel } from '~/utils/ruleEngine'
import type { Profiled } from '~/utils/deviceProfile'
import { healthSwatches, paraColors, paraColorsDark, paraOrder } from './healthTokens'
import { copyTableToClipboard, downloadCsv } from '~/utils/csvDownload'

const props = defineProps<{
  rows: Profiled<HealthAugmentedRow>[]
}>()

const emit = defineEmits<{
  (e: 'select-lot', row: HealthAugmentedRow): void
  (e: 'open-outliers', lot_cd: string): void
}>()

const text = {
  title: 'Lot 요약',
  subtitleCards: '카드를 클릭하면 recipe 상세와 추이를, outlier 를 클릭하면 과다 측정 파라미터를 확인합니다.',
  subtitleTable: '행을 클릭하면 recipe 상세와 추이를, outlier 를 클릭하면 과다 측정 파라미터를 확인합니다.',
  noProfile: '이 lot 의 recipe 파라미터를 불러오지 못했습니다',
  empty: '표시할 lot 이 없습니다. 다른 bucket 을 선택해 보세요.',
  copy: '클립보드 복사',
  copyAria: '표를 클립보드에 복사',
  download: 'CSV',
  viewToggle: 'Lot 요약 보기 방식',
  noRules: '룰 없음',
  violations: '위반',
  coverage: '판정 범위',
  recipeRatio: '운용 / 전체 recipe',
  pointMedian: '측정점 중앙값',
  paraDist: 'para 분포',
  outlier: 'outlier',
  sortNote: 'health 순 정렬 · 판정 없음은 항상 마지막'
} as const

const healthLevels: HealthLevel[] = ['red', 'yellow', 'green']

const view = useRowCardView('cdsem-comparison:lotView', 'skewnono:comparison.lotView')

const subtitle = computed(() => view.value === 'cards' ? text.subtitleCards : text.subtitleTable)

const colorMode = useColorMode()
const isDark = computed(() => colorMode.value === 'dark')
const paraPalette = computed(() => isDark.value ? paraColorsDark : paraColors)

// 카드 배지는 tint 배경 + ink 글자입니다. dot 하나만 쓰던 표와 달리 카드에서는
// 판정이 색면(色面)이라, 같은 swatch 의 밝기 짝을 그대로 씁니다.
const healthBadgeStyle = (level: HealthLevel) => {
  const swatch = healthSwatches[level]
  return {
    background: isDark.value ? swatch.tintDark : swatch.tint,
    color: isDark.value ? swatch.inkDark : swatch.ink
  }
}

// 판정 없음(룰 없는 fab)은 띠도 중성 회색입니다 — 초록과 섞이면 "판정했고
// 괜찮다" 로 읽힙니다. 룰이 없어 아무 말도 하지 않은 것과는 다릅니다.
const stripeColor = (row: HealthAugmentedRow) =>
  row.verdict.health ? healthSwatches[row.verdict.health].dot : 'var(--sk-border)'

// Shared box for the outlier count so the alert and zero states can't drift apart.
const countPill = 'inline-flex h-6 min-w-8 items-center justify-center rounded px-1.5 font-mono text-[13px] font-semibold tabular-nums'

const counts = computed<Record<HealthLevel, number>>(() => ({
  red: props.rows.filter(r => r.verdict.health === 'red').length,
  yellow: props.rows.filter(r => r.verdict.health === 'yellow').length,
  green: props.rows.filter(r => r.verdict.health === 'green').length
}))

// 룰이 없어 판정하지 못한 lot. 초록과 섞이면 안 되므로 따로 셉니다.
const noRuleCount = computed(() => props.rows.filter(r => r.verdict.kind === 'no-rules').length)

const maxParaTotal = computed(() => Math.max(0, ...props.rows.map(paraTotal)))

const percent = (value: number) => `${Math.round(value * 100)}%`

/** gray 사유별 건수를 툴팁 한 줄로. 왜 판정 대상에서 빠졌는지 말해 줍니다. */
const coverageTitle = (r: HealthAugmentedRow) => {
  const v = r.verdict
  // 판정 외 job(_WCDU/_FCDU/_FULL)은 분모에도 없으므로 항상 꼬리로만 언급합니다.
  const exempt = v.exempt_recipes > 0 ? ` · 판정 외 job ${v.exempt_recipes}건 (WCDU/FCDU/FULL)` : ''
  if (v.kind === 'no-rules') {
    // 같은 kind 라도 원인이 둘입니다 — gray 가 있으면 룰은 있었던 것입니다.
    // 사무실에서 "판정 범위 전부 0" 이 보일 때 이 툴팁이 원인을 가릅니다.
    if (v.gray_recipes > 0) {
      const detail = Object.entries(v.gray_reasons).map(([reason, n]) => `${reason} ${n}건`).join(', ')
      return `룰은 있으나 전 recipe 가 판정에서 제외되었습니다 — ${detail}${exempt}`
    }
    return `${r.fac_id} 의 계측 룰이 없습니다 — M 계열은 D22 폐기, R3 라면 룰 미발행(publish_rules) 확인${exempt}`
  }
  const reasons = Object.entries(v.gray_reasons)
  if (reasons.length === 0) return `${v.judged_recipes}건 모두 판정했습니다${exempt}`
  const detail = reasons.map(([reason, n]) => `${reason} ${n}건`).join(', ')
  return `판정 ${v.judged_recipes} / 전체 ${v.total_recipes} — 제외: ${detail}${exempt}`
}

// 정렬은 lotHealth 가 정의합니다 — 판정 없음이 항상 맨 뒤로 갑니다.
const healthSortValue = (r: HealthAugmentedRow) => verdictSortValue(r.verdict)

// 프로파일이 없는 lot 은 -1 로 정렬합니다. null 을 그대로 넘기면 표(TanStack)와
// CSV 가 각자 다른 규칙으로 섞어 두 결과가 어긋납니다.
const profileSortValue = (key: 'point_median' | 'outlier_count') =>
  (r: Profiled<HealthAugmentedRow>) => r[key] ?? -1

const sorting = ref<SortingState>([{ id: 'health', desc: false }])

const columns: TableColumn<Profiled<HealthAugmentedRow>>[] = [
  { accessorKey: 'lot_cd', header: 'lot', size: 120 },
  { id: 'stage', accessorFn: r => r.dev_stage, header: 'stage', size: 72 },
  { id: 'health', accessorFn: healthSortValue, header: 'health', size: 90 },
  { id: 'violations', accessorFn: r => r.verdict.violation_recipes, header: 'violations', size: 110 },
  { id: 'coverage', accessorFn: r => r.verdict.coverage, header: '판정 범위', size: 120 },
  { id: 'params', header: 'para 분포', size: 216, enableSorting: false },
  { id: 'para_total', accessorFn: paraTotal, header: 'para 합계', size: 90 },
  { accessorKey: 'avail_recipe', header: '운용 recipe', size: 100 },
  { accessorKey: 'total_recipe', header: '전체 recipe', size: 100 },
  // 측정 프로파일 — 과다 측정 디바이스 탐지. 요약 버킷이 아니라 recipe_params 에서
  // 옵니다(버킷을 바꿔도 기준선이 움직이면 안 되므로).
  { id: 'point_median', accessorFn: profileSortValue('point_median'), header: '중앙값', size: 90 },
  { id: 'outlier_count', accessorFn: profileSortValue('outlier_count'), header: 'outlier', size: 90 },
  { accessorKey: 'ctn_desc', header: 'description' }
]

const sortableColumnIds = [
  'lot_cd', 'stage', 'health', 'violations', 'coverage',
  'para_total', 'avail_recipe', 'total_recipe',
  'point_median', 'outlier_count', 'ctn_desc'
] as const

const getSortIcon = (direction: false | 'asc' | 'desc') => {
  if (direction === 'asc') return 'i-lucide-arrow-up-narrow-wide'
  if (direction === 'desc') return 'i-lucide-arrow-down-wide-narrow'
  return 'i-lucide-arrow-up-down'
}

const tableUi = {
  tr: 'cursor-pointer select-none transition-colors hover:bg-zinc-50 dark:hover:bg-zinc-800/50',
  td: 'py-2 px-3 text-sm whitespace-nowrap overflow-hidden text-ellipsis tabular-nums text-(--sk-ink)',
  // nowrap: 열이 늘어나 폭이 빠듯해지면 브라우저가 한글 헤더를 글자 단위로 세로
  // 배열해 버립니다("측/정/중/앙/값"). 줄바꿈을 막고 가로 스크롤로 넘깁니다.
  th: 'py-2 px-3 text-[13px] font-medium text-(--sk-ink-muted) bg-zinc-50/60 dark:bg-zinc-900/40 whitespace-nowrap'
}

// Mirror the active column sort so exports match what the user sees;
// UTable sorts internally and never mutates props.rows.
const exportSortValue: Record<string, (r: Profiled<HealthAugmentedRow>) => string | number> = {
  lot_cd: r => r.lot_cd,
  stage: r => r.dev_stage,
  health: healthSortValue,
  violations: r => r.verdict.violation_recipes,
  coverage: r => r.verdict.coverage,
  para_total: paraTotal,
  avail_recipe: r => r.avail_recipe,
  total_recipe: r => r.total_recipe,
  point_median: profileSortValue('point_median'),
  outlier_count: profileSortValue('outlier_count'),
  ctn_desc: r => r.ctn_desc
}

// 카드 목록과 CSV 가 **같은** 배열입니다. 표 보기에서 정렬을 바꾸고 카드로
// 돌아오면 카드도 그 순서를 따르고, 내보내기도 마찬가지입니다 — 세 표면이
// 한 `sorting` 을 읽으므로 갈라질 자리가 없습니다.
const orderedRows = computed(() => {
  const active = sorting.value[0]
  const get = active ? exportSortValue[active.id] : undefined
  if (!get) return [...props.rows]
  const direction = active?.desc ? -1 : 1
  return [...props.rows].sort((a, b) => {
    const av = get(a)
    const bv = get(b)
    const diff = typeof av === 'number' && typeof bv === 'number'
      ? av - bv
      : String(av).localeCompare(String(bv), undefined, { numeric: true })
    return diff * direction || a.lot_cd.localeCompare(b.lot_cd)
  })
})

const lotTable = () => {
  // health 가 빈 칸이면 "판정 없음" 입니다 — 초록으로 읽히지 않도록 색 이름 대신
  // 빈 값을 내보내고, 몇 건을 실제로 판정했는지는 옆 두 열이 말합니다.
  const headers = [
    'lot_cd', 'fac_id', 'stage', 'health', 'violation_recipes',
    'judged_recipes', 'total_recipes', 'coverage',
    'para_16', 'para_13', 'para_9', 'para_5', 'para_total',
    'avail_recipe', 'total_recipe', 'point_median', 'outlier_count', 'ctn_desc'
  ]
  // 프로파일이 없는 lot 은 0 이 아니라 빈 칸으로 나갑니다 — 표의 "—" 와 같은 뜻이고,
  // 스프레드시트에서 "측정 0건" 으로 집계되면 안 됩니다.
  const rows = orderedRows.value.map(r => [
    r.lot_cd, r.fac_id, r.dev_stage, r.verdict.health ?? '', r.verdict.violation_recipes,
    r.verdict.judged_recipes, r.verdict.total_recipes, r.verdict.coverage.toFixed(3),
    r.para_16, r.para_13, r.para_9, r.para_5, paraTotal(r),
    r.avail_recipe, r.total_recipe,
    r.point_median ?? '', r.outlier_count ?? '',
    r.ctn_desc
  ])
  return { headers, rows }
}

const toast = useToast()

const exportFileName = computed(() => {
  const today = new Date().toISOString().slice(0, 10)
  return `cdsem-comparison-lots-${today}.csv`
})

const downloadLotCsv = () => {
  const { headers, rows } = lotTable()
  downloadCsv(exportFileName.value, headers, rows)
}

const copyLotTable = async () => {
  const { headers, rows } = lotTable()
  const ok = await copyTableToClipboard(headers, rows)
  toast.add(
    ok
      ? { title: '클립보드에 복사됨', icon: 'i-lucide-check', color: 'success' }
      : { title: '복사에 실패했습니다', icon: 'i-lucide-x', color: 'error' }
  )
}
</script>
