<template>
  <USlideover
    :open="!!selectedRecipe"
    :title="selectedRecipe ?? ''"
    :description="`${toolLabel} · ${fabs.join(' + ')} · Recipe 사용 이력`"
    :ui="{ content: 'w-[96vw] sm:max-w-[860px]', title: 'font-mono break-all' }"
    @update:open="(open: boolean) => { if (!open) selectRecipe(null) }"
  >
    <template #body>
      <p
        v-if="error"
        class="sk-body text-(--sk-bad)"
      >
        Recipe 사용 이력을 불러오지 못했습니다.
      </p>
      <p
        v-else-if="!detail"
        class="sk-body"
      >
        Recipe 사용 이력을 불러오는 중입니다.
      </p>
      <p
        v-else-if="!detail.tools.length && !detail.daily.length"
        class="sk-body"
      >
        선택한 fab의 장비에서 이 recipe를 찾을 수 없습니다.
      </p>
      <div
        v-else
        class="space-y-5"
      >
        <section class="space-y-2">
          <div class="flex flex-wrap items-center gap-2">
            <h3 class="sk-title">
              장비별 사용
            </h3>
            <span class="sk-count-chip">{{ detail.tools.length.toLocaleString() }}대</span>
            <span class="sk-meta">누적 사용 {{ totalUses.toLocaleString() }}회 (전체 기간)</span>
          </div>
          <div class="overflow-x-auto rounded-(--sk-r-chip) ring-1 ring-(--sk-border-soft)">
            <table class="min-w-full text-left">
              <thead class="bg-(--sk-muted-surface)">
                <tr>
                  <th class="px-3 py-2 sk-label">
                    eqp_id
                  </th>
                  <th class="px-3 py-2 sk-label">
                    Fab
                  </th>
                  <th class="px-3 py-2 text-right sk-label">
                    누적 사용
                  </th>
                  <th class="px-3 py-2 sk-label">
                    최초 사용
                  </th>
                  <th class="px-3 py-2 sk-label">
                    최근 사용
                  </th>
                  <th class="px-3 py-2 sk-label">
                    장비 상주
                  </th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="tool in detail.tools"
                  :key="tool.eqp_id"
                  class="border-t border-(--sk-border-soft)"
                >
                  <td class="px-3 py-1.5 sk-value-num">
                    {{ tool.eqp_id }}
                  </td>
                  <td class="px-3 py-1.5 sk-value">
                    {{ tool.fab_name }}
                  </td>
                  <td class="px-3 py-1.5 text-right sk-value-num">
                    {{ tool.n_uses.toLocaleString() }}
                  </td>
                  <td class="whitespace-nowrap px-3 py-1.5 sk-value-num">
                    {{ tool.first_used ?? '—' }}
                  </td>
                  <td class="whitespace-nowrap px-3 py-1.5 sk-value-num">
                    {{ tool.last_used ?? '—' }}
                  </td>
                  <td class="px-3 py-1.5 sk-value">
                    {{ tool.on_tool ? '있음' : '없음' }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        <section class="space-y-2">
          <div class="flex flex-wrap items-center gap-2">
            <h3 class="sk-title">
              일별 추이
            </h3>
            <span
              v-if="detail.daily.length"
              class="sk-meta"
            >
              {{ detail.daily[0]?.date }} ~ {{ detail.daily.at(-1)?.date }}
              · 작업 {{ windowTotals.runs.toLocaleString() }}회
              · Fail {{ windowTotals.fail_runs.toLocaleString() }}회
              · 측정 {{ formatSecondsAsDuration(windowTotals.meas_min * 60) }}
            </span>
          </div>
          <EbeamRecipeUsageDailyChart
            v-if="detail.daily.length"
            :points="detail.daily"
            export-name="recipe-usage-daily"
            class="h-[300px]"
          />
          <p
            v-else
            class="sk-body"
          >
            적재된 기간에는 이 recipe의 작업이 없습니다.
          </p>
          <p class="sk-meta leading-relaxed">
            일별 추이는 현재 적재된 기간의 작업만 포함하며, 작업이 없는 날은 표시되지 않습니다.
            누적 사용 횟수는 전체 기간 기준이므로 추이의 합계와 다를 수 있습니다.
          </p>
        </section>
      </div>
    </template>
  </USlideover>
</template>

<script setup lang="ts">
import { formatSecondsAsDuration } from '~/composables/useRecipeTatApi'
import type { RecipeUsageToolType } from '~/composables/useRecipeUsageApi'

// The recipe drawer shared by Recipe 검색 and Recipe 현황. It opens for
// whatever `?recipe=` names, so a host only has to call selectRecipe().
const props = defineProps<{
  fabs: string[]
  toolLabel: string
  toolType: RecipeUsageToolType
}>()

const { selectedRecipe, selectRecipe } = useRecipeUsageSelection()
const { fetchRecipeUsageDetail } = useRecipeUsageApi()

const cacheKey = computed(
  () => `recipe-usage-detail:${props.toolType}:${props.fabs.join(',') || 'ALL'}:${selectedRecipe.value ?? ''}`
)

const { data, error } = useAsyncData(
  () => cacheKey.value,
  async () => selectedRecipe.value
    ? await fetchRecipeUsageDetail(props.toolType, props.fabs, selectedRecipe.value)
    : null,
  { watch: [cacheKey], lazy: true }
)

// The previous recipe's response must not show under the next one's title.
const detail = computed(() =>
  data.value && data.value.recipe_id === selectedRecipe.value ? data.value : null)

const totalUses = computed(() =>
  (detail.value?.tools ?? []).reduce((sum, tool) => sum + tool.n_uses, 0))

const windowTotals = computed(() =>
  (detail.value?.daily ?? []).reduce(
    (sum, point) => ({
      runs: sum.runs + point.runs,
      fail_runs: sum.fail_runs + point.fail_runs,
      meas_min: sum.meas_min + point.meas_min
    }),
    { runs: 0, fail_runs: 0, meas_min: 0 }
  ))
</script>
