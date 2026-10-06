<template>
  <div class="space-y-6">
    <EbeamMetaBar
      :eyebrow="`AFM · ${toolName}`"
      title="AFM 팁 모니터링"
      :subtitle="`팁 값이 있는 측정 ${points.length}건${missing ? ` · 없는 측정 ${missing}건` : ''}`"
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
      v-else-if="points.length === 0"
      icon="i-lucide-pen-tool"
      title="팁 값이 있는 측정이 없습니다."
      description="이 장비의 측정 목록에 팁 열(tip_id 등)이 아직 적재되지 않았습니다."
    />

    <template
      v-for="(category, index) in categories"
      v-else
      :key="category.type"
    >
      <AfmTrendSection
        :num="String(index + 1).padStart(2, '0')"
        :title="category.type"
        :hint="`측정 ${category.points.length}건 · 팁 ${category.tips.length}개 · 관리선 밖 ${category.flags.length}건 — 같은 종류(Tip ID)의 측정끼리 비교합니다.`"
      />

      <div class="grid gap-6 xl:grid-cols-2">
        <AfmCard
          icon="i-lucide-ruler"
          title="항목별 분포"
          flush
        >
          <template #actions>
            <span class="sk-meta">관리선 = μ ± 3σ (σ는 MAD 기반) · 측정 {{ TIP_MIN_SAMPLES }}건 미만이면 내지 않습니다</span>
          </template>
          <div class="overflow-x-auto">
            <table class="w-full border-collapse">
              <thead>
                <tr class="border-b border-(--sk-border)">
                  <th
                    v-for="(label, i) in ['항목', 'n', 'μ', 'σ', '하한', '상한', '밖']"
                    :key="label"
                    class="px-2.5 py-2 whitespace-nowrap sk-label"
                    :class="i ? 'text-right' : 'text-left'"
                  >
                    {{ label }}
                  </th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="stat in category.stats"
                  :key="stat.param"
                  class="border-b border-(--sk-border-soft)"
                >
                  <td class="px-2.5 py-1.5 whitespace-nowrap text-xs text-(--sk-ink)">
                    {{ PARAM_LABEL[stat.param] }}
                  </td>
                  <td class="px-2.5 py-1.5 text-right sk-value-num">
                    {{ stat.n }}
                  </td>
                  <td
                    v-for="(cell, i) in [stat.limits?.mu, stat.limits?.sigma, stat.limits?.lcl, stat.limits?.ucl]"
                    :key="i"
                    class="px-2.5 py-1.5 text-right sk-value-num"
                  >
                    {{ fmt2(cell) }}
                  </td>
                  <td
                    class="px-2.5 py-1.5 text-right sk-value-num"
                    :class="stat.outliers ? 'font-semibold text-(--sk-brand)' : 'text-(--sk-ink-muted)'"
                  >
                    {{ stat.outliers }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </AfmCard>

        <AfmCard
          icon="i-lucide-pen-tool"
          title="팁"
          :count="category.tips.length"
          flush
        >
          <template #actions>
            <span class="sk-meta">ID · 카세트/포트/슬롯 · 최근에 쓴 팁부터</span>
          </template>
          <div class="overflow-x-auto">
            <table class="w-full border-collapse">
              <thead>
                <tr class="border-b border-(--sk-border)">
                  <th
                    v-for="(label, i) in ['팁', '측정', '첫 측정', '마지막 측정', '마지막 Tip Width', '밖']"
                    :key="label"
                    class="px-2.5 py-2 whitespace-nowrap sk-label"
                    :class="i ? 'text-right' : 'text-left'"
                  >
                    {{ label }}
                  </th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="unit in category.tips"
                  :key="unit.tip"
                  class="border-b border-(--sk-border-soft)"
                >
                  <td class="px-2.5 py-1.5 whitespace-nowrap sk-value-num">
                    {{ unit.tip }}
                  </td>
                  <td class="px-2.5 py-1.5 text-right sk-value-num">
                    {{ unit.count }}
                  </td>
                  <td class="px-2.5 py-1.5 text-right whitespace-nowrap sk-value-num text-(--sk-ink-muted)">
                    {{ shortTime(unit.first) }}
                  </td>
                  <td class="px-2.5 py-1.5 text-right whitespace-nowrap sk-value-num text-(--sk-ink-muted)">
                    {{ shortTime(unit.last) }}
                  </td>
                  <td class="px-2.5 py-1.5 text-right sk-value-num">
                    {{ fmt2(unit.lastWidth) }}
                  </td>
                  <td
                    class="px-2.5 py-1.5 text-right sk-value-num"
                    :class="unit.flagged ? 'font-semibold text-(--sk-brand)' : 'text-(--sk-ink-muted)'"
                  >
                    {{ unit.flagged }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </AfmCard>
      </div>

      <AfmCard
        v-if="category.flags.length"
        icon="i-lucide-triangle-alert"
        title="관리선 밖 측정"
        :count="category.flags.length"
        flush
      >
        <template #actions>
          <span class="sk-meta">행을 누르면 아래 차트에서 그 측정을 표시합니다 · 최근 측정부터</span>
        </template>
        <div class="overflow-x-auto">
          <table class="w-full border-collapse">
            <thead>
              <tr class="border-b border-(--sk-border)">
                <th
                  v-for="label in ['시각', '팁', 'Recipe · Lot', '벗어난 항목', '']"
                  :key="label"
                  class="px-2.5 py-2 text-left whitespace-nowrap sk-label"
                >
                  {{ label }}
                </th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="flag in category.flags"
                :key="flag.point.key"
                class="cursor-pointer border-b border-(--sk-border-soft) hover:bg-(--sk-muted-surface)"
                :class="flag.point.key === selected ? 'bg-(--sk-muted-surface)' : ''"
                :aria-selected="flag.point.key === selected"
                @click="selected = flag.point.key"
              >
                <td class="px-2.5 py-1.5 whitespace-nowrap sk-value-num text-(--sk-ink-muted)">
                  {{ shortTime(flag.point.time) }}
                </td>
                <td class="px-2.5 py-1.5 whitespace-nowrap sk-value-num">
                  {{ flag.point.tip }}
                </td>
                <td class="px-2.5 py-1.5 whitespace-nowrap sk-value-num">
                  {{ flag.point.recipe }} <span class="text-(--sk-ink-muted)">· {{ flag.point.lot }}</span>
                </td>
                <td class="px-2.5 py-1.5 text-xs text-(--sk-brand)">
                  {{ flag.params.map(param => `${PARAM_LABEL[param]} ${fmt2(flag.point[param])}`).join(' · ') }}
                </td>
                <td class="px-2.5 py-1.5 text-right">
                  <UButton
                    size="xs"
                    color="neutral"
                    variant="ghost"
                    trailing-icon="i-lucide-arrow-right"
                    label="상세"
                    :to="`/afm/${toolId}/${encodeURIComponent(flag.point.key)}`"
                    @click.stop
                  />
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </AfmCard>

      <AfmTrendHealthStrip
        :health="tipHealth(category.points)"
        :selected="selected"
        :export-name="`${toolId}-tips-${category.type}`"
        :hint="`${category.type} 팁으로 잰 이 장비의 모든 측정 · 세로선은 팁(ID·카세트·포트·슬롯)이 바뀐 시점`"
        @select="selected = $event"
      />
    </template>
  </div>
</template>

<script setup lang="ts">
import { TIP_MIN_SAMPLES, tipCategories, tipHealth, tipPoints, type TipParam } from '~/utils/afmTips'

// `key` remounts the page per tool, so the route params are read once.
definePageMeta({
  key: route => route.path
})

const toolId = String(useRoute().params.tool ?? '')
const toolName = toolId.toUpperCase()
const { fabs } = useAfmToolData()

const { data: rows, pending, error } = useAfmDetailApi().useAfmTipRows(toolName)

const points = computed(() => tipPoints(rows.value ?? []))
const missing = computed(() => (rows.value?.length ?? 0) - points.value.length)
const categories = computed(() => tipCategories(points.value))

// The one measurement every chart highlights, by filename.
const selected = ref<string | null>(null)

const PARAM_LABEL: Record<TipParam, string> = {
  tipWidth: 'Tip Width',
  approach: 'Approach Count 평균',
  mileage: 'Mileage 평균',
  notCompleted: 'FAILED + STOPPED 포인트',
  invalid: 'Valid = FALSE 포인트'
}
</script>
