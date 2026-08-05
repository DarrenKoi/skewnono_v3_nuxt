<template>
  <div class="space-y-3">
    <EbeamMetaBar
      eyebrow="CD-SEM"
      :title="text.title"
      :subtitle="text.subtitle"
      :stats="metaStats"
    >
      <template #toggle>
        <div class="flex flex-wrap items-center gap-2">
          <div
            role="radiogroup"
            :aria-label="text.fabSelect"
            class="inline-flex flex-wrap items-center gap-1 rounded-lg bg-zinc-100/70 p-1 dark:bg-zinc-800/60"
          >
            <button
              v-for="option in deviceFabOptions"
              :key="option.value"
              type="button"
              role="radio"
              :aria-checked="selectedFab === option.value"
              class="inline-flex h-9 items-center gap-2 rounded-md px-4 text-sm font-semibold transition-colors"
              :class="selectedFab === option.value
                ? 'bg-white text-zinc-900 shadow-sm ring-1 ring-zinc-200/80 dark:bg-zinc-900 dark:text-zinc-50 dark:ring-zinc-700/80'
                : 'text-(--sk-ink-muted) hover:text-(--sk-ink)'"
              @click="selectedFab = option.value"
            >
              {{ option.label }}
            </button>
          </div>
          <UButton
            v-if="hasRSelection"
            to="/ebeam/cd-sem/device-statistics/measurement-rules"
            size="md"
            color="neutral"
            variant="outline"
            icon="i-lucide-ruler"
            :label="text.rulesLink"
          />
        </div>
      </template>
    </EbeamMetaBar>

    <!-- Step 1 — 그룹별 필터 카드. 예전에는 세 그룹이 한 줄짜리 칩 스트립으로
         나란히 붙어 있어서, 어느 칩이 어느 필터에 속하는지 왼쪽 끝의 10px
         mono 필드명을 되짚어야 알 수 있었습니다. -->
    <div class="dashboard-surface rounded-2xl px-4 py-3.5">
      <div class="mb-3 flex flex-wrap items-center justify-between gap-3">
        <div class="flex items-center gap-2.5">
          <span class="inline-flex h-6 w-6 items-center justify-center rounded-full bg-(--sk-accent) font-mono text-[13px] font-bold text-white">1</span>
          <h3 class="sk-panel-title">
            {{ text.step1Title }}
          </h3>
          <span class="sk-hint">
            {{ hasRSelection ? text.step1HintR : text.step1HintM }}
          </span>
        </div>
        <div class="flex items-center gap-2">
          <span
            v-if="hasActiveFilters"
            class="inline-flex h-[30px] items-center rounded-md bg-(--sk-accent-tint) px-2.5 font-mono text-sm font-semibold tabular-nums text-(--sk-accent)"
          >
            {{ filteredRowCount.toLocaleString() }} / {{ rows.length.toLocaleString() }}
          </span>
          <UButton
            color="neutral"
            variant="ghost"
            icon="i-lucide-rotate-ccw"
            class="h-[34px] px-3 text-sm font-semibold"
            :label="text.reset"
            :disabled="!hasActiveFilters"
            @click="resetAllFilters"
          />
        </div>
      </div>

      <div
        class="grid grid-cols-1 gap-3"
        :class="hasRSelection
          ? 'xl:grid-cols-[minmax(220px,0.8fr)_minmax(220px,0.8fr)_2fr]'
          : 'xl:grid-cols-[minmax(220px,0.8fr)_3fr]'"
      >
        <div
          class="filter-card"
          :title="text.topNHint"
        >
          <div class="filter-card__head">
            <span class="filter-card__title">{{ text.topNTitle }}</span>
            <span class="sk-field-name">{{ text.topNScope }}</span>
          </div>
          <div class="flex flex-wrap items-center gap-1.5">
            <button
              type="button"
              :class="[CHIP_BASE, chipClass(selectedTopN === null)]"
              @click="selectedTopN = null"
            >
              {{ text.topNAll }}
            </button>
            <button
              v-for="option in topNOptions"
              :key="option"
              type="button"
              :class="[CHIP_BASE_MONO, chipClass(selectedTopN === option)]"
              @click="selectedTopN = selectedTopN === option ? null : option"
            >
              {{ option }}
            </button>
          </div>
        </div>

        <div
          v-if="hasRSelection"
          class="filter-card"
        >
          <div class="filter-card__head">
            <span class="filter-card__title">{{ text.categoryTitle }}</span>
            <span class="sk-field-name">prod_catg_cd</span>
          </div>
          <div class="flex flex-wrap items-center gap-1.5">
            <button
              v-for="category in prodCategoryOptions"
              :key="category"
              type="button"
              :class="[CHIP_BASE, chipClass(isProdCategorySelected(category))]"
              @click="toggleProdCategory(category)"
            >
              {{ category }}
            </button>
          </div>
        </div>

        <div class="filter-card">
          <div class="filter-card__head">
            <span class="filter-card__title">{{ identityFilter.title }}</span>
            <span class="sk-field-name">{{ identityFilter.fieldName }} · {{ identityFilter.total }}개 중 {{ identityFilter.strip.chips.length }}개 표시</span>
          </div>
          <div class="flex flex-wrap items-center gap-1.5">
            <UInput
              v-model="identitySearch"
              class="w-48 shrink-0"
              size="md"
              color="neutral"
              variant="subtle"
              icon="i-lucide-search"
              :placeholder="identityFilter.placeholder"
            />
            <button
              v-for="value in identityFilter.strip.chips"
              :key="value"
              type="button"
              :class="[identityFilter.mono ? CHIP_BASE_MONO : CHIP_BASE, chipClass(identityFilter.isSelected(value))]"
              @click="identityFilter.toggle(value)"
            >
              {{ value }}
            </button>
            <button
              v-if="identityFilter.strip.overflowCount > 0 || chipsExpanded"
              type="button"
              :class="[CHIP_BASE, 'bg-(--sk-muted-surface) text-(--sk-ink-muted) ring-(--sk-border-soft) hover:text-(--sk-ink)']"
              @click="chipsExpanded = !chipsExpanded"
            >
              {{ chipsExpanded ? text.collapseChips : `${text.expandChips} +${identityFilter.strip.overflowCount}` }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Step 2 (table) + Step 3 (cart) -->
    <div class="grid grid-cols-12 gap-3">
      <div class="col-span-12 space-y-2 lg:col-span-8">
        <div class="flex items-center gap-2.5 px-1">
          <span class="inline-flex h-6 w-6 items-center justify-center rounded-full bg-(--sk-accent) font-mono text-[13px] font-bold text-white">2</span>
          <h3 class="sk-panel-title">
            {{ text.step2Title }}
          </h3>
          <span class="sk-hint">
            {{ text.step2Hint }}
          </span>
        </div>

        <UCard
          class="dashboard-surface rounded-2xl"
          :ui="{ body: 'p-0 sm:p-0', header: 'px-4 py-3 sm:px-4' }"
        >
          <template #header>
            <div class="flex flex-wrap items-center justify-between gap-3">
              <p class="text-sm tabular-nums text-(--sk-ink-muted)">
                {{ pageStart }}-{{ pageEnd }} / {{ filteredRowCount }} rows
              </p>
              <UButton
                color="neutral"
                variant="outline"
                icon="i-lucide-rotate-ccw"
                class="h-[34px] px-3 text-sm font-semibold"
                :label="text.resetAll"
                :disabled="!hasActiveFilters"
                @click="resetAllFilters"
              />
            </div>
          </template>

          <div class="flex flex-wrap items-center gap-2 border-b border-(--sk-border-soft) px-4 py-3">
            <UInput
              v-model="tableSearch"
              class="min-w-56 flex-1"
              size="md"
              color="neutral"
              variant="subtle"
              icon="i-lucide-search"
              :placeholder="text.tableSearch"
            />
            <AppViewToggle
              v-model="view"
              :aria-label="text.viewToggle"
            />
            <USelect
              v-model="pageSize"
              class="w-28"
              size="md"
              color="neutral"
              variant="subtle"
              :items="pageSizeOptions"
            />
            <UTooltip text="클립보드 복사">
              <UButton
                color="neutral"
                variant="outline"
                icon="i-lucide-clipboard"
                class="h-[34px] px-3 text-sm font-semibold"
                :aria-label="text.clipboardCopy"
                :disabled="filteredRowCount === 0"
                @click="copyDeviceList"
              />
            </UTooltip>
            <UButton
              color="neutral"
              variant="outline"
              icon="i-lucide-download"
              class="h-[34px] px-3.5 text-sm font-semibold"
              :label="text.csvDownload"
              :disabled="filteredRowCount === 0"
              @click="downloadDeviceListCsv"
            />
          </div>

          <AppLoadingState
            v-if="pending"
            variant="inline"
            :title="text.loading"
          />
          <div
            v-else-if="error"
            class="px-4 py-12 text-center sk-body text-rose-600 dark:text-rose-300"
          >
            {{ text.loadError }}
          </div>

          <!-- 행 카드. 10열 표에서 옮긴 것: Lot 은 카드 제목, Category/Grade 는
               배지, Fab·Tech 같은 고정값은 라벨 달린 메타 줄, Meas (90d)는
               오른쪽 큰 숫자. description 은 잘리지 않고 그대로 읽힙니다. -->
          <template v-else-if="view === 'cards'">
            <p
              v-if="deviceCards.length === 0"
              class="px-4 py-12 text-center sk-body text-(--sk-ink-muted)"
            >
              {{ text.emptyRows }}
            </p>
            <!-- 표의 헤더 행에 해당합니다. 전체 선택 체크박스는 표와 같은
                 페이지 단위이고, '90일 측정'은 카드마다 반복하지 않고 여기서
                 오른쪽 숫자 열 위에 한 번만 답니다. -->
            <div
              v-else
              class="flex items-center gap-3.5 border-b border-(--sk-border-soft) px-4 py-2"
            >
              <label class="flex cursor-pointer items-center gap-3.5">
                <input
                  type="checkbox"
                  :checked="allOnPageSelected"
                  class="h-[18px] w-[18px] flex-none rounded accent-(--sk-accent)"
                  @change="togglePageSelection"
                >
                <span class="sk-field-label">{{ text.selectAll }}</span>
              </label>
              <span class="ml-auto w-24 flex-none pl-2 text-right sk-field-label">
                {{ text.measCaption }}
              </span>
            </div>
            <label
              v-for="card in deviceCards"
              :key="card.row.lot_cd"
              class="flex cursor-pointer items-start gap-3.5 border-b border-(--sk-border-soft) px-4 py-3.5 transition-colors last:border-b-0 hover:bg-(--sk-muted-surface) has-checked:bg-(--sk-accent-tint)"
            >
              <input
                type="checkbox"
                :checked="isDeviceSelected(card.row.lot_cd)"
                class="mt-1 h-[18px] w-[18px] flex-none rounded accent-(--sk-accent)"
                @change="toggleDeviceSelect(card.row.lot_cd)"
              >
              <div class="min-w-0 flex-1">
                <div class="flex flex-wrap items-center gap-2">
                  <span class="sk-card-id">{{ card.row.lot_cd }}</span>
                  <span
                    v-for="badge in card.badges"
                    :key="badge.label"
                    class="sk-badge font-bold"
                    :class="badge.accent
                      ? 'bg-(--sk-brand-soft) font-sans text-(--sk-brand-ink)'
                      : 'bg-(--sk-muted-surface) text-(--sk-ink-muted)'"
                  >{{ badge.label }}</span>
                </div>
                <p class="mt-1.5 sk-card-desc">
                  {{ card.row.ctn_desc || '—' }}
                </p>
                <div class="mt-1.5 flex flex-wrap gap-x-5 gap-y-0.5">
                  <span
                    v-for="field in card.meta"
                    :key="field.label"
                    class="sk-field-label"
                  >
                    {{ field.label }} <span class="sk-field-value">{{ field.value || '—' }}</span>
                  </span>
                </div>
              </div>
              <div class="w-24 flex-none pl-2 text-right">
                <div
                  v-if="card.measCount !== undefined"
                  class="font-mono text-[19px] font-semibold leading-tight tabular-nums text-(--sk-ink)"
                >{{ card.measCount.toLocaleString() }}</div>
                <div
                  v-else
                  class="font-mono text-[19px] font-semibold leading-tight text-(--sk-ink-subtle)"
                  :title="text.noMeasRank"
                >—</div>
              </div>
            </label>
          </template>

          <UTable
            v-else
            class="max-h-136 font-mono-ids"
            :columns="columns"
            :data="pagedRows"
            :empty="text.emptyRows"
            :meta="tableMeta"
            sticky="header"
            @select="(_, row) => toggleDeviceSelect(row.original.lot_cd)"
          >
            <template #select-header>
              <input
                type="checkbox"
                :checked="allOnPageSelected"
                :aria-label="text.selectAll"
                class="h-4 w-4 rounded accent-(--sk-accent)"
                @change="togglePageSelection"
              >
            </template>
            <template #select-cell="{ row }">
              <input
                type="checkbox"
                :checked="isDeviceSelected(row.original.lot_cd)"
                class="h-4 w-4 rounded accent-(--sk-accent)"
                @click.stop
                @change="toggleDeviceSelect(row.original.lot_cd)"
              >
            </template>
            <template #meas_count-cell="{ row }">
              <span
                v-if="measCountByLot.get(row.original.lot_cd) !== undefined"
                class="tabular-nums text-(--sk-ink-muted)"
              >{{ measCountByLot.get(row.original.lot_cd)!.toLocaleString() }}</span>
              <span
                v-else
                class="text-(--sk-ink-subtle)"
                :title="text.noMeasRank"
              >—</span>
            </template>
            <template #ctn_desc-cell="{ row }">
              <span class="block max-w-md truncate text-(--sk-ink-muted)">
                {{ row.original.ctn_desc }}
              </span>
            </template>
          </UTable>

          <div class="flex flex-wrap items-center justify-between gap-3 border-t border-(--sk-border-soft) px-4 py-3">
            <p class="text-sm tabular-nums text-(--sk-ink-muted)">
              Page {{ currentPage }} / {{ pageCount }}
            </p>
            <div class="flex gap-2">
              <UButton
                color="neutral"
                variant="outline"
                icon="i-lucide-chevron-left"
                class="h-[34px] px-3.5 text-sm font-semibold"
                :label="text.prev"
                :disabled="currentPage <= 1"
                @click="currentPage -= 1"
              />
              <UButton
                color="neutral"
                variant="outline"
                trailing-icon="i-lucide-chevron-right"
                class="h-[34px] px-3.5 text-sm font-semibold"
                :label="text.next"
                :disabled="currentPage >= pageCount"
                @click="currentPage += 1"
              />
            </div>
          </div>
        </UCard>
      </div>

      <div class="col-span-12 space-y-2 lg:col-span-4">
        <EbeamCompareCart
          :selected-device-rows="selectedDeviceRows"
          :fab="selectedFab"
          @proceed="proceedToStatistics"
          @apply-preset="applyPreset"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { TableColumn } from '@nuxt/ui'
import type { DeviceDescRow, MeasActivityRow, R3DeviceGrpRow } from '~/composables/useDeviceStatisticsApi'
import type { DevicePreset } from '~/composables/useDevicePresets'
import {
  DEFAULT_DEVICE_FAB,
  toDeviceFab,
  type DeviceFab
} from '~/composables/useDeviceStatisticsPreferences'
import { sameFab } from '~/utils/fab'
import type { MetaBarStat } from '~/components/ebeam/MetaBar.vue'
import { CHIP_BASE, CHIP_BASE_MONO, chipClass } from '~/utils/chipClass'
import { copyTableToClipboard, downloadCsv } from '~/utils/csvDownload'

definePageMeta({
  hideFabSidebar: true
})

type DeviceRow = R3DeviceGrpRow | DeviceDescRow

const { setToolType, setFab } = useNavigation()
const { fetchDeviceDesc, fetchMeasActivity, fetchR3DeviceGrp } = useDeviceStatisticsApi()

const text = {
  title: '디바이스 통계',
  subtitle: 'Fab 별로 운영중인 CD-SEM Recipe 현황을 확인합니다.',
  fabSelect: 'Fab',
  rulesLink: 'R3 계측 룰',
  reset: '초기화',
  lotSearch: 'Lot 검색 (예: R0A2)',
  techSearch: 'Tech 검색',
  csvDownload: 'CSV 다운로드',
  clipboardCopy: '표를 클립보드에 복사 (엑셀에 붙여넣기)',
  resetAll: '전체 초기화',
  tableSearch: '테이블 검색',
  allRows: '전체',
  filteredRows: '표시',
  activeFilters: '필터',
  loading: '로딩 중',
  loadError: '데이터를 불러오지 못했습니다.',
  emptyRows: '조건에 맞는 디바이스가 없습니다.',
  prev: '이전',
  next: '다음',
  step1Title: '빠른 필터',
  step1HintR: '한 그룹씩 읽고 고르기',
  step1HintM: 'Tech로 좁히기',
  topNAll: '전체',
  topNTitle: '측정 상위',
  topNScope: '90일 기준',
  topNHint: '최근 90일 측정 건수 순위 기준',
  categoryTitle: '카테고리',
  expandChips: '전체 보기',
  collapseChips: '접기',
  step2Title: '디바이스 선택',
  step2Hint: '체크박스로 여러 개 선택',
  viewToggle: '디바이스 목록 보기 방식',
  selectAll: '이 페이지 전체 선택',
  measCaption: '90일 측정',
  noMeasRank: '최근 90일 측정 순위에 없는 lot 입니다'
} as const

const deviceFabOptions: { label: string, value: DeviceFab }[] = [
  { label: 'R3', value: 'R3' },
  { label: 'M16', value: 'M16' },
  { label: 'M15', value: 'M15' },
  { label: 'M14', value: 'M14' },
  { label: 'M12', value: 'M12' },
  { label: 'M11', value: 'M11' }
]

const sortCollator = new Intl.Collator(undefined, { numeric: true, sensitivity: 'base' })
// Step 1 keeps the lot/tech chip strips compact: surface a small budget of unselected options,
// always paired with any currently-selected ones so they remain togglable from the strip.
//
// 8, not 24: at 34px the chips are twice the old height, so a 24-chip strip
// became four wrapped rows and pushed Step 2 below the fold. "전체 보기" lifts
// the cap for the rare case where someone is hunting a specific lot.
//
// R3 의 lot 과 M 계열의 tech 가 같은 값을 씁니다 — 두 스트립은 같은 자리에
// 배타적으로 서므로 예산이 갈라질 이유가 없습니다.
const STEP1_CHIP_BUDGET = 8

const {
  selectedFab,
  selectedProdCategories,
  selectedLots,
  selectedTechs
} = useDeviceStatisticsPreferences()

// Step 3 cart — extracted to useDeviceCart so the comparison sub-page reads the same ref.
const {
  selectedDeviceLots,
  selectedDeviceLotSet,
  isDeviceSelected,
  toggleDeviceSelect,
  addDeviceLots,
  removeDeviceLots
} = useDeviceCart()
const lotSearch = ref('')
const techSearch = ref('')
const tableSearch = ref('')
const currentPage = ref(1)

const view = useRowCardView('device-stats:listView', 'skewnono:deviceStatistics.listView')

// 기본 페이지 크기는 보기 방식을 따릅니다. 행 카드 한 장이 표 한 행보다 훨씬
// 높아 25 로 두면 한 페이지가 화면 세 개 분량이 되지만, 표 보기를 저장해 둔
// 사람에게까지 12행을 강요하면 정렬·붙여넣기 하러 온 쪽이 손해를 봅니다.
// 첫 값만 정하고 그 뒤로는 사용자가 고른 값을 그대로 둡니다.
const pageSize = ref(view.value === 'cards' ? '12' : '25')

const chipsExpanded = ref(false)

// 측정 상위 N 필터 — null 이면 전체. 세션 한정 상태라 preferences 에 넣지
// 않습니다(순위 탐색용 토글이지, 남겨 둘 작업 조건이 아닙니다).
const topNOptions = [10, 25, 50] as const
const selectedTopN = ref<number | null>(null)

const { data, pending, error } = await useAsyncData<DeviceRow[]>(
  'device-statistics',
  () => {
    return selectedFab.value === 'R3'
      ? fetchR3DeviceGrp()
      : fetchDeviceDesc([selectedFab.value])
  },
  { watch: [selectedFab] }
)

// lot_cd 별 최근 90일 측정 건수 순위 (meas_count 내림차순, fab 단위).
// 실패해도 페이지의 나머지는 살아야 하므로 카탈로그 fetch 와 분리합니다 —
// 순위가 없으면 측정 상위 필터가 빈 결과를 낼 뿐입니다.
const { data: measActivity } = await useAsyncData<MeasActivityRow[]>(
  'device-meas-activity',
  () => fetchMeasActivity(selectedFab.value),
  { watch: [selectedFab] }
)

const rows = computed(() => data.value ?? [])
const hasRSelection = computed(() => selectedFab.value === 'R3')
const hasMSelection = computed(() => selectedFab.value.startsWith('M'))
const pageSizeNumber = computed(() => Number.parseInt(pageSize.value, 10))

const uniqueSorted = (values: string[]) => {
  return Array.from(new Set(values.map(value => value.trim()).filter(Boolean)))
    .sort((left, right) => sortCollator.compare(left, right))
}

const filterOptions = (options: string[], search: string) => {
  const searchTerm = search.trim().toLowerCase()

  if (!searchTerm) {
    return options
  }

  return options.filter(option => option.toLowerCase().includes(searchTerm))
}

// Narrow `rows` for each branch. Filtering by fac_id guards against the brief
// transition window where useAsyncData still holds the previous fab's rows
// while the new fetch is in flight.
// sameFab, not `===`: fac_id arrives from the backend in whichever case its source DB uses,
// while selectedFab is the canonical uppercase DeviceFab. A raw compare empties the table.
const r3Rows = computed<R3DeviceGrpRow[]>(() => {
  if (!hasRSelection.value) return []
  return (rows.value as R3DeviceGrpRow[]).filter(row => sameFab(row.fac_id, 'R3'))
})
const mRows = computed<DeviceDescRow[]>(() => {
  if (!hasMSelection.value || !selectedFab.value) return []
  return (rows.value as DeviceDescRow[]).filter(row => sameFab(row.fac_id, selectedFab.value))
})

const prodCategoryOptions = computed(() => uniqueSorted(r3Rows.value.map(row => row.prod_catg_cd)))

const r3RowsAfterCategory = computed(() => {
  if (selectedProdCategories.value.length === 0) {
    return r3Rows.value
  }

  return r3Rows.value.filter(row => selectedProdCategories.value.includes(row.prod_catg_cd))
})

const lotOptions = computed(() => uniqueSorted(r3RowsAfterCategory.value.map(row => row.lot_cd)))
const techOptions = computed(() => uniqueSorted(mRows.value.map(row => row.tech_nm)))
const searchedLotOptions = computed(() => filterOptions(lotOptions.value, lotSearch.value))
const visibleTechOptions = computed(() => filterOptions(techOptions.value, techSearch.value))

const selectedProdCategorySet = computed(() => new Set(selectedProdCategories.value))
const selectedLotSet = computed(() => new Set(selectedLots.value))
const selectedTechSet = computed(() => new Set(selectedTechs.value))
const normalizedTableSearch = computed(() => tableSearch.value.trim().toLowerCase())

const isProdCategorySelected = (category: string) => selectedProdCategorySet.value.has(category)
const isLotSelected = (lot: string) => selectedLotSet.value.has(lot)
const isTechSelected = (tech: string) => selectedTechSet.value.has(tech)

const buildSearchText = (row: DeviceRow) => {
  return Object.values(row)
    .map(value => String(value).toLowerCase())
    .join('\u0000')
}

// 측정 상위 N 집합. 순위 목록을 현재 fab 의 카탈로그 행과 교집합한 뒤 앞에서
// N 개를 취합니다 — 순위에는 카탈로그에 없는 lot 이 있을 수 있어(office 는
// hist 에만 존재하는 lot 가능), 교집합 없이 자르면 표가 N 개보다 적게 남습니다.
const topLotSet = computed<Set<string> | null>(() => {
  const limit = selectedTopN.value
  if (limit === null) return null

  const catalogLots = new Set(
    (hasRSelection.value ? r3Rows.value : mRows.value).map(row => row.lot_cd)
  )
  const top = new Set<string>()

  for (const entry of measActivity.value ?? []) {
    if (!catalogLots.has(entry.lot_cd)) continue
    top.add(entry.lot_cd)
    if (top.size >= limit) break
  }

  return top
})

// lot_cd -> 순위 index. 측정 상위 필터가 켜졌을 때 표를 순위순으로 세우는 데
// 씁니다 — 필터만 걸고 lot_cd 순으로 두면 "상위 10" 인데 1위가 어디 있는지
// 다시 찾아야 합니다.
const measRankIndex = computed(() => {
  const map = new Map<string, number>()
  ;(measActivity.value ?? []).forEach((entry, index) => map.set(entry.lot_cd, index))
  return map
})

// lot_cd -> 측정 건수. Meas (90d) 열이 읽습니다 — 순위에 없는 lot 은
// undefined 로 남겨 "0건" 과 "순위 자료 없음" 을 구분합니다.
const measCountByLot = computed(() => {
  const map = new Map<string, number>()
  for (const entry of measActivity.value ?? []) map.set(entry.lot_cd, entry.meas_count)
  return map
})

const matchesDomainFilters = (row: DeviceRow) => {
  if (topLotSet.value && !topLotSet.value.has(row.lot_cd)) {
    return false
  }

  if (hasRSelection.value) {
    const r3Row = row as R3DeviceGrpRow
    const matchesCategory = selectedProdCategories.value.length === 0
      || selectedProdCategorySet.value.has(r3Row.prod_catg_cd)
    const matchesLot = selectedLots.value.length === 0 || selectedLotSet.value.has(r3Row.lot_cd)

    return matchesCategory && matchesLot
  }

  const mRow = row as DeviceDescRow
  return selectedTechs.value.length === 0 || selectedTechSet.value.has(mRow.tech_nm)
}

const sortedRows = computed(() => {
  const sourceRows: DeviceRow[] = hasRSelection.value ? r3Rows.value : mRows.value

  // 측정 상위 필터가 켜지면 순위순으로 — 순위 밖(순위 목록에 없는) lot 은 맨 뒤.
  if (selectedTopN.value !== null) {
    const rank = measRankIndex.value
    return [...sourceRows].sort((left, right) => {
      const leftRank = rank.get(left.lot_cd) ?? Number.MAX_SAFE_INTEGER
      const rightRank = rank.get(right.lot_cd) ?? Number.MAX_SAFE_INTEGER
      return leftRank - rightRank || sortCollator.compare(left.lot_cd, right.lot_cd)
    })
  }

  return [...sourceRows].sort((left, right) => sortCollator.compare(left.lot_cd, right.lot_cd))
})

const indexedRows = computed(() => sortedRows.value.map(row => ({
  row,
  searchText: buildSearchText(row)
})))

const filteredRows = computed(() => {
  const searchTerm = normalizedTableSearch.value

  // Skip the searchText index when there's no search term — Vue's lazy computeds mean
  // indexedRows isn't built at all unless this branch reaches it.
  if (!searchTerm) {
    return sortedRows.value.filter(matchesDomainFilters)
  }

  return indexedRows.value
    .filter(({ row, searchText }) => matchesDomainFilters(row) && searchText.includes(searchTerm))
    .map(({ row }) => row)
})

const filteredRowCount = computed(() => filteredRows.value.length)
const pageCount = computed(() => Math.max(1, Math.ceil(filteredRowCount.value / pageSizeNumber.value)))
const pageStart = computed(() => filteredRowCount.value === 0 ? 0 : ((currentPage.value - 1) * pageSizeNumber.value) + 1)
const pageEnd = computed(() => Math.min(currentPage.value * pageSizeNumber.value, filteredRowCount.value))
const pagedRows = computed(() => {
  const startIndex = (currentPage.value - 1) * pageSizeNumber.value

  return filteredRows.value.slice(startIndex, startIndex + pageSizeNumber.value)
})

const pageSizeOptions = [
  { label: '12개', value: '12' },
  { label: '25개', value: '25' },
  { label: '50개', value: '50' },
  { label: '100개', value: '100' }
]

// 행 카드가 보여 줄 배지와 메타 줄. 열 정의(r3ColumnMetadata / deviceDesc…)와
// 나란히 두는 것은 같은 필드를 두 형태로 그리기 때문입니다 — 표 보기는 열,
// 카드 보기는 배지 + 라벨 달린 값. 어느 쪽도 상대의 필드를 몰래 빠뜨리지
// 않도록 이 자리에서 함께 읽히게 했습니다.
type CardBadge = { label: string, accent?: boolean }
type CardField = { label: string, value: string }

const isR3Row = (row: DeviceRow): row is R3DeviceGrpRow => 'prod_catg_cd' in row

const cardBadges = (row: DeviceRow): CardBadge[] => {
  if (!isR3Row(row)) return [{ label: row.tech_nm, accent: true }]
  return [
    { label: row.prod_catg_cd, accent: true },
    { label: `Grade ${row.plan_grade_cd}` }
  ]
}

const cardMeta = (row: DeviceRow): CardField[] => {
  if (!isR3Row(row)) {
    return [
      { label: 'Fab', value: row.fac_id },
      { label: 'R&D Connector', value: row.rnd_connector },
      { label: 'Changed', value: row.chg_tm }
    ]
  }
  return [
    { label: 'Fab', value: row.fac_id },
    { label: 'R Tech', value: row.tech_cd },
    { label: 'Density', value: row.den_type },
    { label: 'Group', value: row.prod_grp_typ },
    { label: 'Gen', value: row.gen_typ },
    { label: 'Plan', value: row.plan_catg_type }
  ]
}

// 카드가 그릴 것을 미리 한 번만 만들어 둡니다. 두 함수를 템플릿에서 바로
// 부르면 행마다 새 배열·새 객체가 나오고, 체크박스 하나를 눌러 페이지가 다시
// 그려질 때마다 보이는 모든 행이 그 일을 되풀이합니다. computed 로 감싸면
// pagedRows 가 실제로 바뀔 때(필터·정렬·페이지 이동)만 다시 만듭니다.
const deviceCards = computed(() => pagedRows.value.map(row => ({
  row,
  badges: cardBadges(row),
  meta: cardMeta(row),
  measCount: measCountByLot.value.get(row.lot_cd)
})))

const r3ColumnMetadata = [
  { key: 'fac_id', label: 'Fab', size: 72 },
  { key: 'plan_catg_type', label: 'Plan Catg', size: 96 },
  { key: 'prod_catg_cd', label: 'Category', size: 108 },
  { key: 'tech_cd', label: 'R Tech', size: 88 },
  { key: 'den_type', label: 'Density', size: 84 },
  { key: 'prod_grp_typ', label: 'Group', size: 120 },
  { key: 'gen_typ', label: 'Gen', size: 80 },
  { key: 'lot_cd', label: 'Lot', size: 92 },
  { key: 'plan_grade_cd', label: 'Grade', size: 76 },
  { key: 'ctn_desc', label: 'Description' }
] satisfies { key: keyof R3DeviceGrpRow, label: string, size?: number }[]

const deviceDescColumnMetadata = [
  { key: 'fac_id', label: 'Fab', size: 72 },
  { key: 'lot_cd', label: 'Lot', size: 100 },
  { key: 'tech_nm', label: 'Tech', size: 88 },
  { key: 'rnd_connector', label: 'R&D Connector', size: 124 },
  { key: 'chg_tm', label: 'Changed', size: 200 },
  { key: 'ctn_desc', label: 'Description' }
] satisfies { key: keyof DeviceDescRow, label: string, size?: number }[]

const columns = computed<TableColumn<DeviceRow>[]>(() => {
  const meta = hasRSelection.value ? r3ColumnMetadata : deviceDescColumnMetadata

  const mapped: TableColumn<DeviceRow>[] = meta.map(column => ({
    accessorKey: column.key as string,
    header: column.label,
    size: column.size
  }))

  // Lot 바로 뒤에 측정 건수 열 — 측정 상위 필터가 자르는 근거 숫자를 표에서
  // 바로 보여줍니다. 행 데이터가 아니라 순위 응답에서 조인하는 파생 열이라
  // metadata 표(행 key 기반)에는 넣지 않습니다.
  const lotIndex = mapped.findIndex(
    column => (column as { accessorKey?: string }).accessorKey === 'lot_cd'
  )
  mapped.splice(lotIndex + 1, 0, {
    id: 'meas_count',
    header: 'Meas (90d)',
    size: 100,
    accessorFn: row => measCountByLot.value.get(row.lot_cd) ?? null
  })

  return [
    {
      id: 'select',
      header: '',
      size: 40,
      enableSorting: false,
      enableHiding: false
    },
    ...mapped
  ]
})

const tableMeta = {
  class: {
    tr: 'cursor-pointer select-none transition-colors hover:bg-zinc-50 dark:hover:bg-zinc-800/50',
    td: 'py-2 px-3 text-sm whitespace-nowrap overflow-hidden text-ellipsis text-(--sk-ink)',
    th: 'py-2 px-3 text-[13px] font-medium text-(--sk-ink-muted) bg-zinc-50/60 dark:bg-zinc-900/40'
  }
}

const toggleValue = (values: string[], value: string) => {
  return values.includes(value)
    ? values.filter(currentValue => currentValue !== value)
    : [...values, value]
}

const toggleProdCategory = (category: string) => {
  selectedProdCategories.value = toggleValue(selectedProdCategories.value, category)
}

const toggleLot = (lot: string) => {
  selectedLots.value = toggleValue(selectedLots.value, lot)
}

const toggleTech = (tech: string) => {
  selectedTechs.value = toggleValue(selectedTechs.value, tech)
}

// Preserve selection order so the Step 3 cart shows lots in the order the user added them.
const sortedRowMap = computed(() => {
  const map = new Map<string, DeviceRow>()

  for (const row of sortedRows.value) {
    map.set(row.lot_cd, row)
  }

  return map
})

const selectedDeviceRows = computed<DeviceRow[]>(() => {
  return selectedDeviceLots.value
    .map(lot => sortedRowMap.value.get(lot))
    .filter((row): row is DeviceRow => Boolean(row))
})

const allOnPageSelected = computed(() => {
  return pagedRows.value.length > 0
    && pagedRows.value.every(row => selectedDeviceLotSet.value.has(row.lot_cd))
})

const togglePageSelection = () => {
  const pageLots = pagedRows.value.map(row => row.lot_cd)
  if (allOnPageSelected.value) removeDeviceLots(pageLots)
  else addDeviceLots(pageLots)
}

const buildChipStrip = (
  allOptions: string[],
  visibleOptions: string[],
  selectedSet: Set<string>,
  budget: number
) => {
  const selectedFromOptions = allOptions.filter(option => selectedSet.has(option))
  const matchedUnselected = visibleOptions.filter(option => !selectedSet.has(option))
  const remainingBudget = Math.max(0, budget - selectedFromOptions.length)

  return {
    chips: [...selectedFromOptions, ...matchedUnselected.slice(0, remainingBudget)],
    overflowCount: Math.max(0, matchedUnselected.length - remainingBudget)
  }
}

const chipBudget = computed(() =>
  chipsExpanded.value ? Number.MAX_SAFE_INTEGER : STEP1_CHIP_BUDGET
)

const stepOneLotStrip = computed(() => buildChipStrip(
  lotOptions.value,
  searchedLotOptions.value,
  selectedLotSet.value,
  chipBudget.value
))

const stepOneTechStrip = computed(() => buildChipStrip(
  techOptions.value,
  visibleTechOptions.value,
  selectedTechSet.value,
  chipBudget.value
))

// R3 는 lot_cd 로, M 계열은 tech_nm 으로 디바이스를 지목합니다. 두 필터는 같은
// 자리에 배타적으로 서고 생김새도 같아서, 마크업을 한 벌만 두고 어느 필드를
// 다루는지만 갈아 끼웁니다 — 두 벌이면 한쪽에만 "전체 보기" 가 붙거나 칩 높이가
// 갈라지고, 그 차이는 두 fab 을 번갈아 보지 않는 한 아무도 알아채지 못합니다.
const identityFilter = computed(() => hasRSelection.value
  ? {
      title: 'Lot',
      fieldName: 'lot_cd',
      placeholder: text.lotSearch,
      // lot_cd 는 사람이 한 글자씩 대조하는 식별자라 mono 로 세웁니다.
      mono: true,
      total: lotOptions.value.length,
      strip: stepOneLotStrip.value,
      isSelected: isLotSelected,
      toggle: toggleLot
    }
  : {
      title: 'Tech',
      fieldName: 'tech_nm',
      placeholder: text.techSearch,
      mono: false,
      total: techOptions.value.length,
      strip: stepOneTechStrip.value,
      isSelected: isTechSelected,
      toggle: toggleTech
    })

// 검색어 자체는 fab 별로 따로 둡니다 — R3 에서 치던 lot 검색어가 M16 으로
// 넘어가 tech 검색어가 되면 안 됩니다.
const identitySearch = computed({
  get: () => hasRSelection.value ? lotSearch.value : techSearch.value,
  set: (value: string) => {
    if (hasRSelection.value) lotSearch.value = value
    else techSearch.value = value
  }
})

const proceedToStatistics = async () => {
  if (selectedDeviceLots.value.length === 0) return

  await navigateTo('/ebeam/cd-sem/device-statistics/comparison')
}

// Apply runs across multiple awaits and mutates cross-page useState (selectedDeviceLots) plus
// fires a toast — both must be skipped if the user navigates away mid-apply, otherwise we'd
// silently overwrite their cart and surface a toast for a page they've already left.
let unmounted = false
let cancelDataWait: (() => void) | null = null
onUnmounted(() => {
  unmounted = true
  cancelDataWait?.()
})

const waitForDataReady = () => {
  if (!pending.value) return Promise.resolve()
  return new Promise<void>((resolve) => {
    const stop = watch(pending, (next) => {
      if (!next) finish()
    })
    const finish = () => {
      stop()
      cancelDataWait = null
      resolve()
    }
    cancelDataWait = finish
  })
}

const toast = useToast()

// Apply a saved preset. If the preset was captured on a different fab, switch fab first and let
// the existing watchers (clear cart on fab change + prune on data ready) settle before assigning
// the preset's lots — otherwise the fab-change watcher would clear the lots we just set.
//
// Backend data may have changed since the preset was saved (lots archived, removed, or renamed),
// so we diff the preset's lots against the current sortedRows: assign only the surviving lots and
// raise a toast naming the missing ones so the user sees explicitly what didn't load.
const applyPreset = async (preset: DevicePreset) => {
  const presetFab = toDeviceFab(preset.fab)
  if (presetFab && presetFab !== selectedFab.value) {
    selectedFab.value = presetFab
    await nextTick()
    if (unmounted) return
  }
  await waitForDataReady()
  if (unmounted) return

  const validLots = new Set(sortedRows.value.map(row => row.lot_cd))
  const loaded = preset.lots.filter(lot => validLots.has(lot))
  const missing = preset.lots.filter(lot => !validLots.has(lot))
  selectedDeviceLots.value = loaded

  if (missing.length === 0) return

  const MISSING_PREVIEW_LIMIT = 5
  const previewLots = missing.slice(0, MISSING_PREVIEW_LIMIT).join(', ')
  const overflow = missing.length > MISSING_PREVIEW_LIMIT
    ? ` 외 ${missing.length - MISSING_PREVIEW_LIMIT}개`
    : ''

  toast.add({
    title: `프리셋 '${preset.name}' · ${preset.lots.length}개 중 ${loaded.length}개 로드`,
    description: `누락된 디바이스 ${missing.length}개: ${previewLots}${overflow}`,
    icon: 'i-lucide-triangle-alert',
    color: loaded.length === 0 ? 'error' : 'warning',
    duration: 8000
  })
}

const resetAllFilters = () => {
  selectedFab.value = DEFAULT_DEVICE_FAB
  selectedProdCategories.value = []
  selectedLots.value = []
  selectedTechs.value = []
  selectedTopN.value = null
  lotSearch.value = ''
  techSearch.value = ''
  tableSearch.value = ''
  currentPage.value = 1
  chipsExpanded.value = false
}

const hasActiveFilters = computed(() => {
  return selectedFab.value !== DEFAULT_DEVICE_FAB
    || selectedProdCategories.value.length > 0
    || selectedLots.value.length > 0
    || selectedTechs.value.length > 0
    || selectedTopN.value !== null
    || lotSearch.value.length > 0
    || techSearch.value.length > 0
    || tableSearch.value.length > 0
})

const activeDomainFilterCount = computed(() => {
  const topNActive = Number(selectedTopN.value !== null)

  if (hasRSelection.value) {
    return topNActive
      + Number(selectedProdCategories.value.length > 0)
      + Number(selectedLots.value.length > 0)
  }

  return topNActive + Number(selectedTechs.value.length > 0)
})

const activeFilterCount = computed(() => activeDomainFilterCount.value + (normalizedTableSearch.value ? 1 : 0))

// Fab is omitted here — the fab selector in the meta bar's toggle slot already
// surfaces the active fab, so repeating it as a stat would be redundant.
const metaStats = computed<MetaBarStat[]>(() => [
  { key: 'all', label: text.allRows, value: rows.value.length, tone: 'neutral' },
  { key: 'filtered', label: text.filteredRows, value: filteredRowCount.value, tone: 'accent' },
  { key: 'active', label: text.activeFilters, value: activeFilterCount.value, tone: 'neutral' }
])

const syncSelectionWithOptions = (selectedValues: string[], options: string[]) => {
  const optionSet = new Set(options)

  return selectedValues.filter(value => optionSet.has(value))
}

// Clear the Step 3 cart whenever the user actively switches fab — devices belong to a single
// fab in this UI, so carrying selections across fabs would be confusing. Initial-load mismatches
// are pruned by the watcher on `pending`/`sortedRows` below.
watch(selectedFab, () => {
  selectedDeviceLots.value = []
})

watch([sortedRows, pending], ([nextSortedRows, nextPending]) => {
  if (nextPending) return
  if (selectedDeviceLots.value.length === 0) return

  const validLots = new Set(nextSortedRows.map(row => row.lot_cd))

  if (validLots.size === 0) return

  const pruned = selectedDeviceLots.value.filter(lot => validLots.has(lot))

  if (pruned.length !== selectedDeviceLots.value.length) {
    selectedDeviceLots.value = pruned
  }
})

const getDeviceRowValue = (row: DeviceRow, key: string) => {
  return (row as unknown as Record<string, unknown>)[key]
}

const csvFileName = computed(() => {
  const today = new Date().toISOString().slice(0, 10)
  const fab = selectedFab.value.toLowerCase()
  return `cd-sem-${fab}-device-statistics-${today}.csv`
})

const deviceTable = () => {
  const meta = hasRSelection.value ? r3ColumnMetadata : deviceDescColumnMetadata
  // 화면과 같은 자리(Lot 뒤)에 Meas (90d)를 넣습니다. 순위에 없는 lot 은 0 이
  // 아니라 빈 칸 — 스프레드시트에서 "측정 0건" 으로 집계되면 안 됩니다.
  const lotIndex = meta.findIndex(column => column.key === 'lot_cd')
  const headers = meta.map(column => column.label)
  headers.splice(lotIndex + 1, 0, 'Meas (90d)')

  return {
    headers,
    rows: filteredRows.value.map((row) => {
      const values = meta.map(column => getDeviceRowValue(row, column.key as string))
      values.splice(lotIndex + 1, 0, measCountByLot.value.get(row.lot_cd) ?? '')
      return values
    })
  }
}

const downloadDeviceListCsv = () => {
  const { headers, rows } = deviceTable()
  downloadCsv(csvFileName.value, headers, rows)
}

const copyDeviceList = async () => {
  const { headers, rows } = deviceTable()
  const ok = await copyTableToClipboard(headers, rows)
  toast.add(
    ok
      ? { title: '클립보드에 복사됨', icon: 'i-lucide-check', color: 'success' }
      : { title: '복사에 실패했습니다', icon: 'i-lucide-x', color: 'error' }
  )
}

watch([prodCategoryOptions, lotOptions, techOptions, hasRSelection, hasMSelection], () => {
  // Skip during refetch — useAsyncData briefly holds the previous fab's data while options
  // computeds collapse to [] for the new fab, which would falsely prune (and clobber
  // localStorage) the very R3/M selections this branch is meant to preserve. The watcher
  // re-fires once data settles via the option-array changes themselves, so we don't need
  // pending in the watch list.
  if (pending.value) return

  // R3 selections are kept across fab switches so they survive a quick R3 → M → R3 round-trip.
  // Hidden in the template via v-if="hasRSelection" and ignored by matchesDomainFilters on M,
  // so leaving them populated is harmless. Only prune against the live R3 option set on R3.
  if (hasRSelection.value) {
    const nextCategories = syncSelectionWithOptions(selectedProdCategories.value, prodCategoryOptions.value)
    const nextLots = syncSelectionWithOptions(selectedLots.value, lotOptions.value)

    if (nextCategories.length !== selectedProdCategories.value.length) {
      selectedProdCategories.value = nextCategories
    }

    if (nextLots.length !== selectedLots.value.length) {
      selectedLots.value = nextLots
    }
  }

  // Same reasoning as R3 above — keep techs across fab switches; only prune on an M-fab.
  if (hasMSelection.value) {
    const nextTechs = syncSelectionWithOptions(selectedTechs.value, techOptions.value)

    if (nextTechs.length !== selectedTechs.value.length) {
      selectedTechs.value = nextTechs
    }
  }
})

watch([filteredRowCount, pageSize], () => {
  if (currentPage.value > pageCount.value) {
    currentPage.value = pageCount.value
  }

  if (currentPage.value < 1) {
    currentPage.value = 1
  }
})

watch([selectedFab, selectedProdCategories, selectedLots, selectedTechs, selectedTopN, tableSearch], () => {
  currentPage.value = 1
})

onMounted(() => {
  setToolType('cd-sem')
  setFab(selectedFab.value)
})
</script>

<style scoped>
/* Step 1 필터 카드 — 한 그룹이 한 상자 안에 들어가야 어느 칩이 어느 필터인지
   제목만 보고 알 수 있습니다. */
.filter-card {
  padding: 12px 14px;
  border-radius: 12px;
  background: var(--sk-muted-surface);
  border: 1px solid var(--sk-border-soft);
}

.filter-card__head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 10px;
}

.filter-card__title {
  font-size: 14px;
  font-weight: 700;
  color: var(--sk-ink);
}

.font-mono-ids :deep(td) {
  font-size: 14px;
}

/* ctn_desc is always the last column in both R3 and device_desc layouts and
   is the only prose field. Mono everything else regardless of column count. */
.font-mono-ids :deep(td:not(:last-child)) {
  font-family: 'JetBrains Mono', ui-monospace, 'SF Mono', Menlo, Consolas, monospace;
}
</style>
