<template>
  <div class="flex h-full min-h-[640px] flex-col gap-4">
    <EbeamRecipeSwitcher
      :tool-type="toolType"
      :fab-segment="routeFabSegment"
      :owner-fab="fab"
      active-screen="open"
    />
    <EbeamRecipeDetailNav
      :tool-type="toolType"
      :fab-segment="routeFabSegment"
      :owner-fab="fab"
      :recipe-name="titleRecipeName || recipeName"
      active-screen="open"
    />

    <div
      v-if="!recipeName"
      class="dashboard-surface flex flex-1 flex-col items-center justify-center rounded-2xl px-6 py-12 text-center"
    >
      <UIcon
        name="i-lucide-circle-alert"
        class="mx-auto h-6 w-6 text-rose-500"
      />
      <p class="mt-2 sk-body">
        Recipe 이름이 없습니다.
      </p>
      <UButton
        class="mt-3"
        size="sm"
        color="neutral"
        variant="outline"
        label="Recipe 검색으로 돌아가기"
        :to="backRoute"
      />
    </div>

    <AppLoadingState
      v-else-if="pending"
      class="flex flex-1 flex-col justify-center"
      title="Recipe 내용을 불러오는 중입니다."
    />

    <div
      v-else-if="error"
      class="dashboard-surface flex flex-1 flex-col items-center justify-center rounded-2xl px-6 py-12 text-center"
    >
      <UIcon
        name="i-lucide-circle-alert"
        class="mx-auto h-6 w-6 text-rose-500"
      />
      <p class="mt-2 sk-body text-rose-600 dark:text-rose-300">
        Recipe 내용을 불러오지 못했습니다.
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

    <template v-else-if="data && selectedIdp">
      <div class="grid gap-3.5 lg:min-h-0 lg:flex-1 lg:grid-cols-[1.05fr_1.3fr]">
        <section class="dashboard-surface flex h-[520px] flex-col overflow-hidden rounded-2xl lg:h-auto">
          <EbeamRecipeOpenIdpTable
            v-model:selected-index="selectedIdpIndex"
            :rows="idpImageRows"
            :measurement-point-count="waferMpRows.length"
            :align-point-count="data.wafer_align_info.length"
            @open-align="alignOpen = true"
          />
        </section>

        <section class="dashboard-surface flex h-[640px] flex-col overflow-hidden rounded-2xl lg:h-auto">
          <div class="border-b border-zinc-200/70 px-4 pt-3 pb-3 dark:border-zinc-800/70">
            <div class="mb-3 flex flex-wrap items-center justify-between gap-2.5">
              <div class="flex flex-wrap items-baseline gap-2.5">
                <span class="sk-eyebrow text-(--sk-brand)">
                  SELECTED
                </span>
                <span class="font-mono text-[20px] font-bold tracking-tight text-zinc-900 dark:text-zinc-100">
                  {{ selectedIdp.Parameter }}
                </span>
                <EbeamRecipeOpenBoolPill :value="selectedIdp.Addressing" />
                <!-- Mother_Para 는 다른 parameter 이름이 아니라 이 parameter 자신이
                     mother 인지를 나타내는 flag 입니다. 참일 때만 표시합니다. -->
                <span
                  v-if="selectedIdp.Mother_Para"
                  class="inline-block rounded bg-(--sk-brand-soft) px-1.5 py-px font-mono text-[10px] font-bold tracking-wide text-(--sk-brand-ink)"
                >MOTHER</span>
              </div>

              <!-- 선택한 parameter 전체에 대한 동작이므로 특정 탭에 두지 않고
                   헤더에 둡니다. -->
              <div class="flex shrink-0 items-center gap-1">
                <UButton
                  size="xs"
                  color="neutral"
                  variant="outline"
                  icon="i-lucide-file-down"
                  :loading="exporting"
                  :disabled="exportDisabled"
                  label="Excel 다운로드"
                  @click="downloadExcel(false)"
                />
                <UPopover
                  v-model:open="optionsOpen"
                  :content="{ align: 'end' }"
                >
                  <UButton
                    size="xs"
                    color="neutral"
                    variant="ghost"
                    icon="i-lucide-chevron-down"
                    :disabled="exportDisabled"
                    aria-label="다운로드 옵션"
                  />
                  <template #content>
                    <div class="w-72 space-y-2 p-3">
                      <p class="sk-label">
                        이미지 포함
                      </p>
                      <p class="sk-meta">
                        측정 이미지는 항상 포함됩니다. Addressing 이미지는 장비에서 파일을 2장 더 받아오므로 필요할 때만 내려받으십시오.
                      </p>
                      <!-- An ACTION, not a remembered setting: a sticky
                           checkbox would silently change what the main button
                           does on a later visit. -->
                      <UButton
                        size="xs"
                        color="neutral"
                        variant="outline"
                        icon="i-lucide-images"
                        block
                        label="Addressing 이미지까지 포함해 다운로드"
                        @click="downloadExcel(true)"
                      />
                    </div>
                  </template>
                </UPopover>
              </div>
            </div>
            <div class="flex flex-wrap gap-1.5">
              <SkNavPill
                size="sm"
                label="이미지 + 설정"
                icon="i-lucide-eye"
                :active="activeTab === 'image'"
                @click="activeTab = 'image'"
              />
              <SkNavPill
                size="sm"
                label="AMP"
                :active="activeTab === 'amp'"
                @click="activeTab = 'amp'"
              />
              <SkNavPill
                size="sm"
                label="Sequence"
                :active="activeTab === 'sequence'"
                @click="activeTab = 'sequence'"
              />
              <SkNavPill
                size="sm"
                label="측정 위치"
                :count="mpRowsForSelected.length"
                :active="activeTab === 'mp'"
                @click="activeTab = 'mp'"
              />
            </div>
          </div>

          <div class="flex min-h-0 flex-1 flex-col overflow-hidden p-4">
            <EbeamRecipeOpenParamSettings
              v-if="activeTab === 'image'"
              :tool-slug="toolSlug"
              :locator="locator"
              :detail="paramDetail"
              :pending="paramPending"
              :error="paramError"
              @open-image="openLightbox"
            />

            <EbeamRecipeOpenAmpSettings
              v-else-if="activeTab === 'amp'"
              :detail="paramDetail"
              :pending="paramPending"
              :error="paramError"
            />

            <EbeamRecipeOpenSequenceSettings
              v-else-if="activeTab === 'sequence'"
              :detail="paramDetail"
              :pending="paramPending"
              :error="paramError"
            />

            <template v-else>
              <p class="mb-2 sk-meta">
                자주 보지 않는 정보입니다. wafer_mp_info 에서
                <b class="text-zinc-700 dark:text-zinc-200">Parameter = {{ selectedIdp.Parameter }}</b>
                으로 필터링.
              </p>
              <EbeamRecipeOpenMpTable :rows="mpRowsForSelected" />
            </template>
          </div>
        </section>
      </div>

      <EbeamRecipeOpenAlignPopup
        v-model:open="alignOpen"
        :rows="data.wafer_align_info"
        :tool-slug="toolSlug"
        :locator="locator"
      />

      <EbeamRecipeOpenImageLightbox
        v-model:open="lightboxOpen"
        :data="lightboxData"
      />
    </template>
  </div>
</template>

<script setup lang="ts">
import type { Fab } from '~/stores/navigation'
import type {
  IdpLocator,
  RecipeDetailResponse,
  RecipeSearchToolType
} from '~/composables/useRecipeSearchApi'
import { toolSlug as toBackendSlug } from '~/composables/useRecipeSearchApi'
import type { ParamDetail, ParamImage } from '~/composables/useRecipeParamDetail'
import {
  fetchParamDetails,
  paramDetailKey,
  recipeApiBase,
  recipeImageUrl,
  slotsOf
} from '~/composables/useRecipeParamDetail'
import {
  IMAGE_SLOTS,
  isRecipeDetailScreenSupported,
  readRecipeNameQuery,
  readRecipeSourceQuery
} from '~/utils/recipeView'
import {
  EXPORT_IMAGE_SLOTS,
  buildParamWorkbook,
  downloadParamWorkbook,
  paramExportFilename
} from '~/utils/recipeParamExport'
import type { LightboxData } from '~/components/ebeam/recipeOpen/ImageLightbox.vue'

const props = defineProps<{
  fab: Fab
  toolLabel: string
  toolType: RecipeSearchToolType
}>()

const route = useRoute()
const router = useRouter()
const { fetchRecipeDetail } = useRecipeSearchApi()

const recipeName = computed(() => readRecipeNameQuery(route))
const source = computed(() => readRecipeSourceQuery(route))
const isSupportedSource = computed(() => isRecipeDetailScreenSupported('open', source.value))
// The route's OWN [fab] segment, not the owner fab: a multi-fab sidebar
// selection (e.g. "r3,m16b") must survive the trip back to recipe-search even
// though this recipe's data was fetched from a single owner fab.
const routeFabSegment = computed(() => String(route.params.fab || props.fab.toLowerCase()))
const backRoute = computed(() => `/ebeam/${props.toolType}/${routeFabSegment.value}/recipe-search`)
const cacheKey = computed(() => (
  `recipe-open:${props.toolType}:${props.fab || 'ALL'}:${source.value}:${recipeName.value}`
))

watch(isSupportedSource, (supported) => {
  if (!supported) void router.replace(backRoute.value)
}, { immediate: true })

const { data, pending, error, refresh } = await useAsyncData<RecipeDetailResponse | null>(
  () => cacheKey.value,
  () => {
    if (!recipeName.value || !isSupportedSource.value) return Promise.resolve(null)
    return fetchRecipeDetail({
      toolType: props.toolType,
      fabName: props.fab,
      recipeName: recipeName.value
    })
  },
  {
    watch: [cacheKey],
    default: () => null,
    getCachedData: (key, nuxtApp) => nuxtApp.payload.data[key] ?? nuxtApp.static.data[key]
  }
)

const waferMpRows = computed(() => data.value?.wafer_mp_info ?? [])
const idpImageRows = computed(() => data.value?.idp_image_info ?? [])

const titleRecipeName = computed(() => data.value?.recipe_id ?? recipeName.value)

// No 개요 tab: every field it showed — Region, SEQ, the three flags, Meas_Counting,
// dnumber_removed — is already a column of the idp_image_info table on the left,
// with the selected row highlighted. AMP took its place.
type Tab = 'image' | 'amp' | 'sequence' | 'mp'

const selectedIdpIndex = ref(0)
const activeTab = ref<Tab>('image')
const alignOpen = ref(false)
const lightboxOpen = ref(false)
const lightboxData = ref<LightboxData | null>(null)

watch(cacheKey, () => {
  selectedIdpIndex.value = 0
  activeTab.value = 'image'
  lightboxOpen.value = false
  lightboxData.value = null
})

const selectedIdp = computed(() => idpImageRows.value[selectedIdpIndex.value] ?? null)

const mpRowsForSelected = computed(() => {
  const param = selectedIdp.value?.Parameter
  if (!param) return []
  return waferMpRows.value.filter(r => r.Parameter === param)
})

// Where this recipe's raw folder lives. An empty locator means the detail call
// has not landed yet; the settings panel simply stays pending.
const locator = computed<IdpLocator>(() => data.value?.locator ?? {
  eqp_ip: '', class_name: '', idw: '', idp: ''
})

const toolSlug = computed(() => toBackendSlug(props.toolType))

// What the selected ROW asks the raw-folder endpoint for. Two rows of one
// parameter can name different files (a row is an image definition, not a
// parameter), so the request — and everything keyed on it — belongs to the row.
const paramRequest = computed(() => {
  const row = selectedIdp.value
  if (!row) return null
  return {
    parameter: row.Parameter,
    slots: slotsOf(row as unknown as Record<string, string>)
  }
})

// A STRING identity for that request, so both the cache and the watcher below
// compare by value. A refresh() rebuilds every row object but produces the same
// key, which is what keeps it from re-reading files that cannot have changed.
const paramRequestKey = computed(() => (
  paramRequest.value
    ? `${cacheKey.value}::${paramDetailKey(paramRequest.value.parameter, paramRequest.value.slots)}`
    : ''
))

// Settings for the selected row, fetched on selection. Cached per request so
// clicking back to a row already viewed is free — the raw folder is immutable
// for a given recipe.
const paramDetail = ref<ParamDetail | null>(null)
const paramPending = ref(false)
const paramError = ref(false)
// Keyed on `paramRequestKey`: recipe + parameter + the five slots. Keyed on
// recipe + parameter alone (as it was until 2026-07-30) the second of two
// Para_13 rows hit the first one's entry and displayed IMMP0004 under the row
// that names IMMP0011 — a wrong answer with no cue. The row INDEX stays out of
// the key on purpose: it is not what identifies the files, and it would miss the
// cache whenever row order shifted after a refresh.
const paramCache = new Map<string, ParamDetail>()

// The request currently in flight. Clicking quickly through parameters starts
// overlapping FTP-backed POSTs, and without this the slower one can land last
// and show the wrong parameter's settings.
const inFlight = ref('')

async function loadParamDetail() {
  const request = paramRequest.value
  const locator = data.value?.locator
  if (!request || !locator?.eqp_ip) {
    paramDetail.value = null
    return
  }
  const key = paramRequestKey.value
  const cached = paramCache.get(key)
  if (cached) {
    paramDetail.value = cached
    paramError.value = false
    return
  }

  inFlight.value = key
  paramPending.value = true
  paramError.value = false
  try {
    // Same `request` object the key was built from, so a cache entry can never
    // be filed under settings other than the ones fetched.
    const rows = await fetchParamDetails(toolSlug.value, [{ locator, ...request }])
    const detail = rows[0] ?? null
    if (detail) paramCache.set(key, detail)
    // A later selection won; its response owns the panel.
    if (inFlight.value !== key) return
    paramDetail.value = detail
  } catch {
    if (inFlight.value !== key) return
    paramError.value = true
    paramDetail.value = null
  } finally {
    if (inFlight.value === key) {
      inFlight.value = ''
      paramPending.value = false
    }
  }
}

// Watches the request KEY, not the row object and not the parameter name. The
// name alone missed the selection entirely when the user moved between two rows
// of one parameter: no fetch ran, so the previous row's files stayed on screen.
// A string still ignores the new row objects a refresh() builds.
watch([paramRequestKey, () => data.value?.locator?.eqp_ip], () => {
  void loadParamDetail()
}, { immediate: true })

const exporting = ref(false)
const optionsOpen = ref(false)
const toast = useToast()

// One condition for BOTH halves of the control: with separate ones the menu
// stayed live while the button it belongs to was dead, offering an action that
// could not run.
const exportDisabled = computed(() => paramPending.value || !paramDetail.value)

/**
 * Export the selected row.
 *
 * 측정 이미지 is unconditional; Addressing is the caller's choice per click
 * rather than a remembered setting, so the same button always does the same
 * thing. They are two of the three pictures and the ones a reader least often
 * needs, which is why they are not the default.
 */
const downloadExcel = async (withAddressing: boolean) => {
  const row = selectedIdp.value
  optionsOpen.value = false
  if (!row || !paramDetail.value || exporting.value) return
  exporting.value = true
  try {
    const slots = [
      ...EXPORT_IMAGE_SLOTS.measure,
      ...(withAddressing ? EXPORT_IMAGE_SLOTS.addressing : [])
    ]
    const workbook = buildParamWorkbook({
      recipeId: titleRecipeName.value,
      fabName: props.fab,
      toolLabel: props.toolLabel,
      locator: locator.value,
      // The SELECTED row, not the parameter: two rows of one parameter name
      // different files, and this workbook describes the row on screen.
      idp: row,
      detail: paramDetail.value,
      slots,
      exportedAt: new Date().toISOString()
    })
    const base = recipeApiBase()
    await downloadParamWorkbook(
      workbook,
      paramExportFilename(titleRecipeName.value, row.Parameter),
      name => recipeImageUrl(base, toolSlug.value, locator.value, name)
    )
  } catch (err) {
    // Told, not just logged. The export reads files off a live tool, so it can
    // fail entirely — and with only a console line the spinner simply stops and
    // a silent no-download is indistinguishable from success.
    console.error('Excel export failed', err)
    toast.add({
      title: 'Excel 다운로드에 실패했습니다.',
      description: '장비에서 파일을 읽지 못했습니다. 잠시 후 다시 시도하십시오.',
      color: 'error',
      icon: 'i-lucide-circle-alert'
    })
  } finally {
    exporting.value = false
  }
}

const openLightbox = (image: ParamImage) => {
  lightboxData.value = {
    slot: image.slot,
    stage: image.stage,
    name: image.name,
    src: recipeImageUrl(recipeApiBase(), toolSlug.value, locator.value, image.name),
    role: IMAGE_SLOTS.find(s => s.key === image.slot)?.role ?? 'address',
    cond: image.cond
  }
  lightboxOpen.value = true
}
</script>
