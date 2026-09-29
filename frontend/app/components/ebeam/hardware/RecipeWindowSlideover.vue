<template>
  <USlideover
    :open="!!at"
    :title="`${eqpId} · 측정 recipe`"
    :description="at ? `${at.replace('T', ' ')} 앞뒤 30분에 걸친 측정입니다.` : ''"
    :ui="{ content: 'w-[96vw] sm:max-w-[760px]' }"
    @update:open="(open: boolean) => { if (!open) emit('close') }"
  >
    <template #body>
      <div
        v-if="pending"
        class="sk-body"
      >
        측정 이력을 불러오는 중...
      </div>
      <div
        v-else-if="error"
        class="sk-body text-(--sk-bad)"
      >
        측정 이력 요청 실패: {{ error }}
      </div>
      <div
        v-else-if="!rows.length"
        class="sk-body"
      >
        이 시간대에 이 장비에서 측정한 recipe 가 없습니다.
      </div>
      <div
        v-else
        class="space-y-3"
      >
        <div class="flex flex-wrap gap-2 text-xs">
          <span class="rounded bg-(--sk-muted-surface) px-2 py-1">측정 <b>{{ summary.total }}</b>건 · recipe <b>{{ summary.recipes }}</b>종</span>
          <span
            v-for="chip in failureChips"
            :key="chip.label"
            class="rounded px-2 py-1"
            :class="chip.count ? 'bg-(--sk-bad-soft) text-(--sk-bad)' : 'bg-(--sk-muted-surface) text-(--sk-ink-muted)'"
          >{{ chip.label }} <b>{{ chip.count }}</b></span>
        </div>
        <p
          v-if="capped"
          class="sk-body text-(--sk-warn)"
        >
          측정이 너무 많아 일부만 표시합니다. 시각이 이른 순으로 잘렸습니다.
        </p>
        <p class="sk-meta">
          선택 시각에 가까운 순입니다. 불량 이미지 비율 {{ RECIPE_WINDOW_FAIL_RATIO }}% 이상, Align fail, raw data 없음(msr_check No) 인 측정을 강조합니다.
        </p>
        <div class="overflow-x-auto rounded-xl ring-1 ring-(--sk-border-soft)">
          <table class="min-w-full text-left text-xs">
            <thead class="bg-(--sk-muted-surface) text-(--sk-ink-muted)">
              <tr>
                <th class="whitespace-nowrap px-3 py-2 text-right sk-label">
                  시각 차
                </th>
                <th class="px-3 py-2 sk-label">
                  측정 시간
                </th>
                <th class="px-3 py-2 sk-label">
                  Recipe
                </th>
                <th class="px-3 py-2 sk-label">
                  Lot
                </th>
                <th class="px-3 py-2 sk-label">
                  Align
                </th>
                <th class="whitespace-nowrap px-3 py-2 text-right sk-label">
                  불량 이미지
                </th>
                <th class="px-3 py-2 sk-label">
                  Raw
                </th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="item in rows"
                :key="item.row.id || `${item.row.timestamp}:${item.row.full_name}:${item.row.lot_id}`"
                class="border-t border-(--sk-border-soft)"
                :class="item.flags.length ? 'bg-(--sk-bad-soft)/50' : ''"
              >
                <td class="whitespace-nowrap px-3 py-2 text-right sk-value-num">
                  {{ item.offsetMin > 0 ? '+' : '' }}{{ item.offsetMin }}분
                </td>
                <td class="px-3 py-2 sk-value-num whitespace-nowrap">
                  {{ clock(item.row.start_time) }}~{{ clock(item.row.end_time) }}
                </td>
                <td class="px-3 py-2">
                  <NuxtLink
                    :to="recipeLink(item.row)"
                    class="font-mono text-(--sk-ink) underline decoration-(--sk-border) underline-offset-2 hover:decoration-(--sk-ink) focus-visible:decoration-(--sk-ink)"
                  >
                    {{ item.row.full_name }}
                  </NuxtLink>
                </td>
                <td class="px-3 py-2 font-mono">
                  {{ item.row.lot_id }}
                </td>
                <td
                  class="px-3 py-2"
                  :class="item.flags.includes('align') ? 'font-bold text-(--sk-bad)' : ''"
                >
                  {{ item.row.align_fail }}
                </td>
                <td
                  class="px-3 py-2 text-right sk-value-num"
                  :class="item.flags.includes('images') ? 'font-bold text-(--sk-bad)' : ''"
                >
                  {{ item.row.fail_images }}/{{ item.row.total_images }} ({{ item.row.fail_ratio.toFixed(1) }}%)
                </td>
                <td
                  class="px-3 py-2"
                  :class="item.flags.includes('msr') ? 'font-bold text-(--sk-bad)' : ''"
                >
                  {{ item.row.msr_check === 'Yes' ? '있음' : '없음' }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>
  </USlideover>
</template>

<script setup lang="ts">
import type { MeasHistRow } from '~/composables/useMeasHistApi'
import type { HardwareToolType } from '~/composables/useHardwareApi'
import { recipeWindowRows, recipeWindowSummary, RECIPE_WINDOW_FAIL_RATIO, type RecipeWindowRow } from '~/utils/recipeWindow'
import { recipeDetailRoute } from '~/utils/recipeView'

// Which recipes ran on the tool around a hardware timestamp (user request
// 2026-09-29): an FDC/Sharpness anomaly can then be traced to a measurement
// that failed alignment or lost images at the same time.
const props = defineProps<{
  toolType: HardwareToolType
  eqpId: string
  // Offset-less KST wall clock; null closes the slideover.
  at: string | null
}>()
const emit = defineEmits<{ close: [] }>()

const { fetchMeasHistWindow } = useMeasHistApi()
const rows = ref<RecipeWindowRow[]>([])
const capped = ref(false)
const pending = ref(false)
const error = ref('')

// A click on another point while one request is still in flight must not be
// overwritten by the older answer.
let request = 0
watch(() => [props.eqpId, props.at] as const, async ([eqpId, at]) => {
  const id = ++request
  rows.value = []
  capped.value = false
  error.value = ''
  if (!at || !eqpId) return
  pending.value = true
  try {
    const response = await fetchMeasHistWindow(eqpId, at)
    if (id === request) {
      rows.value = recipeWindowRows(response.rows, response.at)
      capped.value = response.capped
    }
  } catch (err) {
    if (id === request) error.value = err instanceof Error ? err.message : String(err)
  } finally {
    if (id === request) pending.value = false
  }
}, { immediate: true })

const summary = computed(() => recipeWindowSummary(rows.value))
const failureChips = computed(() => [
  { label: 'Align fail', count: summary.value.align },
  { label: `불량 이미지 ≥${RECIPE_WINDOW_FAIL_RATIO}%`, count: summary.value.images },
  { label: 'Raw 없음', count: summary.value.msr }
])

const clock = (value: string) => value.replace('Z', '').slice(11, 16)
// The detail screens need the class-qualified name AND the measurement's fab.
const recipeLink = (row: MeasHistRow) =>
  recipeDetailRoute(props.toolType, row.fab_name, 'meas-hist', row.full_name, 'redis', row.fab_name)
</script>
