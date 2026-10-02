<template>
  <div class="px-4 md:px-6 lg:px-8 py-6 md:py-8 space-y-6">
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
    </EbeamMetaBar>

    <AppEmptyState
      v-if="groupedItems.length === 0"
      icon="i-lucide-layers-2"
      title="그룹에 담긴 측정이 없습니다."
      description="검색 화면에서 측정을 데이터 그룹에 추가한 뒤 다시 여세요."
    />

    <div
      v-else
      class="grid items-start gap-6 min-[112.5rem]:grid-cols-12"
    >
      <AfmCard
        class="min-[112.5rem]:col-span-4"
        icon="i-lucide-list-checks"
        title="선택한 측정"
        :count="groupedItems.length"
        flush
      >
        <ul class="divide-y divide-(--sk-border-soft)">
          <li
            v-for="item in sortedGroupedItems"
            :key="item.filename"
            class="flex min-w-0 flex-wrap items-center gap-x-3 gap-y-1 px-4 py-2.5"
          >
            <span class="sk-value-num font-semibold">
              {{ item.formattedDate }}
            </span>
            <span class="truncate text-sm font-medium">
              {{ item.recipeName }}
            </span>
            <span class="sk-value-num">
              {{ item.lotId }}
            </span>
            <UBadge
              :label="`Slot ${item.slotNumber}`"
              color="neutral"
              variant="subtle"
            />
            <UBadge
              :label="item.measuredInfo"
              color="neutral"
              variant="outline"
            />
          </li>
        </ul>
      </AfmCard>

      <div class="space-y-6 min-[112.5rem]:col-span-8">
        <UAlert
          v-if="failedCount > 0"
          color="warning"
          variant="soft"
          icon="i-lucide-triangle-alert"
          :title="`측정 ${failedCount}건을 불러오지 못했습니다.`"
          description="아래 차트는 불러온 측정만 사용합니다."
        />

        <AfmCard
          icon="i-lucide-chart-no-axes-combined"
          title="시계열"
          :count="loaded.length"
        >
          <template #actions>
            <div class="flex flex-wrap items-center gap-2">
              <USelect
                v-model="selectedSite"
                :items="siteItems"
                size="xs"
                class="min-w-28"
                aria-label="사이트"
              />
              <USelect
                v-model="selectedItem"
                :items="AFM_SUMMARY_ITEMS"
                size="xs"
                class="min-w-28"
                aria-label="통계 항목"
              />
              <USelect
                v-model="selectedColumn"
                :items="columnItems"
                size="xs"
                class="min-w-36"
                aria-label="측정 항목"
              />
            </div>
          </template>

          <AppLoadingState
            v-if="pending"
            variant="inline"
            class="h-96"
            title="측정 상세 데이터를 불러오는 중입니다."
          />
          <AfmTrendTimeSeriesChart
            v-else
            :points="chartPoints"
            :series-name="selectedSite"
            :y-name="selectedColumn"
            :export-name="`${toolId}-trend`"
          />
        </AfmCard>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { AfmSummaryItem } from '~/composables/useAfmDetailApi'
import { AFM_SUMMARY_ITEMS } from '~/composables/useAfmDetailApi'

// `key` remounts the page per tool, so the route params are read once.
definePageMeta({
  layout: 'hub',
  key: route => route.path
})

const toolId = String(useRoute().params.tool ?? '')
const toolName = toolId.toUpperCase()
const { groupedData: groupedItems } = useAfmCart(toolId)
const { fetchDetail } = useAfmDetailApi()

const sortedGroupedItems = computed(() =>
  [...groupedItems.value].sort((a, b) => a.formattedDate.localeCompare(b.formattedDate))
)
const groupKey = computed(() => groupedItems.value.map(item => item.filename).sort().join('|'))

// One request per grouped measurement. A failed one resolves to a null payload,
// so the rest still chart and the alert above the chart counts what is missing.
const { data: results, pending } = useAsyncData(
  `afm-see-together:${toolName}`,
  () => Promise.all(groupedItems.value.map(async measurement => ({
    measurement,
    payload: await fetchDetail(toolName, measurement.filename)
      .then(res => res.success ? res.data : null, () => null)
  }))),
  { watch: [groupKey], default: () => [] }
)

const loaded = computed(() =>
  results.value.flatMap(({ measurement, payload }) => payload ? [{ measurement, payload }] : [])
)
const failedCount = computed(() => results.value.length - loaded.value.length)

const selectedSite = ref('')
const selectedItem = ref<AfmSummaryItem>('MEAN')
const selectedColumn = ref('')

const naturalSort = (values: Iterable<string>) =>
  [...new Set(values)].sort((a, b) => a.localeCompare(b, undefined, { numeric: true, sensitivity: 'base' }))

const siteItems = computed(() =>
  naturalSort(loaded.value.flatMap(({ payload }) => payload.summary.map(row => row.Site)))
)
const columnItems = computed(() =>
  naturalSort(loaded.value.flatMap(({ payload }) => summaryColumns(payload.summary)))
    .filter(column => column.toLowerCase().includes('nm'))
)

// Keep each pick valid as the loaded set changes; default to the first option.
watch(siteItems, (next) => {
  if (!next.includes(selectedSite.value)) selectedSite.value = next[0] ?? ''
}, { immediate: true })

watch(columnItems, (next) => {
  if (!next.includes(selectedColumn.value)) selectedColumn.value = next[0] ?? ''
}, { immediate: true })

const chartPoints = computed(() =>
  loaded.value.flatMap(({ measurement, payload }) => {
    const row = payload.summary.find(r => r.Site === selectedSite.value && r.ITEM === selectedItem.value)
    const value = summaryNumber(row?.[selectedColumn.value])
    if (value === null) return []
    const startTime = payload.information['Start Time']
    return [{
      timestamp: typeof startTime === 'string' && startTime.trim() ? startTime : measurement.formattedDate,
      value,
      lotId: measurement.lotId,
      recipe: measurement.recipeName,
      filename: measurement.filename
    }]
  }).sort((a, b) => Date.parse(a.timestamp) - Date.parse(b.timestamp))
)
</script>
