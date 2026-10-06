<template>
  <div class="space-y-6">
    <EbeamMetaBar
      :eyebrow="`AFM · ${toolName}`"
      title="AFM 가동 현황"
      :subtitle="subtitle"
    >
      <template #toggle>
        <nav
          class="flex flex-wrap gap-1"
          aria-label="AFM 장비"
        >
          <SkNavPill
            v-for="tool in fabs.flatMap(group => group.tools)"
            :key="tool.id"
            size="sm"
            :to="`/afm/${tool.id}/usage`"
            :active="tool.id === toolId"
            :label="tool.label"
          />
        </nav>
      </template>
    </EbeamMetaBar>

    <AppLoadingState
      v-if="pending"
      title="측정 목록을 불러오는 중입니다."
    />

    <UAlert
      v-else-if="error"
      color="error"
      variant="soft"
      icon="i-lucide-triangle-alert"
      title="측정 목록을 불러오지 못했습니다."
    />

    <AppEmptyState
      v-else-if="!span || !range"
      icon="i-lucide-activity"
      title="날짜가 있는 측정이 없습니다."
      description="이 장비의 측정 목록에 측정일(formatted_date)이 있는 측정이 없어 가동 현황을 낼 수 없습니다."
    />

    <template v-else>
      <!-- 기간 + 요약: 아래의 모든 숫자와 차트는 이 기간 안에서 셉니다. -->
      <section class="dashboard-surface rounded-(--sk-r-card)">
        <div class="flex flex-wrap items-center justify-between gap-3 border-b border-(--sk-border) px-4 py-3">
          <span class="sk-meta">{{ range[0] }} ~ {{ range[1] }} · {{ days.length }}일</span>
          <div class="flex items-center gap-2">
            <span class="sk-label">기간</span>
            <SkNavPillGroup
              v-model="period"
              :items="PERIODS"
              label="기간"
            />
          </div>
        </div>
        <div class="grid grid-cols-4 gap-2.5 p-4 xl:grid-cols-7">
          <div
            v-for="tile in tiles"
            :key="tile.label"
            class="flex flex-col gap-0.5 rounded-(--sk-r-nav) bg-(--sk-muted-surface) px-3.5 py-3"
          >
            <span class="sk-label">{{ tile.label }}</span>
            <span
              class="font-mono text-xl font-semibold tracking-tight tabular-nums"
              :class="tile.warn ? 'text-(--sk-brand)' : 'text-(--sk-ink)'"
            >{{ tile.value }}</span>
            <span class="truncate sk-meta">{{ tile.meta }}</span>
          </div>
        </div>
      </section>

      <div class="grid items-start gap-6 xl:grid-cols-12">
        <AfmCard
          class="xl:col-span-7"
          icon="i-lucide-chart-column"
          title="일별 측정 건수"
        >
          <template #actions>
            <span class="sk-meta">측정이 많은 recipe {{ TOP_RECIPES }}개 + 기타 · 날짜를 누르면 그날의 측정을 봅니다</span>
          </template>
          <p
            v-if="!rows.length"
            class="flex h-72 items-center justify-center sk-body"
          >
            이 기간에 측정이 없습니다.
          </p>
          <AfmUsageDayBars
            v-else
            :days="days"
            :series="daily"
            stacked
            :selected="day"
            :export-name="`${toolId}-usage-daily`"
            @select="picked = $event"
          />
        </AfmCard>

        <AfmCard
          class="xl:col-span-5"
          icon="i-lucide-grid-3x3"
          title="시간대별 측정"
        >
          <template
            v-if="hours.missing"
            #actions
          >
            <span class="sk-meta">시각 없는 측정 {{ hours.missing.toLocaleString() }}건 제외</span>
          </template>
          <p
            v-if="!hours.cells.length"
            class="flex h-72 items-center justify-center sk-body"
          >
            이 기간에 시각이 있는 측정이 없습니다.
          </p>
          <AfmUsageHourHeat
            v-else
            :days="days"
            :cells="hours.cells"
            :max="hours.max"
            :selected="day"
            :export-name="`${toolId}-usage-hours`"
            @select="picked = $event"
          />
          <p
            v-if="toolName === 'MAP608'"
            class="mt-2 sk-meta"
          >
            MAP608은 목록의 시각이 세션 시작 시각이라, 한 세션의 측정이 같은 시간대에 모입니다.
          </p>
        </AfmCard>

        <AfmCard
          class="xl:col-span-5"
          icon="i-lucide-circle-alert"
          title="미완료·무효 측정"
        >
          <template
            v-if="failures.series && failureMissing"
            #actions
          >
            <span class="sk-meta">{{ failureMissing }}</span>
          </template>
          <p
            v-if="!failures.series"
            class="flex h-72 items-center justify-center px-6 text-center sk-body"
          >
            측정 목록에 미완료·무효 열(not_completed_count, invalid_count)이 아직 적재되지 않았습니다.
          </p>
          <AfmUsageDayBars
            v-else
            :days="days"
            :series="failureSeries"
            :selected="day"
            :export-name="`${toolId}-usage-failures`"
            @select="picked = $event"
          />
        </AfmCard>

        <AfmCard
          class="xl:col-span-7"
          icon="i-lucide-list"
          title="선택한 날의 측정"
          :count="dayList.length"
          flush
        >
          <template #actions>
            <span class="sk-meta"><b class="sk-value-num">{{ day ?? '–' }}</b> · 최근 측정부터 · 행을 누르면 측정을 엽니다</span>
          </template>
          <p
            v-if="!dayList.length"
            class="px-4 py-10 text-center sk-body"
          >
            {{ day ? '이 날에는 측정이 없습니다.' : '이 기간에 측정이 없습니다.' }}
          </p>
          <div
            v-else
            class="max-h-80 overflow-auto"
          >
            <table class="w-full border-collapse">
              <thead class="sticky top-0 bg-(--sk-surface)">
                <tr class="border-b border-(--sk-border)">
                  <th
                    v-for="h in HEADERS"
                    :key="h.label"
                    class="px-3 py-2 whitespace-nowrap sk-label"
                    :class="h.num ? 'text-right' : 'text-left'"
                  >
                    {{ h.label }}
                  </th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="item in dayList"
                  :key="item.row.filename"
                  class="cursor-pointer border-b border-(--sk-border-soft) hover:bg-(--sk-muted-surface)"
                  tabindex="0"
                  @click="open(item)"
                  @keydown.enter="open(item)"
                >
                  <td class="px-3 py-1.5 whitespace-nowrap sk-value-num text-(--sk-ink-muted)">
                    {{ item.clock || '–' }}
                  </td>
                  <td class="px-3 py-1.5 sk-value-num">
                    {{ item.recipe || '–' }}
                  </td>
                  <td class="px-3 py-1.5 whitespace-nowrap sk-value-num">
                    {{ item.lot || '–' }} <span class="text-(--sk-ink-muted)">/ {{ item.row.slot_number ?? '–' }}</span>
                  </td>
                  <td class="px-3 py-1.5 text-right sk-value-num">
                    {{ item.points ?? '–' }}
                  </td>
                  <td
                    class="px-3 py-1.5 text-right sk-value-num"
                    :class="item.notCompleted ? 'font-semibold text-(--sk-brand)' : ''"
                  >
                    {{ item.notCompleted ?? '–' }}
                  </td>
                  <td
                    class="px-3 py-1.5 text-right sk-value-num"
                    :class="item.invalid ? 'font-semibold text-(--sk-brand)' : ''"
                  >
                    {{ item.invalid ?? '–' }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </AfmCard>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import {
  TOP_RECIPES,
  dailyByRecipe,
  dayRows,
  failureDaily,
  hourGrid,
  inWindow,
  latestDay,
  usageRows,
  usageSummary,
  usageWindow,
  usageDays,
  type UsageRow
} from '~/utils/afmUsage'
import { toMeasurement } from '~/utils/afmSearch'
import { SK_STATE } from '~/utils/chartPalette'

// `key` remounts the page per tool, so the route params are read once.
definePageMeta({
  key: route => route.path
})

const toolId = String(useRoute().params.tool ?? '')
const toolName = toolId.toUpperCase()
const { fabs } = useAfmToolData()
const cart = useAfmCart(toolId)

const { data, pending, error } = useAfmDetailApi().useAfmTipRows(toolName)

// 기간 counts back from today, in the viewer's own time zone — as 측정 검색 does.
const today = todayStamp()

const all = computed(() => usageRows(data.value ?? []))
const undated = computed(() => all.value.filter(r => r.day === null).length)
// The tool's whole dated span, whatever 기간 says.
const span = computed(() => usageWindow(data.value ?? [], null, today))
const subtitle = computed(() => span.value
  ? `측정 ${(all.value.length - undated.value).toLocaleString()}건 · ${span.value[0]} ~ ${span.value[1]}${undated.value ? ` · 날짜 없는 측정 ${undated.value.toLocaleString()}건 제외` : ''}`
  : undefined)

const PERIODS = [
  { value: '7', label: '7일' },
  { value: '30', label: '30일' },
  { value: 'all', label: '전체' }
] as const
const period = ref<typeof PERIODS[number]['value']>('30')

const range = computed(() => usageWindow(data.value ?? [], period.value === 'all' ? null : Number(period.value), today))
const days = computed(() => range.value ? usageDays(range.value) : [])
const rows = computed(() => range.value ? inWindow(all.value, range.value) : [])

const summary = computed(() => usageSummary(rows.value))
const tiles = computed(() => {
  const s = summary.value
  const { hit, known } = s.notCompleted
  return [
    { label: '측정', value: s.count.toLocaleString(), meta: '건' },
    { label: '가동일', value: `${s.activeDays} / ${days.value.length}일`, meta: '측정이 1건 이상인 날' },
    { label: '일평균', value: s.perActiveDay === null ? '–' : s.perActiveDay.toFixed(1), meta: '가동일 하루당 측정' },
    { label: 'Recipe', value: s.recipes.toLocaleString(), meta: '종' },
    { label: 'Lot', value: s.lots.toLocaleString(), meta: '개' },
    {
      label: '측정 point',
      value: s.pointsMissing === s.count && s.count ? '–' : s.points.toLocaleString(),
      meta: s.pointsMissing ? `point 수 없는 측정 ${s.pointsMissing.toLocaleString()}건 제외` : 'point_count 합'
    },
    {
      label: '미완료 측정',
      value: known ? `${hit} / ${known}건` : '–',
      meta: known ? (known < s.count ? `값 없는 측정 ${(s.count - known).toLocaleString()}건 제외` : 'FAILED·STOPPED point가 있는 측정') : '미완료 열이 아직 없습니다',
      warn: hit > 0
    }
  ]
})

const daily = computed(() => dailyByRecipe(rows.value, days.value))
const hours = computed(() => hourGrid(rows.value, days.value))
const failures = computed(() => failureDaily(rows.value, days.value))
const failureSeries = computed(() => [
  { name: '미완료 포함', values: failures.value.series?.notCompleted ?? [], color: SK_STATE.warn },
  { name: 'Valid=FALSE 포함', values: failures.value.series?.invalid ?? [], color: SK_STATE.bad }
])
// A measurement whose column is null is in neither series: say how many.
const failureMissing = computed(() => {
  const { notCompletedMissing: a, invalidMissing: b } = failures.value
  if (!a && !b) return ''
  return a === b ? `값 없는 측정 ${a.toLocaleString()}건 제외` : `값 없는 측정 제외: 미완료 ${a.toLocaleString()}건 · 무효 ${b.toLocaleString()}건`
})

// The day on show: the one picked while it is inside the window, else the
// latest day that measured.
const picked = ref<string | null>(null)
const day = computed(() =>
  picked.value && days.value.includes(picked.value) ? picked.value : latestDay(rows.value))
const dayList = computed(() => day.value ? dayRows(rows.value, day.value) : [])

const HEADERS = [
  { label: '시각' }, { label: 'Recipe' }, { label: 'Lot / Slot' },
  { label: 'Point', num: true }, { label: '미완료', num: true }, { label: '무효', num: true }
]

const open = (item: UsageRow) => {
  cart.addToHistory(toMeasurement(item.row))
  navigateTo(`/afm/${toolId}/${encodeURIComponent(item.row.filename)}`)
}
</script>
