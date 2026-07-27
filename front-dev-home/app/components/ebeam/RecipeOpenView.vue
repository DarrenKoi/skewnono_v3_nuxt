<template>
  <div class="flex h-full min-h-[640px] flex-col gap-4">
    <EbeamRecipeSwitcher
      :tool-type="toolType"
      :fab="fab"
      active-screen="open"
    />
    <EbeamRecipeDetailNav
      :tool-type="toolType"
      :fab="fab"
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

    <div
      v-else-if="pending"
      class="dashboard-surface flex flex-1 flex-col items-center justify-center rounded-2xl px-6 py-12 text-center text-sm text-(--sk-ink-muted)"
    >
      <UIcon
        name="i-lucide-loader-circle"
        class="mx-auto h-5 w-5 animate-spin text-(--sk-ink-muted)"
      />
      <p class="mt-2">
        Recipe 내용을 불러오는 중입니다.
      </p>
    </div>

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
            <div class="mb-3 flex flex-wrap items-baseline gap-2.5">
              <span class="sk-eyebrow text-(--sk-brand)">
                SELECTED
              </span>
              <span class="font-mono text-[20px] font-bold tracking-tight text-zinc-900 dark:text-zinc-100">
                {{ selectedIdp.Parameter }}
              </span>
              <EbeamRecipeOpenYesNoPill :value="selectedIdp.Addressing" />
              <span
                v-if="selectedIdp.Mother_Para && selectedIdp.Mother_Para !== '—'"
                class="font-mono text-[11px] text-(--sk-ink-muted)"
              >
                ← {{ selectedIdp.Mother_Para }}
              </span>
            </div>
            <div class="flex flex-wrap gap-1.5">
              <SkNavPill
                size="sm"
                label="이미지 + AMP"
                icon="i-lucide-eye"
                :count="IMAGE_SLOTS.length"
                :active="activeTab === 'image'"
                @click="activeTab = 'image'"
              />
              <SkNavPill
                size="sm"
                label="개요"
                :active="activeTab === 'overview'"
                @click="activeTab = 'overview'"
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
            <EbeamRecipeOpenImageAmpMatrix
              v-if="activeTab === 'image'"
              :row="selectedIdp"
              :amp-rows="ampRowsForSelected"
              @open-image="openLightbox"
            />

            <EbeamRecipeOpenOverviewKV
              v-else-if="activeTab === 'overview'"
              :row="selectedIdp"
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
        :images="data.align_images"
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
  AmpRow,
  RecipeDetailResponse,
  RecipeSearchToolType
} from '~/composables/useRecipeSearchApi'
import {
  IMAGE_SLOTS,
  isRecipeDetailScreenSupported,
  type ImageSlotKey,
  readRecipeNameQuery,
  readRecipeSourceQuery
} from '~/utils/recipeView'
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
const backRoute = computed(() => `/ebeam/${props.toolType}/${props.fab.toLowerCase()}/recipe-search`)
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
const ampInfo = computed<AmpRow[]>(() => data.value?.amp_info ?? [])

const titleRecipeName = computed(() => data.value?.recipe_id ?? recipeName.value)

type Tab = 'image' | 'overview' | 'mp'

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

const ampRowsForSelected = computed(() => {
  const param = selectedIdp.value?.Parameter
  if (!param) return []
  return ampInfo.value.filter(a => a.parameter === param)
})

const openLightbox = (slotKey: ImageSlotKey) => {
  if (!selectedIdp.value) return
  const slot = IMAGE_SLOTS.find(s => s.key === slotKey)
  if (!slot) return
  lightboxData.value = {
    slot,
    filename: selectedIdp.value[slot.key],
    ampRow: ampRowsForSelected.value.find(a => a.slot === slot.key) ?? null
  }
  lightboxOpen.value = true
}
</script>
