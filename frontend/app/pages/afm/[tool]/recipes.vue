<template>
  <div class="space-y-6">
    <EbeamMetaBar
      :eyebrow="`AFM · ${toolName}`"
      title="AFM Recipe 현황"
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
            :to="`/afm/${tool.id}/recipes`"
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
      v-else-if="board.recipes.length === 0"
      icon="i-lucide-list-tree"
      title="recipe 이름이 있는 측정이 없습니다."
      :description="board.unnamed ? `측정 ${board.unnamed}건 모두 recipe 이름이 비어 있습니다.` : '이 장비의 측정 목록이 비어 있습니다.'"
    />

    <template v-else>
      <!-- 요약: recipe 수, 그리고 목록을 좁히는 세 가지 조건. -->
      <section class="dashboard-surface rounded-(--sk-r-card)">
        <div class="grid grid-cols-4 gap-2.5 p-4">
          <div class="flex flex-col gap-0.5 rounded-(--sk-r-nav) bg-(--sk-muted-surface) px-3.5 py-3">
            <span class="sk-label">Recipe</span>
            <span class="font-mono text-xl font-semibold tracking-tight text-(--sk-ink) tabular-nums">{{ board.recipes.length }}</span>
            <span class="truncate sk-meta">측정 {{ board.measured }}건</span>
          </div>
          <button
            v-for="item in TILES"
            :key="item.key"
            type="button"
            class="flex flex-col gap-0.5 rounded-(--sk-r-nav) px-3.5 py-3 text-left transition-colors duration-200"
            :class="tile === item.key ? 'bg-(--sk-brand-soft) shadow-[inset_0_0_0_1px_var(--sk-brand)]' : 'bg-(--sk-muted-surface) hover:bg-(--sk-accent-soft)'"
            :aria-pressed="tile === item.key"
            @click="tile = tile === item.key ? null : item.key"
          >
            <span
              class="sk-label"
              :class="tile === item.key ? 'text-(--sk-brand-ink)' : ''"
            >{{ item.label }}</span>
            <span
              class="font-mono text-xl font-semibold tracking-tight tabular-nums"
              :class="tile === item.key ? 'text-(--sk-brand-ink)' : counts[item.key] ? 'text-(--sk-ink)' : 'text-(--sk-ink-muted)'"
            >{{ counts[item.key] }}</span>
            <span
              class="truncate sk-meta"
              :class="tile === item.key ? 'text-(--sk-brand-ink)' : ''"
            >{{ tile === item.key ? '다시 누르면 전체 recipe를 봅니다' : item.rule }}</span>
          </button>
        </div>
      </section>

      <div class="grid items-start gap-6 xl:grid-cols-12">
        <AfmCard
          class="min-w-0 xl:col-span-7"
          icon="i-lucide-list-tree"
          title="Recipe 목록"
          :count="shown.length"
          flush
        >
          <template #actions>
            <UInput
              v-model="query"
              icon="i-lucide-search"
              placeholder="recipe 이름"
              size="sm"
              class="w-64"
              aria-label="recipe 이름으로 좁히기"
            />
          </template>
          <div class="max-h-[44rem] overflow-auto">
            <table class="w-full border-collapse">
              <thead class="sticky top-0 z-10 bg-(--sk-surface)">
                <tr class="border-b border-(--sk-border)">
                  <th
                    v-for="column in COLUMNS"
                    :key="column.label"
                    class="px-2.5 py-2 whitespace-nowrap sk-label"
                    :class="column.num ? 'text-right' : 'text-left'"
                    :aria-sort="column.key ? ariaSort(column.key) : undefined"
                  >
                    <button
                      v-if="column.key"
                      type="button"
                      class="inline-flex items-center gap-1"
                      @click="applySort(column.key)"
                    >
                      {{ column.label }}
                      <UIcon
                        :name="sortIcon(column.key)"
                        class="size-3.5"
                        :class="sort.key === column.key ? 'text-(--sk-ink)' : ''"
                      />
                    </button>
                    <template v-else>
                      {{ column.label }}
                    </template>
                  </th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="r in shown"
                  :key="r.recipe"
                  class="cursor-pointer border-b border-(--sk-border-soft) hover:bg-(--sk-muted-surface)"
                  :class="r.recipe === picked?.recipe ? 'bg-(--sk-muted-surface) shadow-[inset_2px_0_0_var(--sk-ink)]' : ''"
                  :aria-selected="r.recipe === picked?.recipe"
                  @click="pickedName = r.recipe"
                >
                  <td class="max-w-64 px-2.5 py-2">
                    <button
                      type="button"
                      class="block max-w-full truncate text-left sk-value-num font-semibold"
                      :title="r.recipe"
                    >
                      {{ r.recipe }}
                    </button>
                  </td>
                  <td class="px-2.5 py-2 text-right sk-value-num">
                    {{ r.count }}
                  </td>
                  <td class="px-2.5 py-2 whitespace-nowrap sk-value-num">
                    {{ r.last ?? '–' }}
                    <span
                      v-if="r.last"
                      class="font-sans sk-meta"
                    >{{ daysAgoLabel(r.daysAgo) }}</span>
                  </td>
                  <td class="px-2.5 py-2 whitespace-nowrap sk-value-num">
                    {{ r.first ?? '–' }}
                  </td>
                  <td class="px-2.5 py-2 text-right sk-value-num">
                    {{ r.lots }}
                  </td>
                  <td class="px-2.5 py-2 text-right whitespace-nowrap sk-value-num">
                    {{ pointLabel(r) }}
                  </td>
                  <td class="px-2.5 py-2">
                    <span class="flex flex-wrap gap-1">
                      <UBadge
                        v-for="file in r.files"
                        :key="file.label"
                        :label="fileLabel(file, r.count)"
                        color="neutral"
                        :variant="file.count === r.count ? 'subtle' : 'outline'"
                        size="sm"
                      />
                    </span>
                  </td>
                  <td class="px-2.5 py-2">
                    <span
                      class="flex h-6 w-21 items-end gap-px"
                      role="img"
                      :aria-label="sparkTitle(r)"
                      :title="sparkTitle(r)"
                    >
                      <span
                        v-for="(n, i) in r.spark"
                        :key="i"
                        class="flex-1"
                        :class="n ? 'bg-(--sk-ink)' : 'bg-(--sk-border)'"
                        :style="{ height: n ? `${Math.max(n / peak * 100, 15)}%` : '2px' }"
                      />
                    </span>
                  </td>
                  <td
                    class="px-2.5 py-2 text-right whitespace-nowrap sk-value-num"
                    :class="r.failed ? 'font-semibold text-(--sk-warn)' : ''"
                  >
                    {{ failedLabel(r) }}
                  </td>
                </tr>
              </tbody>
            </table>
            <p
              v-if="!shown.length"
              class="px-4 py-6 text-center sk-body"
            >
              조건에 맞는 recipe가 없습니다.
            </p>
          </div>
        </AfmCard>

        <!-- 고른 recipe. -->
        <div class="min-w-0 space-y-6 xl:col-span-5">
          <AppEmptyState
            v-if="!picked"
            icon="i-lucide-list-tree"
            title="조건에 맞는 recipe가 없습니다."
          />
          <template v-else>
            <AfmCard
              icon="i-lucide-scan-search"
              :title="picked.recipe"
            >
              <div class="space-y-4">
                <p class="sk-body text-(--sk-ink)">
                  측정 {{ picked.count }}건 · Lot {{ picked.lots }}개 · {{ picked.first ? `${picked.first} ~ ${picked.last}` : '날짜가 있는 측정 없음' }}
                </p>
                <div class="space-y-1.5">
                  <p class="flex items-baseline justify-between gap-2">
                    <span class="sk-label">일별 측정 건수</span>
                    <span
                      v-if="picked.dated < picked.count"
                      class="sk-meta"
                    >날짜 없는 측정 {{ picked.count - picked.dated }}건 제외</span>
                  </p>
                  <AfmRecipesDailyChart
                    v-if="days.length"
                    :key="picked.recipe"
                    :days="days"
                    :export-name="`${toolId}-recipe-${picked.recipe}`"
                  />
                  <p
                    v-else
                    class="sk-meta"
                  >
                    날짜가 있는 측정이 없어 그리지 않았습니다.
                  </p>
                </div>
                <div
                  v-if="tips.length"
                  class="flex flex-wrap items-center gap-1.5"
                >
                  <span class="sk-label">사용한 팁</span>
                  <UBadge
                    v-for="tip in tips"
                    :key="tip.tip"
                    color="neutral"
                    variant="subtle"
                    class="font-mono"
                  >
                    {{ tip.tip }} <span class="text-(--sk-ink-muted)">{{ tip.count }}</span>
                  </UBadge>
                </div>
              </div>
            </AfmCard>

            <AfmCard
              icon="i-lucide-list"
              title="측정"
              :count="picked.count"
              flush
            >
              <template #actions>
                <span class="sk-meta">최근 측정부터 · 행을 누르면 측정 상세를 엽니다</span>
              </template>
              <div class="max-h-96 overflow-auto">
                <table class="w-full border-collapse">
                  <thead class="sticky top-0 bg-(--sk-surface)">
                    <tr class="border-b border-(--sk-border)">
                      <th
                        v-for="h in RUN_HEADERS"
                        :key="h.label"
                        class="px-2.5 py-2 whitespace-nowrap sk-label"
                        :class="h.num ? 'text-right' : 'text-left'"
                      >
                        {{ h.label }}
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr
                      v-for="row in picked.rows"
                      :key="row.filename"
                      class="cursor-pointer border-b border-(--sk-border-soft) hover:bg-(--sk-muted-surface)"
                      tabindex="0"
                      @click="open(row)"
                      @keydown.enter="open(row)"
                    >
                      <td class="px-2.5 py-1.5 whitespace-nowrap sk-value-num">
                        {{ measuredAt(row) || '–' }}
                      </td>
                      <td class="px-2.5 py-1.5 whitespace-nowrap sk-value-num">
                        {{ row.lot_id || '–' }} <span class="text-(--sk-ink-muted)">/</span> {{ row.slot_number || '–' }}
                      </td>
                      <td class="px-2.5 py-1.5 text-right sk-value-num">
                        {{ row.point_count ?? '–' }}
                      </td>
                      <td
                        v-for="(value, i) in [row.not_completed_count, row.invalid_count]"
                        :key="i"
                        class="px-2.5 py-1.5 text-right sk-value-num"
                        :class="value ? 'font-semibold text-(--sk-warn)' : ''"
                      >
                        {{ value ?? '–' }}
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </AfmCard>
          </template>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import type { AfmFileRow } from '~/composables/useAfmDetailApi'
import {
  DEFAULT_RECIPE_SORT,
  RECENT_DAYS,
  SPARK_DAYS,
  STALE_DAYS,
  dailyCounts,
  daysAgoLabel,
  failedLabel,
  fileLabel,
  filterRecipes,
  pointLabel,
  recipeBoard,
  sortRecipes,
  sparkPeak,
  sparkTotal,
  tileCounts,
  tipUsage,
  type AfmRecipeSortKey,
  type RecipeSummary,
  type RecipeTile
} from '~/utils/afmRecipes'

// `key` remounts the page per tool, so the route params are read once.
definePageMeta({
  key: route => route.path
})

const toolId = String(useRoute().params.tool ?? '')
const toolName = toolId.toUpperCase()
const { fabs } = useAfmToolData()

const { data: rows, pending, error } = useAfmDetailApi().useAfmTipRows(toolName)

// Days count back from today in the viewer's own time zone, as 측정 검색 does.
const today = todayStamp()
const board = computed(() => recipeBoard(rows.value ?? [], today))
const counts = computed(() => tileCounts(board.value.recipes))
const peak = computed(() => sparkPeak(board.value.recipes))

const subtitle = computed(() => {
  const { recipes, measured, unnamed, undated } = board.value
  return `Recipe ${recipes.length}개 · 측정 ${measured}건`
    + (unnamed ? ` · recipe 이름 없는 측정 ${unnamed}건 제외` : '')
    + (undated ? ` · 날짜 없는 측정 ${undated}건은 날짜 계산에서 제외` : '')
})

const TILES: { key: RecipeTile, label: string, rule: string }[] = [
  { key: 'recent', label: `최근 ${RECENT_DAYS}일 측정`, rule: `오늘 포함 ${RECENT_DAYS}일 안에 측정한 recipe` },
  { key: 'stale', label: `${STALE_DAYS}일 넘게 측정 없음`, rule: `마지막 측정이 ${STALE_DAYS}일보다 전인 recipe` },
  { key: 'once', label: '1회만 측정', rule: '측정이 1건뿐인 recipe' }
]

const tile = ref<RecipeTile | null>(null)
const query = ref('')
const sort = ref({ ...DEFAULT_RECIPE_SORT })

const COLUMNS: { label: string, key?: AfmRecipeSortKey, num?: boolean }[] = [
  { label: 'Recipe', key: 'recipe' },
  { label: '측정', key: 'count', num: true },
  { label: '마지막 측정', key: 'last' },
  { label: '처음 측정', key: 'first' },
  { label: 'Lot', key: 'lots', num: true },
  { label: 'Point', key: 'point', num: true },
  { label: '파일' },
  { label: `최근 ${SPARK_DAYS}일` },
  { label: '미완료', key: 'failed', num: true }
]

// A new column starts with its biggest / newest on top; names start at A.
const applySort = (key: AfmRecipeSortKey) => {
  sort.value = sort.value.key === key ? { key, desc: !sort.value.desc } : { key, desc: key !== 'recipe' }
}
const ariaSort = (key: AfmRecipeSortKey) =>
  key !== sort.value.key ? 'none' : sort.value.desc ? 'descending' : 'ascending'
const sortIcon = (key: AfmRecipeSortKey) =>
  key !== sort.value.key ? 'i-lucide-arrow-up-down' : sort.value.desc ? 'i-lucide-arrow-down' : 'i-lucide-arrow-up'

const shown = computed(() => sortRecipes(filterRecipes(board.value.recipes, query.value, tile.value), sort.value))

// The recipe on show: the one picked while it is in the list, else the first row.
const pickedName = ref<string | null>(null)
const picked = computed(() => shown.value.find(r => r.recipe === pickedName.value) ?? shown.value[0] ?? null)
const days = computed(() => picked.value ? dailyCounts(picked.value) : [])
const tips = computed(() => picked.value ? tipUsage(picked.value) : [])

const sparkTitle = (r: RecipeSummary) =>
  `최근 ${SPARK_DAYS}일 측정 ${sparkTotal(r)}건`

const RUN_HEADERS = [
  { label: '측정 시각' }, { label: 'Lot / Slot' },
  { label: 'Point', num: true }, { label: '미완료', num: true }, { label: '무효', num: true }
]

const cart = useAfmCart(toolId)
const open = (row: AfmFileRow) => {
  cart.addToHistory(toMeasurement(row))
  navigateTo(`/afm/${toolId}/${encodeURIComponent(row.filename)}`)
}
</script>
