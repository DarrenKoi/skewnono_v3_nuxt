<template>
  <div class="space-y-6">
    <EbeamMetaBar
      :eyebrow="`AFM · ${toolName}`"
      title="AFM 시계열 비교"
      :subtitle="`선택한 측정 ${groupedItems.length}건`"
    >
      <template #leading>
        <AppBackButton
          :to="`/afm/${toolId}`"
          label="검색으로"
        />
      </template>
      <template
        v-if="groupedItems.length"
        #actions
      >
        <UDropdownMenu
          :items="exportItems"
          :content="{ align: 'end' }"
          :ui="{ content: 'w-64' }"
        >
          <UButton
            size="sm"
            color="neutral"
            variant="outline"
            icon="i-lucide-download"
            trailing-icon="i-lucide-chevron-down"
            label="Excel 다운로드"
          />
        </UDropdownMenu>
      </template>
    </EbeamMetaBar>

    <AppEmptyState
      v-if="groupedItems.length === 0"
      icon="i-lucide-layers-2"
      title="그룹에 담긴 측정이 없습니다."
      description="검색 화면에서 측정을 데이터 그룹에 추가한 뒤 다시 여세요."
    />

    <AppLoadingState
      v-else-if="pending"
      title="측정 상세 데이터를 불러오는 중입니다."
    />

    <template v-else>
      <UAlert
        v-if="failedCount > 0"
        color="warning"
        variant="soft"
        icon="i-lucide-triangle-alert"
        :title="`측정 ${failedCount}건을 불러오지 못했습니다.`"
        description="아래 카드는 불러온 측정만 사용합니다."
      />
      <UAlert
        v-if="mixed"
        color="warning"
        variant="soft"
        icon="i-lucide-triangle-alert"
        :title="`recipe ${recipes.length}종이 섞인 그룹입니다.`"
        :description="`${recipes.join(', ')} — 같은 이름의 측정 항목이 recipe마다 같은 측정량이라는 보장이 없습니다. 추세는 recipe별 시리즈와 기준 범위로 나누고, 포인트 비교는 선택한 측정의 recipe만 보이며, 변동 분해와 그룹 행은 내지 않습니다.`"
      />

      <!-- 분석 조건: block × column × statistic, read by every card below. -->
      <section class="dashboard-surface rounded-(--sk-r-card)">
        <div class="flex flex-wrap items-center justify-between gap-3 border-b border-(--sk-border) px-4 py-3">
          <div class="flex flex-wrap items-center gap-3.5">
            <label class="flex items-center gap-1.5">
              <span class="sk-label">블록</span>
              <USelect
                v-model="block"
                :items="blockItems"
                size="xs"
                class="min-w-36"
                aria-label="블록"
              />
            </label>
            <div
              class="flex flex-wrap items-center gap-1.5"
              role="group"
              aria-label="측정 항목"
            >
              <span class="sk-label">측정 항목</span>
              <SkChip
                v-for="c in columnItems"
                :key="c"
                size="sm"
                :label="c"
                :active="column === c"
                @click="column = c"
              />
            </div>
            <label class="flex items-center gap-1.5">
              <span class="sk-label">통계</span>
              <USelect
                v-model="stat"
                :items="AFM_SUMMARY_ITEMS"
                size="xs"
                class="min-w-24"
                aria-label="통계 항목"
              />
            </label>
          </div>
          <span class="sk-meta">{{ mixed ? `recipe ${recipes.length}종 · recipe별로 시리즈를 나눕니다` : `같은 recipe ${entries.length}건 · ${recipes[0] ?? ''}` }}</span>
        </div>
        <AfmTrendKpiStrip
          class="p-4"
          :kpis="kpis"
        />
      </section>

      <AfmTrendSection
        num="01"
        title="추세"
        :hint="`측정마다 분포를 입히고, ${pinned ? '기준으로 고정한 측정' : '그룹'}의 평균 ± 3σ를 ${bandName}로 긋습니다. 범위 밖의 측정은 붉은 점으로 표시합니다. 관리 한계나 규격이 아닌 참고 범위입니다.`"
      />
      <div class="grid grid-cols-1 gap-6 2xl:grid-cols-12">
        <AfmTrendChart
          v-model:show-limits="showLimits"
          class="min-w-0 2xl:col-span-8"
          :rows="rows"
          :recipes="recipes"
          :centres="centres"
          :block="block"
          :column="column"
          :stat="stat"
          :selected="selected"
          :export-name="`${toolId}-trend`"
          @select="select"
        />
        <AfmTrendMeasurementList
          class="min-w-0 2xl:col-span-4"
          :rows="rows"
          :stat="stat"
          :selected="selected"
          :repeat-keys="repeatKeys"
          :mixed="mixed"
          @select="select"
          @toggle-baseline="toggleBaseline"
        />
      </div>

      <AfmTrendSection
        num="02"
        title="포인트별 비교"
        hint="x축이 시간 대신 포인트입니다. 센터·에지 패턴이 lot마다 되풀이되는지, 한 포인트만 흘러가는지가 보입니다."
      />
      <div class="grid grid-cols-1 gap-6 2xl:grid-cols-12">
        <AfmTrendPointsChart
          class="min-w-0 2xl:col-span-8"
          :rows="pointRows"
          :recipe="pointRecipe"
          :block="block"
          :column="column"
          :selected="selected"
          :export-name="`${toolId}-points`"
          @select="select"
        />
        <AfmTrendStabilityChart
          class="min-w-0 2xl:col-span-4"
          :rows="pointRows"
          :export-name="`${toolId}-point-stability`"
        />
      </div>

      <AfmTrendSection
        num="03"
        title="그룹 통계"
        hint="측정별 요약 한 줄씩, 그리고 변동이 lot 간에서 왔는지 wafer 안에서 왔는지."
      />
      <div class="grid grid-cols-1 items-start gap-6 2xl:grid-cols-12">
        <AfmTrendStatsTable
          class="min-w-0 2xl:col-span-8"
          :rows="rows"
          :block="block"
          :column="column"
          :stat="stat"
          :selected="selected"
          :mixed="mixed"
          @select="select"
        />
        <div class="grid min-w-0 grid-cols-1 gap-6 2xl:col-span-4">
          <AfmTrendVarianceSplit
            :split="split"
            :mixed="mixed"
          />
          <AfmTrendRepeatability
            v-if="pairs.length"
            :pairs="pairs"
          />
        </div>
      </div>

      <AfmTrendSection
        num="04"
        title="장비 건강"
        hint="값이 흔들린 측정에 FAILED·approach 증가가 같이 보이면 공정이 아니라 팁·장비를 먼저 의심합니다."
      />
      <AfmTrendHealthStrip
        :health="health"
        :selected="selected"
        :export-name="`${toolId}-health`"
        @select="select"
      />

      <AfmTrendSection
        num="05"
        title="측정 소요시간"
        hint="Info의 Start Time과 End Time이 모두 있는 측정만 계산합니다. 값이 없는 측정은 이유를 표시합니다."
      />
      <AfmTrendDuration
        :rows="durations"
        :recipes="durationSummary"
        :selected="selected"
        @select="select"
      />
    </template>
  </div>
</template>

<script setup lang="ts">
import type { DropdownMenuItem } from '@nuxt/ui'
import type { AfmSummaryItem } from '~/composables/useAfmDetailApi'
import { AFM_SUMMARY_ITEMS } from '~/composables/useAfmDetailApi'
import type { TrendKpi } from '~/components/afm/trend/KpiStrip.vue'
import { mean } from '~/utils/stats'

// `key` remounts the page per tool, so the route params are read once.
definePageMeta({
  key: route => route.path
})

const toolId = String(useRoute().params.tool ?? '')
const toolName = toolId.toUpperCase()
const { groupedData: groupedItems, baselineKeys, toggleBaseline } = useAfmCart(toolId)
const { fetchDetail } = useAfmDetailApi()

const groupKey = computed(() => groupedItems.value.map(item => item.filename).sort().join('|'))

// One request per grouped measurement. A failed one resolves to a null payload,
// so the rest still chart and the alert above the cards counts what is missing.
const { data: results, pending } = useAsyncData(
  `afm-see-together:${toolName}`,
  () => Promise.all(groupedItems.value.map(async measurement => ({
    measurement,
    payload: await fetchDetail(toolName, measurement.filename)
      .then(res => res.success ? res.data : null, () => null)
  }))),
  { watch: [groupKey], default: () => [] }
)

const entries = computed(() => prepareEntries(
  results.value.flatMap(({ measurement, payload }) => payload ? [{ source: measurement, payload }] : [])
))
const failedCount = computed(() => results.value.length - entries.value.length)
const recipes = computed(() => [...new Set(entries.value.map(entry => entry.recipe))])
const mixed = computed(() => recipes.value.length > 1)

const block = ref('')
const column = ref('')
const stat = ref<AfmSummaryItem>('MEAN')
const showLimits = ref(true)
// The one selected measurement every card highlights, by filename.
const selected = ref<string | null>(null)
const select = (key: string) => {
  selected.value = key
}

// Blocks in payload order; columns as today — the union, natural order.
const blockItems = computed(() => [...new Set(entries.value.flatMap(entry => entry.blocks))])
const columnItems = computed(() =>
  [...new Set(entries.value.flatMap(({ payload }) => [
    ...summaryColumns(payload.summary),
    ...payload.data.flatMap(row => Object.keys(row))
  ]))]
    .filter(isMeasurementKey)
    .sort((a, b) => a.localeCompare(b, undefined, { numeric: true, sensitivity: 'base' }))
)

// Keep each pick valid as the loaded set changes; default to the first option.
watch(blockItems, (next) => {
  if (!next.includes(block.value)) block.value = next[0] ?? ''
}, { immediate: true })
watch(columnItems, (next) => {
  if (!next.includes(column.value)) column.value = next[0] ?? ''
}, { immediate: true })

const trend = computed(() => trendRows(entries.value, block.value, column.value, stat.value, showLimits.value, baselineKeys.value))
const rows = computed(() => trend.value.rows)
const centres = computed(() => trend.value.centres)
const valued = computed(() => rows.value.filter(row => row.value !== null))
// 고정 기준선: some loaded measurement is pinned, so μ and the band are its.
const pinnedCount = computed(() => rows.value.filter(row => row.role === 'baseline').length)
const pinned = computed(() => pinnedCount.value > 0)
const bandName = computed(() => trendBandName(pinned.value))

// Start on the newest measurement that has a value; keep a pick that still exists.
watch(rows, (next) => {
  if (!next.some(row => row.entry.key === selected.value)) {
    selected.value = next.findLast(row => row.value !== null)?.entry.key ?? null
  }
}, { immediate: true })

const split = computed(() => mixed.value ? null : varianceSplit(rows.value.flatMap(row => row.stats ?? [])))
// Each recipe's wafer σ̄ (mean STDEV): a repeat is judged against its own recipe.
const waferSd = computed(() => new Map(recipes.value.map((recipe) => {
  const sds = rows.value.flatMap(row => row.entry.recipe === recipe ? row.stats?.STDEV ?? [] : [])
  return [recipe, sds.length ? mean(sds) : null]
})))
const pairs = computed(() => repeatPairs(
  rows.value.map(({ entry, stats }) => ({ key: entry.key, sample: entry.sample, recipe: entry.recipe, time: entry.time, mean: stats?.MEAN ?? null })),
  recipe => waferSd.value.get(recipe) ?? null
))
// Point keys belong to a recipe, so a mixed group compares points within the
// selected measurement's recipe only.
const pointRecipe = computed(() => mixed.value ? rows.value.find(row => row.entry.key === selected.value)?.entry.recipe ?? recipes.value[0] ?? '' : '')
const pointRows = computed(() => pointRecipe.value ? rows.value.filter(row => row.entry.recipe === pointRecipe.value) : rows.value)
const repeatKeys = computed(() => new Set(pairs.value.flatMap(pair => pair.keys)))
const health = computed(() => healthSeries(entries.value))
const durations = computed(() => durationRows(entries.value))
const durationSummary = computed(() => durationByRecipe(durations.value))

const kpis = computed<TrendKpi[]>(() => {
  const only = mixed.value ? null : centres.value.get(recipes.value[0] ?? '') ?? null
  const outCount = valued.value.filter(row => row.out).length
  const troubled = health.value.filter(h => h.notCompleted > 0).length
  const limits = only?.limits
  return [
    {
      label: pinned.value ? '기준 평균 μ' : '그룹 평균 μ',
      value: fmt2(only?.mu),
      sub: mixed.value ? 'recipe별로 따로 냅니다' : `${column.value} · ${stat.value}`
    },
    { label: 'lot 간 σ', value: fmt2(split.value?.lotSd), sub: 'MEAN들의 표본 표준편차' },
    { label: 'wafer 내 σ̄', value: fmt2(split.value?.waferSd), sub: '측정별 STDEV 평균' },
    {
      label: `${bandName.value} 밖`,
      value: `${outCount}건`,
      sub: !showLimits.value
        ? '기준 범위 꺼짐'
        : limits
          ? `${pinned.value ? `기준 ${pinnedCount.value}건의 ` : ''}μ ± 3σ · ${fmt2(limits.lcl)} ~ ${fmt2(limits.ucl)}`
          : mixed.value ? 'recipe별 μ ± 3σ' : only?.reason ? `${only.reason} · 기준 값 2건 이상부터` : '값 2건 이상부터',
      alert: outCount > 0
    },
    { label: 'FAILED · STOPPED', value: `${troubled}건`, sub: `측정 ${entries.value.length}건 중`, alert: troubled > 0 },
    { label: '재측정 쌍', value: `${pairs.value.length}쌍`, sub: '같은 Sample ID' }
  ]
})

const downloadTable = useTableDownload()
const exportItems = computed<DropdownMenuItem[][]>(() => [[{
  label: `측정별 요약 (${rows.value.length}건)`,
  icon: 'i-lucide-table',
  disabled: rows.value.length === 0,
  onSelect: () => {
    const table = trendTable(rows.value)
    downloadTable(`${toolId}-trend-${safeFilePart(block.value)}-${safeFilePart(column.value)}.xlsx`, table.headers, table.rows)
  }
}]])
</script>
