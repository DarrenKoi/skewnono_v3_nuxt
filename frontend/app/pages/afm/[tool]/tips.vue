<template>
  <div class="space-y-6">
    <EbeamMetaBar
      :eyebrow="`AFM · ${toolName}`"
      title="AFM 팁 모니터링"
      :subtitle="`팁 값이 있는 측정 ${allPoints.length}건${missing ? ` · 없는 측정 ${missing}건` : ''}`"
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
            :to="`/afm/${tool.id}/tips`"
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
      v-else-if="allPoints.length === 0"
      icon="i-lucide-pen-tool"
      title="팁 값이 있는 측정이 없습니다."
      description="이 장비의 측정 목록에 팁 열(tip_id 등)이 아직 적재되지 않았습니다."
    />

    <template v-else-if="picked && pickedCategory">
      <!-- 판정 요약 + 범위: 지금 장착된 팁, 상태별 팁 수, recipe로 좁히기. -->
      <section class="dashboard-surface rounded-(--sk-r-card)">
        <div class="grid grid-cols-2 gap-2.5 p-4 xl:grid-cols-[1.6fr_repeat(4,minmax(0,1fr))]">
          <button
            type="button"
            class="col-span-2 flex flex-col gap-1 rounded-(--sk-r-nav) px-3.5 py-3 text-left xl:col-span-1"
            :class="mountedUnit ? STATE[mountedUnit.state].surface : 'bg-(--sk-muted-surface)'"
            :disabled="!mountedUnit"
            @click="pickedTip = mounted"
          >
            <span class="sk-label">지금 장착된 팁</span>
            <span class="font-mono text-base font-semibold tracking-tight text-(--sk-ink)">{{ mounted }}</span>
            <span
              v-if="mountedUnit"
              class="flex items-center gap-1.5 sk-meta"
            >
              <UBadge
                :label="STATE[mountedUnit.state].label"
                :color="STATE[mountedUnit.state].color"
                variant="subtle"
                size="sm"
              />
              {{ verdict(mountedUnit) }} · 마지막 측정 {{ shortTime(mountedUnit.points.at(-1)!.time) }}
            </span>
            <span
              v-else
              class="sk-meta"
            >선택한 recipe로는 잰 적이 없습니다.</span>
          </button>
          <div
            v-for="state in STATE_ORDER"
            :key="state"
            class="flex flex-col gap-0.5 rounded-(--sk-r-nav) bg-(--sk-muted-surface) px-3.5 py-3"
          >
            <span class="sk-label">{{ STATE[state].label }}</span>
            <span
              class="font-mono text-xl font-semibold tracking-tight tabular-nums"
              :class="counts[state] ? STATE[state].text : 'text-(--sk-ink-muted)'"
            >{{ counts[state] }}</span>
            <span class="truncate sk-meta">{{ STATE[state].rule }}</span>
          </div>
        </div>
        <div class="flex flex-wrap items-center gap-x-5 gap-y-2 border-t border-(--sk-border) px-4 py-3">
          <div
            class="flex items-center gap-1.5"
            role="group"
            aria-label="Recipe"
          >
            <span class="sk-label">Recipe</span>
            <SkChip
              size="sm"
              label="전체"
              :count="allPoints.length"
              :active="recipe === null"
              @click="recipe = null"
            />
            <USelectMenu
              :model-value="recipe ?? undefined"
              :items="recipeOptions"
              value-key="value"
              :search-input="{ placeholder: 'recipe 검색…' }"
              :placeholder="`recipe 선택 · ${recipeItems.length}종`"
              :ui="{ content: 'w-auto min-w-(--reka-combobox-trigger-width) max-w-[min(32rem,calc(100vw-2rem))]' }"
              size="sm"
              color="neutral"
              variant="outline"
              icon="i-lucide-search"
              class="w-72"
              @update:model-value="recipe = $event"
            >
              <template #item-trailing="{ item }">
                <span class="ml-auto pl-3 font-mono text-xs tabular-nums text-(--sk-ink-muted)">{{ item.count }}</span>
              </template>
            </USelectMenu>
          </div>
          <div
            class="flex items-center gap-1.5"
            role="group"
            aria-label="상태"
          >
            <span class="sk-label">상태</span>
            <SkChip
              size="sm"
              label="전체"
              :active="!onlyIssues"
              @click="onlyIssues = false"
            />
            <SkChip
              size="sm"
              label="이상·주의만"
              :active="onlyIssues"
              @click="onlyIssues = true"
            />
          </div>
          <span class="ml-auto sk-meta">관리선 = 같은 팁 종류의 중앙값 ± 3σ (σ는 MAD 기반, MCNT의 Tip Width는 팁마다) · Mileage는 누적값이라 판정하지 않습니다 · recipe를 고르면 그 측정만으로 다시 계산합니다</span>
        </div>
      </section>

      <div class="grid items-start gap-6 xl:grid-cols-[480px_minmax(0,1fr)]">
        <!-- 팁 목록: 종류별, 종류 안에서는 나쁜 순. -->
        <AfmCard
          icon="i-lucide-pen-tool"
          title="팁"
          :count="tips.length"
          flush
        >
          <template #actions>
            <span class="sk-meta">선 = Tip Width · 띠 = 관리선 · 점 = 밖</span>
          </template>
          <p
            v-if="!listed.length"
            class="px-4 py-6 text-center sk-body"
          >
            이상·주의인 팁이 없습니다.
          </p>
          <template
            v-for="category in listed"
            :key="category.type"
          >
            <div class="flex items-baseline justify-between gap-2 border-b border-(--sk-border-soft) bg-(--sk-muted-surface) px-4 py-2">
              <span class="sk-value-num font-semibold">{{ category.type }} <span class="font-sans font-normal sk-meta">팁 {{ category.tips.length }}개</span></span>
              <span class="sk-meta">{{ widthLimits(category) }}</span>
            </div>
            <button
              v-for="unit in category.tips"
              :key="unit.tip"
              type="button"
              class="grid w-full grid-cols-[3.25rem_minmax(0,1fr)_9rem] items-center gap-3 border-b border-(--sk-border-soft) px-4 py-2.5 text-left hover:bg-(--sk-muted-surface)"
              :class="unit.tip === picked.tip ? 'bg-(--sk-muted-surface) shadow-[inset_2px_0_0_var(--sk-ink)]' : ''"
              :aria-pressed="unit.tip === picked.tip"
              @click="pickedTip = unit.tip"
            >
              <UBadge
                :label="STATE[unit.state].label"
                :color="STATE[unit.state].color"
                variant="subtle"
                class="justify-center"
              />
              <span class="flex min-w-0 flex-col gap-0.5">
                <span class="flex items-center gap-1.5">
                  <span class="truncate sk-value-num font-semibold">{{ unit.tip }}</span>
                  <UBadge
                    v-if="unit.tip === mounted"
                    label="지금 장착"
                    color="neutral"
                    variant="solid"
                    size="sm"
                  />
                </span>
                <span class="truncate sk-meta">
                  {{ shortTime(unit.points[0]!.time).slice(0, 5) }} – {{ shortTime(unit.points.at(-1)!.time).slice(0, 5) }} · 측정 {{ unit.points.length }}건 · recipe {{ unit.recipes.length }}종
                </span>
                <span
                  class="text-xs"
                  :class="unit.recentOut ? ['font-semibold', STATE[unit.state].text] : 'text-(--sk-ink-muted)'"
                >{{ verdict(unit) }}</span>
              </span>
              <AfmTipsSpark
                :values="unit.points.map(p => p.tipWidth)"
                :limits="unit.widthLimits"
              />
            </button>
          </template>
        </AfmCard>

        <!-- 고른 팁: 판정의 근거. -->
        <div class="min-w-0 space-y-6">
          <AfmCard
            icon="i-lucide-scan-search"
            :title="picked.tip"
          >
            <template #actions>
              <div class="flex flex-wrap items-center gap-2">
                <UBadge
                  :label="STATE[picked.state].label"
                  :color="STATE[picked.state].color"
                  variant="subtle"
                />
                <UBadge
                  v-if="picked.tip === mounted"
                  label="지금 장착"
                  color="neutral"
                  variant="solid"
                  size="sm"
                />
                <span class="sk-meta">ID · 카세트/포트/슬롯 · {{ shortTime(picked.points[0]!.time) }} – {{ shortTime(picked.points.at(-1)!.time) }} · 측정 {{ picked.points.length }}건</span>
              </div>
            </template>
            <div class="space-y-3.5">
              <p
                class="rounded-(--sk-r-nav) px-3 py-2.5 sk-body text-(--sk-ink)"
                :class="STATE[picked.state].surface"
              >
                <b>{{ reason.head }}</b> {{ reason.rest }}
              </p>
              <div class="flex items-start gap-1.5">
                <span class="shrink-0 py-1.5 sk-label">이 팁으로 잰 recipe</span>
                <div :class="RECIPE_ROWS">
                  <SkChip
                    v-for="r in picked.recipes"
                    :key="r.recipe"
                    size="sm"
                    :label="r.recipe"
                    :count="r.count"
                    :active="recipe === r.recipe"
                    @click="recipe = recipe === r.recipe ? null : r.recipe"
                  />
                  <span class="self-center sk-meta">누르면 그 recipe의 측정만으로 다시 판정합니다</span>
                </div>
              </div>
            </div>
          </AfmCard>

          <AfmTrendHealthStrip
            :health="tipHealth(picked.points)"
            :selected="selected"
            :export-name="`${toolId}-tip-${picked.tip}`"
            :bands="bands"
            :hint="`이 팁의 측정 ${picked.points.length}건 · 띠는 ${picked.type}의 관리선`"
            @select="selected = $event"
          />

          <AfmCard
            icon="i-lucide-list"
            title="이 팁의 측정"
            :count="picked.points.length"
            flush
          >
            <template #actions>
              <span class="sk-meta">최근 측정부터 · 관리선 밖 값은 색으로 · 행을 누르면 위 차트에서 표시합니다</span>
            </template>
            <div class="max-h-96 overflow-auto">
              <table class="w-full border-collapse">
                <thead class="sticky top-0 bg-(--sk-surface)">
                  <tr class="border-b border-(--sk-border)">
                    <th
                      v-for="h in HEADERS"
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
                    v-for="point in [...picked.points].reverse()"
                    :key="point.key"
                    class="cursor-pointer border-b border-(--sk-border-soft) hover:bg-(--sk-muted-surface)"
                    :class="point.key === selected ? 'bg-(--sk-muted-surface)' : ''"
                    :aria-selected="point.key === selected"
                    @click="selected = point.key"
                  >
                    <td class="px-2.5 py-1.5 whitespace-nowrap sk-value-num text-(--sk-ink-muted)">
                      {{ shortTime(point.time) }}
                    </td>
                    <td class="px-2.5 py-1.5 whitespace-nowrap sk-value-num">
                      {{ point.recipe }} <span class="text-(--sk-ink-muted)">· {{ point.lot }}</span>
                    </td>
                    <td
                      v-for="param in TIP_PARAMS"
                      :key="param"
                      class="px-2.5 py-1.5 text-right sk-value-num"
                      :class="outside.get(point.key)?.includes(param) ? 'font-semibold text-(--sk-brand)' : ''"
                    >
                      {{ show(param, point[param]) }}
                    </td>
                    <td
                      class="px-2.5 py-1.5 text-xs whitespace-nowrap"
                      :class="outside.has(point.key) ? 'font-semibold text-(--sk-brand)' : 'text-(--sk-ink-muted)'"
                    >
                      {{ outside.has(point.key) ? `밖 ${outside.get(point.key)!.length}항목` : '안' }}
                    </td>
                    <td class="px-2.5 py-1.5 text-right">
                      <UButton
                        size="xs"
                        color="neutral"
                        variant="ghost"
                        trailing-icon="i-lucide-arrow-right"
                        label="상세"
                        :to="`/afm/${toolId}/${encodeURIComponent(point.key)}`"
                        @click.stop
                      />
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </AfmCard>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import {
  TIP_MIN_SAMPLES,
  TIP_PARAMS,
  TIP_RECENT,
  mountedTip,
  tipCategories,
  tipHealth,
  tipPoints,
  tipRecipes,
  widthIsPerTip,
  type TipCategory,
  type TipParam,
  type TipState,
  type TipUnit
} from '~/utils/afmTips'

// `key` remounts the page per tool, so the route params are read once.
definePageMeta({
  key: route => route.path
})

const toolId = String(useRoute().params.tool ?? '')
const toolName = toolId.toUpperCase()
const { fabs } = useAfmToolData()

const { data: rows, pending, error } = useAfmDetailApi().useAfmTipRows(toolName)

const allPoints = computed(() => tipPoints(rows.value ?? []))
const missing = computed(() => (rows.value?.length ?? 0) - allPoints.value.length)
const recipeItems = computed(() => tipRecipes(allPoints.value))
const recipeOptions = computed(() => recipeItems.value.map(r => ({ label: r.recipe, value: r.recipe, count: r.count })))

// The scope everything below is judged in: one recipe's measurements, or all.
const recipe = ref<string | null>(null)
const onlyIssues = ref(false)

// A tip's own recipe chips show three rows and scroll past that.
const RECIPE_ROWS = 'flex max-h-[6.75rem] min-w-0 flex-wrap gap-1.5 overflow-y-auto'

const points = computed(() =>
  recipe.value === null ? allPoints.value : allPoints.value.filter(p => p.recipe === recipe.value))

const categories = computed(() => tipCategories(points.value))
const tips = computed(() => categories.value.flatMap(category => category.tips))
const listed = computed(() => categories.value
  .map(category => ({ ...category, tips: category.tips.filter(t => !onlyIssues.value || t.state === 'bad' || t.state === 'warn') }))
  .filter(category => category.tips.length))

// Mounted is a fact about the tool, so it does not move with the recipe scope.
const mounted = computed(() => mountedTip(allPoints.value))
const mountedUnit = computed(() => tips.value.find(t => t.tip === mounted.value) ?? null)

const STATE_ORDER: TipState[] = ['bad', 'warn', 'ok', 'hold']
const STATE: Record<TipState, { label: string, rule: string, color: 'error' | 'warning' | 'success' | 'neutral', text: string, surface: string }> = {
  bad: { label: '이상', rule: `최근 ${TIP_RECENT}건 중 2건 이상 밖`, color: 'error', text: 'text-(--sk-bad)', surface: 'bg-(--sk-bad-soft)' },
  warn: { label: '주의', rule: `최근 ${TIP_RECENT}건 중 1건 밖`, color: 'warning', text: 'text-(--sk-warn)', surface: 'bg-(--sk-warn-soft)' },
  ok: { label: '정상', rule: `최근 ${TIP_RECENT}건 모두 관리선 안`, color: 'success', text: 'text-(--sk-ok)', surface: 'bg-(--sk-ok-soft)' },
  hold: { label: '보류', rule: `종류의 측정 ${TIP_MIN_SAMPLES}건 미만`, color: 'neutral', text: 'text-(--sk-ink-muted)', surface: 'bg-(--sk-muted-surface)' }
}
const counts = computed(() =>
  Object.fromEntries(STATE_ORDER.map(state => [state, tips.value.filter(t => t.state === state).length])) as Record<TipState, number>)

const PARAM_LABEL: Record<TipParam, string> = {
  tipWidth: 'Tip Width',
  approach: 'Approach Count 평균',
  mileage: 'Mileage 평균',
  notCompleted: 'FAILED + STOPPED 포인트'
}
const HEADERS = [
  { label: '시각' }, { label: 'Recipe · Lot' },
  { label: 'Tip Width', num: true }, { label: 'Mileage', num: true }, { label: 'Approach', num: true },
  { label: 'FAILED', num: true },
  { label: '판정' }, { label: '' }
]
const show = (param: TipParam, value: number | null) =>
  value === null ? '–' : param === 'notCompleted' ? String(value) : fmt2(value)

const recentOf = (unit: TipUnit) => Math.min(TIP_RECENT, unit.points.length)
// The one-line verdict a list row and the mounted tile carry.
const verdict = (unit: TipUnit) =>
  unit.state === 'hold'
    ? `종류의 측정 ${TIP_MIN_SAMPLES}건 미만`
    : unit.recentOut ? `최근 ${recentOf(unit)}건 중 ${unit.recentOut}건 밖` : `최근 ${recentOf(unit)}건 모두 안`

const widthLimits = (category: TipCategory) => {
  if (widthIsPerTip(category.type)) return 'Tip Width 관리선은 팁마다'
  const limits = category.stats.find(stat => stat.param === 'tipWidth')?.limits
  return limits ? `Tip Width ${fmt2(limits.lcl)} – ${fmt2(limits.ucl)}` : '관리선 없음'
}

// The tip on show: the one picked, else the mounted one, else the worst.
const pickedTip = ref<string | null>(null)
const picked = computed(() =>
  tips.value.find(t => t.tip === pickedTip.value) ?? mountedUnit.value
  ?? [...tips.value].sort((a, b) => STATE_ORDER.indexOf(a.state) - STATE_ORDER.indexOf(b.state))[0]
  ?? null)
const pickedCategory = computed(() => categories.value.find(category => category.type === picked.value?.type) ?? null)

// Measurement → the values it has outside the limits, for the picked tip's type.
const outside = computed(() => new Map((pickedCategory.value?.flags ?? []).map(f => [f.point.key, f.params])))
const bands = computed(() => Object.fromEntries(
  (pickedCategory.value?.stats ?? []).flatMap(({ param, limits: typeLimits }) => {
    const limits = param === 'tipWidth' ? picked.value?.widthLimits : typeLimits
    return limits ? [[param, [limits.lcl, limits.ucl]]] : []
  })
) as Partial<Record<TipParam, [number, number]>>)

const reason = computed(() => {
  const unit = picked.value!
  if (unit.state === 'hold') {
    return { head: '판단을 보류합니다.', rest: `${unit.type} 팁의 측정이 ${TIP_MIN_SAMPLES}건 미만이라 관리선을 내지 않았습니다.` }
  }
  const earlier = unit.flagged - unit.recentOut
  const before = earlier ? ` 그 이전 측정에도 ${earlier}건이 밖에 있었습니다.` : ''
  if (!unit.recentOut) return { head: `최근 ${recentOf(unit)}건이 모두 관리선 안입니다.`, rest: before.trim() }
  return {
    head: `최근 ${recentOf(unit)}건 중 ${unit.recentOut}건이 관리선 밖입니다.`,
    rest: `벗어난 항목: ${unit.recentParams.map(param => PARAM_LABEL[param]).join(', ')}.${before}`
  }
})

// The one measurement the charts and the table highlight, by filename.
const selected = ref<string | null>(null)
</script>
