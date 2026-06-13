<template>
  <div class="mx-auto w-full max-w-[1440px] space-y-4">
    <EbeamMetaBar
      :eyebrow="identity"
      title="Recipe 비교"
      subtitle="선택한 recipe들의 파라미터·측정 설정을 나란히/분포로 비교합니다."
      :stats="metaStats"
    />

    <div
      v-if="selected.length < 2"
      class="dashboard-surface rounded-2xl px-6 py-12 text-center"
    >
      <UIcon
        name="i-lucide-scale"
        class="mx-auto h-6 w-6 text-zinc-400"
      />
      <p class="mt-2 text-sm font-medium text-zinc-700 dark:text-zinc-200">
        비교하려면 recipe를 2개 이상 선택하세요.
      </p>
      <UButton
        class="mt-3"
        size="sm"
        color="neutral"
        variant="outline"
        label="Recipe 검색으로"
        :to="backRoute"
      />
    </div>

    <template v-else>
      <EbeamRecipeCompareRecipeSetBar
        :selected="selected"
        :tool-type="toolType"
        :fab="fab"
        :can-export="!!data && selectedParameters.length > 0"
        @remove="remove"
        @add="add"
        @download="downloadExcel"
      />

      <div
        v-if="pending"
        class="dashboard-surface rounded-2xl px-6 py-12 text-center text-sm text-(--sk-ink-muted)"
      >
        <UIcon
          name="i-lucide-loader-circle"
          class="mx-auto h-5 w-5 animate-spin text-zinc-400"
        />
        <p class="mt-2">
          비교 데이터를 불러오는 중입니다.
        </p>
      </div>

      <div
        v-else-if="error"
        class="dashboard-surface rounded-2xl px-6 py-12 text-center"
      >
        <UIcon
          name="i-lucide-circle-alert"
          class="mx-auto h-6 w-6 text-rose-500"
        />
        <p class="mt-2 text-sm font-medium text-rose-600 dark:text-rose-300">
          비교 데이터를 불러오지 못했습니다.
        </p>
        <UButton
          class="mt-3"
          size="sm"
          color="neutral"
          variant="outline"
          icon="i-lucide-refresh-cw"
          label="Retry"
          @click="refresh()"
        />
      </div>

      <template v-else-if="recipes.length">
        <EbeamRecipeCompareParameterSelector
          v-model="selectedParameters"
          :rows="overlapRows"
          :recipe-ids="recipeIds"
        />

        <section
          v-if="selectedParameters.length"
          class="dashboard-surface rounded-2xl p-4"
        >
          <div class="mb-3 flex flex-wrap items-center gap-2">
            <div class="flex flex-wrap gap-1">
              <SkNavPill
                v-for="param in selectedParameters"
                :key="param"
                size="sm"
                :label="param"
                :active="activeParam === param"
                @click="activeParam = param"
              />
            </div>
            <div class="ml-auto flex items-center gap-2">
              <label class="flex items-center gap-1.5 text-[11px] text-(--sk-ink-muted)">
                <UCheckbox v-model="diffOnly" /> 차이만 보기
              </label>
              <div class="flex rounded-lg bg-zinc-100 p-0.5 dark:bg-zinc-800">
                <button
                  type="button"
                  class="rounded-md px-3 py-1 text-[11px] font-semibold transition"
                  :class="viewMode === 'matrix' ? 'bg-white shadow-sm dark:bg-zinc-950' : 'text-(--sk-ink-muted)'"
                  @click="viewMode = 'matrix'"
                >
                  나란히
                </button>
                <button
                  type="button"
                  class="rounded-md px-3 py-1 text-[11px] font-semibold transition"
                  :class="viewMode === 'grouping' ? 'bg-white shadow-sm dark:bg-zinc-950' : 'text-(--sk-ink-muted)'"
                  @click="viewMode = 'grouping'"
                >
                  분포
                </button>
              </div>
            </div>
          </div>

          <div class="mb-3 flex flex-wrap gap-1.5">
            <SkNavPill
              v-for="s in IMAGE_SLOTS"
              :key="s.key"
              size="sm"
              :label="s.stage"
              :active="activeSlot === s.key"
              @click="activeSlot = s.key"
            />
          </div>

          <EbeamRecipeCompareCompareMatrix
            v-if="viewMode === 'matrix'"
            :recipes="recipes"
            :parameter="activeParam"
            :slot-key="activeSlot"
            :diff-only="diffOnly"
          />
          <EbeamRecipeCompareCompareGrouping
            v-else
            :recipes="recipes"
            :parameter="activeParam"
            :slot-key="activeSlot"
            :diff-only="diffOnly"
          />
        </section>

        <div
          v-else
          class="dashboard-surface rounded-2xl px-6 py-10 text-center text-sm text-(--sk-ink-muted)"
        >
          비교할 파라미터를 선택하세요. (공통 전체 선택을 눌러보세요.)
        </div>
      </template>
    </template>
  </div>
</template>

<script setup lang="ts">
import type { Fab } from '~/stores/navigation'
import type { RecipeSearchToolType } from '~/composables/useRecipeSearchApi'
import type { RecipeCompareResponse } from '~/composables/useRecipeCompareApi'
import type { MetaBarStat } from '~/components/ebeam/MetaBar.vue'
import {
  GROUPING_DEFAULT_THRESHOLD,
  buildCompareWorkbook,
  buildOverlap,
  commonParameters,
  downloadCompareWorkbook
} from '~/utils/recipeCompare'
import { IMAGE_SLOTS, type ImageSlotKey } from '~/utils/recipeView'

const props = defineProps<{
  fab: Fab
  toolLabel: string
  toolType: RecipeSearchToolType
}>()

const { selected, add, remove } = useRecipeSelectionSet(props.toolType, props.fab)
const { fetchCompare } = useRecipeCompareApi()

const backRoute = computed(() => `/ebeam/${props.toolType}/${props.fab.toLowerCase()}/recipe-search`)
const cacheKey = computed(() => `recipe-compare:${props.toolType}:${props.fab || 'ALL'}:${[...selected.value].sort().join('|')}`)

const { data, pending, error, refresh } = await useAsyncData<RecipeCompareResponse | null>(
  () => cacheKey.value,
  () => {
    if (selected.value.length < 2) return Promise.resolve(null)
    return fetchCompare({ toolType: props.toolType, fabName: props.fab, recipeNames: selected.value })
  },
  {
    watch: [cacheKey],
    default: () => null,
    getCachedData: (key, nuxtApp) => nuxtApp.payload.data[key] ?? nuxtApp.static.data[key]
  }
)

const recipes = computed(() => data.value?.recipes ?? [])
const recipeIds = computed(() => recipes.value.map(r => r.recipe_id))
const overlapRows = computed(() => buildOverlap(recipes.value))

const selectedParameters = ref<string[]>([])
const activeParam = ref('')
const activeSlot = ref<ImageSlotKey>('img_meas1')
const diffOnly = ref(false)
const viewMode = ref<'matrix' | 'grouping'>('matrix')

// When a new dataset loads, default the parameter selection to common params and
// the view mode to grouping for large sets.
watch(overlapRows, (rows) => {
  if (rows.length === 0) return
  const common = commonParameters(rows)
  selectedParameters.value = common.length ? common : [rows[0]!.parameter]
  viewMode.value = recipes.value.length > GROUPING_DEFAULT_THRESHOLD ? 'grouping' : 'matrix'
}, { immediate: true })

// Keep activeParam valid as the selection changes.
watch(selectedParameters, (params) => {
  if (!params.includes(activeParam.value)) {
    activeParam.value = params[0] ?? ''
  }
}, { immediate: true })

const identity = computed(() => `${props.toolLabel} · ${props.fab || '—'}`)
const metaStats = computed<MetaBarStat[]>(() => [
  { key: 'recipes', label: 'Recipes', value: selected.value.length.toLocaleString(), tone: 'accent' },
  { key: 'params', label: 'Params', value: selectedParameters.value.length.toLocaleString(), tone: 'neutral' }
])

const downloadExcel = () => {
  if (!recipes.value.length || !selectedParameters.value.length) return
  const workbook = buildCompareWorkbook(recipes.value, selectedParameters.value)
  downloadCompareWorkbook(workbook, `recipe-compare_${props.toolType}_${props.fab}.xlsx`)
}
</script>
