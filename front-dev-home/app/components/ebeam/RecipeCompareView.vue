<template>
  <div class="mx-auto w-full max-w-[1440px] space-y-4">
    <EbeamMetaBar
      :eyebrow="identity"
      title="Recipe 비교"
      subtitle="선택한 recipe들의 파라미터·측정 설정을 나란히/분포로 비교합니다."
      :stats="metaStats"
    />

    <div
      v-if="!compareAllowed"
      class="dashboard-surface rounded-2xl px-6 py-12 text-center"
    >
      <UIcon
        name="i-lucide-scale"
        class="mx-auto h-6 w-6 text-(--sk-ink-muted)"
      />
      <p
        v-if="containsFallback"
        class="mt-2 sk-body"
      >
        OpenSearch fallback Recipe는 아직 비교하기를 지원하지 않습니다.
      </p>
      <p
        v-else
        class="mt-2 sk-body"
      >
        비교하려면 recipe를 2개 이상 선택하세요.
      </p>
      <p
        v-if="containsFallback"
        class="mt-1 sk-meta"
      >
        횡전개 또는 측정 이력을 이용해주세요.
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
        :back-route="backRoute"
        :can-export="!!data && selectedParameters.length > 0"
        @remove="remove"
        @download="downloadExcel"
      />

      <div
        v-if="pending"
        class="dashboard-surface rounded-2xl px-6 py-12 text-center text-sm text-(--sk-ink-muted)"
      >
        <UIcon
          name="i-lucide-loader-circle"
          class="mx-auto h-5 w-5 animate-spin text-(--sk-ink-muted)"
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
        <p class="mt-2 sk-body text-rose-600 dark:text-rose-300">
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
              <UCheckbox
                v-model="diffOnly"
                label="차이만 보기"
                class="text-[11px] text-(--sk-ink-muted)"
              />
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

          <EbeamRecipeCompareMatrix
            v-if="viewMode === 'matrix'"
            :recipes="recipes"
            :parameter="activeParam"
            :slot-key="activeSlot"
            :diff-only="diffOnly"
            :details="cellDetails"
            :tool-slug="toolSlug"
          />
          <EbeamRecipeCompareGrouping
            v-else
            :recipes="recipes"
            :parameter="activeParam"
            :slot-key="activeSlot"
            :diff-only="diffOnly"
            :details="cellDetails"
          />
        </section>

        <div
          v-else
          class="dashboard-surface rounded-2xl px-6 py-10 text-center sk-body"
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
import type { CompareParamDetail } from '~/utils/recipeCompare'
import {
  COMPARE_SLOTS,
  GROUPING_DEFAULT_THRESHOLD,
  buildCompareWorkbook,
  buildOverlap,
  commonParameters,
  compareDetailKey,
  downloadCompareWorkbook,
  findParameter,
  imageFilenames
} from '~/utils/recipeCompare'
import { fetchParamDetailsChunked, slotsOf } from '~/composables/useRecipeParamDetail'
import { IMAGE_SLOTS, type ImageSlotKey } from '~/utils/recipeView'
import { recipeNamesForCompare } from '~/utils/recipeSelection'

const props = defineProps<{
  fab: Fab
  toolLabel: string
  toolType: RecipeSearchToolType
}>()

const { entries, selected, remove } = useRecipeSelectionSet(props.toolType, props.fab)
const { fetchCompare } = useRecipeCompareApi()

const backRoute = computed(() => `/ebeam/${props.toolType}/${props.fab.toLowerCase()}/recipe-search`)
const containsFallback = computed(() =>
  entries.value.some(entry => entry.source === 'opensearch')
)
const compareNames = computed(() => recipeNamesForCompare(entries.value))
const compareAllowed = computed(() => compareNames.value !== null)
const cacheKey = computed(() =>
  compareNames.value
    ? `recipe-compare:${props.toolType}:${props.fab || 'ALL'}:${[...compareNames.value].sort().join('|')}`
    : `recipe-compare:unsupported:${props.toolType}:${props.fab || 'ALL'}`
)

const { data, pending, error, refresh } = await useAsyncData<RecipeCompareResponse | null>(
  () => cacheKey.value,
  () => {
    const names = compareNames.value
    return names
      ? fetchCompare({
          toolType: props.toolType,
          fabName: props.fab,
          recipeNames: names
        })
      : Promise.resolve(null)
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

// On first load, default the parameter selection to common params and the view
// mode to grouping for large sets. On later dataset changes (user adds/removes a
// recipe) keep their picks — only drop parameters that no longer exist, and leave
// the view mode alone.
const initialized = ref(false)
watch(overlapRows, (rows) => {
  if (rows.length === 0) return
  const common = commonParameters(rows)

  if (!initialized.value) {
    initialized.value = true
    selectedParameters.value = common.length ? common : [rows[0]!.parameter]
    viewMode.value = recipes.value.length > GROUPING_DEFAULT_THRESHOLD ? 'grouping' : 'matrix'
    return
  }

  const available = new Set(rows.map(r => r.parameter))
  const stillValid = selectedParameters.value.filter(p => available.has(p))
  if (stillValid.length !== selectedParameters.value.length) {
    selectedParameters.value = stillValid.length
      ? stillValid
      : (common.length ? common : [rows[0]!.parameter])
  }
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

const toolSlug = computed(() => props.toolType === 'hv-sem' ? 'hvsem' : 'cdsem')

/**
 * Settings for the VISIBLE cell only — one item per recipe, one request.
 *
 * CompareMatrix and CompareGrouping both scope to a single (parameter, slot)
 * pair, so a cell needs N files rather than the N x M cross-product. As N
 * separate GETs this would trip the 20 req / 5 s per-user limit on /api/*; as
 * one POST it is one request.
 */
const cellDetails = ref<(CompareParamDetail | null)[]>([])
const detailCache = new Map<string, CompareParamDetail>()

/** The (recipe, parameter) pairs still worth asking the tool for.
 *
 * Built once and reused for both the request and the re-keying of its results,
 * so the "results come back in request order" coupling exists in one place
 * instead of being re-derived by two loops kept in step by a cursor.
 */
function missingPairs(parameters: string[]) {
  return recipes.value.flatMap(recipe =>
    parameters
      .filter(parameter =>
        findParameter(recipe, parameter)
        && !detailCache.has(compareDetailKey(recipe.recipe_id, parameter)))
      .map(parameter => ({ recipe, parameter }))
  )
}

async function fetchInto(pairs: ReturnType<typeof missingPairs>) {
  if (!pairs.length) return
  const details = await fetchParamDetailsChunked(toolSlug.value, pairs.map(
    ({ recipe, parameter }) => ({
      locator: recipe.locator,
      parameter,
      slots: slotsOf(findParameter(recipe, parameter)!.images)
    })
  ))
  pairs.forEach(({ recipe, parameter }, index) => {
    const detail = details[index]
    if (detail) detailCache.set(compareDetailKey(recipe.recipe_id, parameter), detail)
  })
}

// The cell currently being fetched; a later selection must win even if its
// response lands first.
const inFlight = ref('')

async function loadCellDetails() {
  const parameter = activeParam.value
  if (!parameter || !recipes.value.length) {
    cellDetails.value = []
    return
  }
  inFlight.value = parameter
  try {
    await fetchInto(missingPairs([parameter]))
  } catch (err) {
    console.error('param-detail fetch failed', err)
  }
  if (inFlight.value !== parameter) return
  cellDetails.value = recipes.value.map(
    r => detailCache.get(compareDetailKey(r.recipe_id, parameter)) ?? null
  )
}

watch([activeParam, recipes], () => {
  void loadCellDetails()
}, { immediate: true })

const downloadExcel = async () => {
  if (!recipes.value.length || !selectedParameters.value.length) return
  try {
    // The workbook covers EVERY selected parameter, not just the visible cell,
    // so it bulk-fetches first — only the pairs browsing has not already
    // cached, and chunked, because the server caps one request at 200 items.
    const parameters = selectedParameters.value
    await fetchInto(missingPairs(parameters))
    const workbook = buildCompareWorkbook(recipes.value, parameters, detailCache)
    const slot = COMPARE_SLOTS.find(s => s.key === activeSlot.value)
    const imageBlock = (slot && activeParam.value)
      ? {
          sheetName: slot.stage,
          parameter: activeParam.value,
          images: imageFilenames(recipes.value, activeParam.value, activeSlot.value)
        }
      : undefined
    await downloadCompareWorkbook(
      workbook,
      `recipe-compare_${props.toolType}_${props.fab}.xlsx`,
      imageBlock
    )
  } catch (err) {
    console.error('Excel export failed', err)
  }
}
</script>
