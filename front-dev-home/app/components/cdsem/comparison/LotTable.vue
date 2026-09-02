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
          @click="downloadLotExcel"
        />
        <AppViewToggle
          v-model="view"
          :aria-label="text.viewToggle"
        />
      </div>
    </header>

    <!-- 행 카드. 12열 표에서 옮긴 것: lot · health · stage 는 카드 첫 줄로,
         상한 초과 · 판정 범위 · 운용/전체 recipe · 중앙값은 라벨 달린 메타
         줄로, para 분포는 가운데 블록으로, 중앙값 초과는 클릭 가능한 배지로. -->
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
          :style="{ background: healthStripeColor(row.verdict.health) }"
          aria-hidden="true"
        />

        <div class="flex min-w-0 flex-1 flex-wrap items-start gap-x-5 gap-y-3 px-4 py-3.5">
          <div class="min-w-0 flex-1">
            <div class="flex flex-wrap items-center gap-2">
              <span class="sk-card-id">{{ row.lot_cd }}</span>
              <span
                v-if="row.verdict.health"
                class="sk-badge font-bold"
                :style="healthBadgeStyle(row.verdict.health, isDark)"
              >{{ row.verdict.health }}</span>
              <span
                v-else
                class="sk-badge bg-(--sk-muted-surface) text-(--sk-ink-subtle) ring-1 ring-(--sk-border) ring-inset"
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
              <span
                class="sk-field-label"
                :title="violationTitle(row.verdict)"
              >
                {{ text.violations }}
                <span
                  class="sk-field-value"
                  :class="{ 'font-semibold text-(--sk-ink)': row.verdict.kind === 'judged' }"
                >{{ formatViolations(row.verdict, ' recipe') }}</span>
              </span>
              <span
                class="sk-field-label"
                :title="coverageTitle(row)"
              >
                {{ text.coverage }}
                <span class="sk-field-value">{{ formatCoverage(row.verdict) }}</span>
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
              <!-- 값이 0 인 구간도 **자리를 지킵니다.** 행마다 칸 수가 달라지면
                   lot 끼리 눈으로 비교할 수 없게 되기 때문입니다. para_over_16 은
                   대부분의 lot 에서 0 이지만, 그 0 자체가 "16 point 를 넘는
                   파라미터가 없다" 는 정보입니다. 막대(StackedBar)는 반대로 0 인
                   구간을 그리지 않습니다 — 거기서는 폭이 곧 값이라 2px 짜리 조각이
                   없는 값을 있는 것처럼 보이게 하기 때문입니다.

                   `?? 0` — 2026-08-10 이전 주차 스냅샷에는 이 키가 아예 없어서
                   그대로 두면 숫자 자리가 빈 칸으로 렌더됩니다. -->
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
                {{ row[key] ?? 0 }}
              </span>
            </div>
          </div>

          <div class="w-32 flex-none text-right">
            <div
              class="mb-1 sk-field-label"
              :title="outlierTitle(row)"
            >
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
              class="inline-flex h-8 min-w-13 items-center justify-center gap-1 rounded-lg bg-(--sk-bad-soft) px-2.5 font-mono text-base font-bold tabular-nums text-(--sk-bad) transition-colors hover:bg-(--sk-bad-soft-hover)"
              :aria-label="`${row.lot_cd} 중앙값 초과 파라미터 ${row.outlier_count}건 자세히`"
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

    <!-- 표 보기 — 정렬·엑셀 붙여넣기를 하는 사람용. 카드와 Excel 이 모두 이
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
            class="tabular-nums"
            :class="row.original.verdict.kind === 'judged' ? 'text-(--sk-ink)' : 'text-(--sk-ink-subtle)'"
            :title="violationTitle(row.original.verdict)"
          >{{ formatViolations(row.original.verdict) }}</span>
        </template>

        <template #coverage-cell="{ row }">
          <span
            class="tabular-nums text-(--sk-ink-muted)"
            :title="coverageTitle(row.original)"
          >{{ formatCoverage(row.original.verdict) }}</span>
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
            :title="outlierTitle(row.original)"
            :aria-label="`${row.original.lot_cd} 중앙값 초과 파라미터 ${row.original.outlier_count}건 자세히`"
            @click.stop="emit('open-outliers', row.original.lot_cd)"
          >
            <span :class="[countPill, 'bg-(--sk-bad-soft) text-(--sk-bad)']">
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
            :title="outlierTitle(row.original)"
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
import { computed, ref, watch } from 'vue'
import { useColorMode } from '#imports'
import type { TableColumn } from '@nuxt/ui'
import type { SortingState } from '@tanstack/vue-table'
import { paraTotal, verdictSortValue, type HealthAugmentedRow, type LotVerdict } from '~/utils/lotHealth'
import { LOT_SORT, type LotSortKey } from '~/utils/lotSort'
import type { HealthLevel } from '~/utils/ruleEngine'
import type { Profiled } from '~/utils/deviceProfile'
import {
  healthBadgeStyle, healthStripeColor, healthSwatches
} from './healthTokens'
import { copyTableToClipboard } from '~/utils/tableExport'
import { todayStamp } from '~/utils/dateTime'
import { buildParameterRamp } from '~/utils/parameterRamp'
import { PARA_KEYS } from '~/utils/paraTrendSeries'

const downloadTable = useTableDownload()

const props = defineProps<{
  rows: Profiled<HealthAugmentedRow>[]
  /**
   * 페이지 상단 "정렬" 칩. 이 표의 정렬 상태를 **몹니다** — 칩을 누르면 위쪽
   * 막대 차트와 이 표가 같은 축으로 함께 늘어섭니다. 열 머리글을 누르면 칩에
   * 없는 축(health·outlier·판정 범위 …)으로 더 파고들 수 있고, 그다음 칩을
   * 다시 누르면 칩 쪽이 이깁니다.
   */
  sort: LotSortKey
}>()

const emit = defineEmits<{
  (e: 'select-lot', row: HealthAugmentedRow): void
  (e: 'open-outliers', lot_cd: string): void
}>()

const text = {
  title: 'Lot 요약',
  subtitleCards: '카드를 클릭하면 recipe 상세와 추이를, 중앙값 초과 배지를 클릭하면 같은 팝업이 초과 recipe 만 추려 열립니다.',
  subtitleTable: '행을 클릭하면 recipe 상세와 추이를, 중앙값 초과 배지를 클릭하면 같은 팝업이 초과 recipe 만 추려 열립니다.',
  noProfile: '이 lot 의 recipe 파라미터를 불러오지 못했습니다',
  empty: '표시할 lot 이 없습니다. 다른 bucket 을 선택해 보세요.',
  copy: '클립보드 복사',
  copyAria: '표를 클립보드에 복사',
  download: 'Excel',
  viewToggle: 'Lot 요약 보기 방식',
  noRules: '룰 없음',
  violations: '상한 초과',
  coverage: '판정 범위',
  recipeRatio: '운용 / 전체 recipe',
  pointMedian: '측정점 중앙값',
  paraDist: 'para 분포',
  outlier: '중앙값 초과 파라미터',
  sortNote: '위 정렬 칩을 따릅니다 · 표 보기에서 열 머리글로 다른 축 정렬'
} as const

const healthLevels: HealthLevel[] = ['red', 'yellow', 'green']

const view = useRowCardView('cdsem-comparison:lotView', 'skewnono:comparison.lotView')

const subtitle = computed(() => view.value === 'cards' ? text.subtitleCards : text.subtitleTable)

const colorMode = useColorMode()
const isDark = computed(() => colorMode.value === 'dark')
const paraOrder = PARA_KEYS
const { resolvedThemeName } = useEchartsTheme()
const paraPalette = computed(() => buildParameterRamp(resolvedThemeName.value))

// Shared box for the outlier count so the alert and zero states can't drift apart.
const countPill = 'inline-flex h-6 min-w-8 items-center justify-center rounded px-1.5 font-mono text-[13px] font-semibold tabular-nums'

// 카드와 표가 같은 문자열을 씁니다. 두 표면이 각자 조건문을 들고 있으면
// "판정 없음" 을 한쪽은 —, 다른 쪽은 0 으로 쓰는 식으로 갈라집니다.
// `unit` 은 카드만 씁니다. 카드는 라벨과 값이 한 줄로 이어져 읽히므로 "3 / 40
// recipe" 가 문장이 되고, 표는 열 머리글이 이미 단위를 말해 자리만 먹습니다.
// 그래도 '—' 판정과 두 숫자의 순서는 여전히 이 한 곳이 정합니다.
const formatViolations = (v: LotVerdict, unit = '') =>
  v.kind === 'judged' ? `${v.violation_recipes} / ${v.judged_recipes}${unit}` : '—'

// 라벨은 "무엇을 넘겼는가", 툴팁은 "몇 건 중 몇 건인가" 를 말합니다. 분자·분모가
// 각각 무엇을 세는지 화면 밖에서 물어보게 두지 않으려는 것이고, 특히 분모가
// 전체 recipe 가 아니라 **판정한** recipe 라는 점은 숫자만 봐서는 알 수 없습니다.
const violationTitle = (v: LotVerdict) =>
  v.kind === 'judged'
    ? `상한을 넘긴 recipe ${v.violation_recipes}건 / 룰로 판정한 recipe ${v.judged_recipes}건`
    + ' — recipe 안에 상한을 넘긴 파라미터가 하나라도 있으면 그 recipe 를 1건으로 셉니다.'
    : '이 lot 은 룰로 판정하지 못했습니다 — 옆의 판정 범위가 이유를 말합니다.'

// outlier 는 상한과 **다른 축**입니다. 이름만으로는 "무엇 대비 초과인지" 를 알
// 수 없어 상한 초과와 같은 종류로 읽히던 자리라, 기준선을 숫자로 펼쳐 둡니다.
const outlierTitle = (r: Profiled<HealthAugmentedRow>) =>
  r.outlier_count === null || r.point_median === null
    ? text.noProfile
    : `측정점 중앙값 ${r.point_median} × 2 = ${r.point_median * 2} 를 넘는 파라미터 ${r.outlier_count}개`
      + ' — 룰의 상한이 아니라 이 lot 자신의 분포를 기준으로 잡은 별개의 축입니다.'

const formatCoverage = (v: LotVerdict) =>
  v.kind === 'judged'
    ? `${v.judged_recipes} / ${v.total_recipes} (${percent(v.coverage)})`
    : `0 / ${v.total_recipes}`

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
  // 특수 측정 job(_*CDU/_FULL/_HALF/_MTX)은 분모에도 없으므로 항상 꼬리로만
  // 언급합니다. outlier 기준선에서도 빠진다는 것을 여기서 함께 말해 둡니다 —
  // 같은 행의 "측정점 중앙값" 이 무엇을 세지 않았는지 읽는 사람이 알아야 합니다.
  const exempt = v.exempt_recipes > 0
    ? ` · 특수 job ${v.exempt_recipes}건 (CDU 계열/FULL/HALF/MTX) 은 판정·outlier 모두에서 제외`
    : ''
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
// Excel 이 각자 다른 규칙으로 섞어 두 결과가 어긋납니다.
const profileSortValue = (key: 'point_median' | 'outlier_count') =>
  (r: Profiled<HealthAugmentedRow>) => r[key] ?? -1

const columns: TableColumn<Profiled<HealthAugmentedRow>>[] = [
  { accessorKey: 'lot_cd', header: 'lot', size: 120 },
  { id: 'stage', accessorFn: r => r.dev_stage, header: 'stage', size: 72 },
  { id: 'health', accessorFn: healthSortValue, header: 'health', size: 90 },
  { id: 'violations', accessorFn: r => r.verdict.violation_recipes, header: '상한 초과', size: 110 },
  { id: 'coverage', accessorFn: r => r.verdict.coverage, header: '판정 범위', size: 120 },
  { id: 'params', header: 'para 분포', size: 216, enableSorting: false },
  { id: 'para_total', accessorFn: paraTotal, header: 'para 합계', size: 90 },
  { accessorKey: 'avail_recipe', header: '운용 recipe', size: 100 },
  { accessorKey: 'total_recipe', header: '전체 recipe', size: 100 },
  // 측정 프로파일 — 과다 측정 디바이스 탐지. 요약 버킷이 아니라 recipe_params 에서
  // 옵니다(버킷을 바꿔도 기준선이 움직이면 안 되므로).
  { id: 'point_median', accessorFn: profileSortValue('point_median'), header: '중앙값', size: 90 },
  { id: 'outlier_count', accessorFn: profileSortValue('outlier_count'), header: '중앙값 초과 파라미터', size: 160 },
  { accessorKey: 'ctn_desc', header: 'description' }
]

const sortableColumnIds = [
  'lot_cd', 'stage', 'health', 'violations', 'coverage',
  'para_total', 'avail_recipe', 'total_recipe',
  'point_median', 'outlier_count', 'ctn_desc'
] as const

// 칩이 가리키는 열이 **이 표에 실제로 있는지**는 여기서만 알 수 있습니다. 아래
// `columnId` 한 줄이 그것을 컴파일 시점에 확인합니다 — 열 id 를 바꾸면 타입
// 오류가 나고, 그 확인이 없으면 TanStack 이 모르는 id 를 조용히 무시해 칩만
// 눌리고 표는 그대로인, 이 기능이 없애려던 바로 그 상태로 돌아갑니다.
const chipSorting = (key: LotSortKey): SortingState => {
  const columnId: typeof sortableColumnIds[number] = LOT_SORT[key].column
  return [{ id: columnId, desc: LOT_SORT[key].desc }]
}

// 정렬 상태는 칩이 정합니다. 첫 그림부터 맞추는 것이 요점입니다 — 예전
// 기본값(health 오름차순)으로 시작하면 칩은 "이름순" 인데 표는 health 순인
// 상태로 화면이 열려, 바로 위 막대 차트와 순서가 어긋난 채로 보입니다.
//
// 카드·표·Excel 세 표면이 모두 이 ref 하나를 읽으므로(orderedRows / UTable), 여기
// 한 곳만 몰면 셋이 함께 따라옵니다.
const sorting = ref<SortingState>(chipSorting(props.sort))

watch(() => props.sort, (key) => {
  sorting.value = chipSorting(key)
})

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

// 카드 목록과 Excel 이 **같은** 배열입니다. 표 보기에서 정렬을 바꾸고 카드로
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
    ...paraOrder, 'para_total',
    'avail_recipe', 'total_recipe', 'point_median', 'outlier_count', 'ctn_desc'
  ]
  // 프로파일이 없는 lot 은 0 이 아니라 빈 칸으로 나갑니다 — 표의 "—" 와 같은 뜻이고,
  // 스프레드시트에서 "측정 0건" 으로 집계되면 안 됩니다.
  const rows = orderedRows.value.map(r => [
    r.lot_cd, r.fac_id, r.dev_stage, r.verdict.health ?? '', r.verdict.violation_recipes,
    r.verdict.judged_recipes, r.verdict.total_recipes, r.verdict.coverage.toFixed(3),
    ...paraOrder.map(key => r[key] ?? 0), paraTotal(r),
    r.avail_recipe, r.total_recipe,
    r.point_median ?? '', r.outlier_count ?? '',
    r.ctn_desc
  ])
  return { headers, rows }
}

const toast = useToast()

const exportFileName = computed(() => {
  const today = todayStamp()
  return `cdsem-comparison-lots-${today}.xlsx`
})

const downloadLotExcel = async () => {
  const { headers, rows } = lotTable()
  await downloadTable(exportFileName.value, headers, rows)
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
