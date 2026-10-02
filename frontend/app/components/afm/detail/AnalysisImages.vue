<template>
  <AfmCard
    icon="i-lucide-images"
    title="분석 이미지"
  >
    <template #actions>
      <div class="flex flex-wrap items-center gap-2.5">
        <SkNavPillGroup
          v-model="activeType"
          :items="tabItems"
          label="분석 이미지 종류"
        />
        <UButton
          v-if="images.length"
          size="sm"
          color="neutral"
          variant="outline"
          icon="i-lucide-maximize-2"
          :label="`팝업에서 보기 · ${images.length}장`"
          @click="openBrowser()"
        />
      </div>
    </template>

    <AppLoadingState
      v-if="state.pending"
      variant="inline"
      class="h-40"
      title="이미지를 불러오는 중입니다."
    />
    <p
      v-else-if="state.failed"
      class="flex h-40 items-center justify-center text-sm text-rose-600 dark:text-rose-400"
    >
      이미지를 불러오지 못했습니다.
    </p>
    <p
      v-else-if="images.length === 0"
      class="flex h-40 items-center justify-center sk-body"
    >
      이미지가 없습니다.
    </p>
    <template v-else>
      <!-- `relative` makes the strip the thumbnails' offset parent, which is
           what the scroll-to-selected below measures against. -->
      <div
        ref="stripEl"
        class="relative flex gap-4 overflow-x-auto pb-2"
      >
        <button
          v-for="image in images"
          :key="image.name"
          type="button"
          class="shrink-0 overflow-hidden rounded-(--sk-r-chip) border bg-(--sk-muted-surface) text-left transition-colors duration-200"
          :class="image.point && image.point === selectedPoint
            ? 'border-(--sk-ink) outline-1 outline-(--sk-ink)'
            : 'border-(--sk-border) hover:border-(--sk-ink-muted)'"
          :data-selected="image.point && image.point === selectedPoint ? '' : undefined"
          :aria-pressed="image.point ? image.point === selectedPoint : undefined"
          :title="image.name"
          @click="image.point ? selectedPoint = image.point : openBrowser(image.name)"
        >
          <img
            :src="image.url"
            :alt="image.name"
            class="h-[113px] w-[200px] object-cover"
            loading="lazy"
          >
          <p class="w-[200px] truncate px-2 py-1.5 sk-value-num">
            {{ image.point || image.name }}
          </p>
        </button>
      </div>
      <p class="mt-2 sk-meta">
        이미지를 누르면 그 포인트를 선택합니다. 크게 보거나 내려받으려면 <b class="font-semibold text-(--sk-ink)">팝업에서 보기</b>를 누릅니다.
      </p>
    </template>

    <UModal
      v-model:open="browserOpen"
      title="분석 이미지"
      description="포인트별로 묶은 분석 이미지 목록입니다."
      :ui="{ content: 'h-[86vh] max-h-[800px] w-[94vw] sm:max-w-[1280px]' }"
    >
      <template #content>
        <div class="flex h-full min-h-0 flex-col">
          <div class="flex flex-wrap items-center gap-3 border-b border-(--sk-border) px-4 py-3">
            <UIcon
              name="i-lucide-images"
              class="size-4 text-(--sk-ink-muted)"
            />
            <h3 class="sk-panel-title">
              분석 이미지
            </h3>
            <span class="whitespace-nowrap sk-value-num">{{ shown.length }} / {{ images.length }}장</span>
            <SkNavPillGroup
              v-model="activeType"
              :items="tabItems"
              label="분석 이미지 종류"
            />
            <UInput
              v-model="imageQuery"
              type="search"
              size="xs"
              icon="i-lucide-search"
              placeholder="포인트 · 파일명 검색"
              aria-label="포인트 · 파일명 검색"
              class="ml-auto w-60"
            />
            <SkNavPillGroup
              v-model="density"
              :items="DENSITIES"
              label="썸네일 크기"
            />
            <UButton
              color="neutral"
              variant="ghost"
              icon="i-lucide-x"
              aria-label="닫기"
              @click="browserOpen = false"
            />
          </div>

          <!-- Side by side from lg; stacked below it, where 380px would not fit. -->
          <div class="grid min-h-0 flex-1 grid-cols-1 grid-rows-[minmax(0,1fr)_auto] lg:grid-cols-[minmax(0,1fr)_380px] lg:grid-rows-1">
            <div class="overflow-y-auto bg-(--sk-muted-surface) p-4">
              <p
                v-if="!shown.length"
                class="py-16 text-center sk-body"
              >
                일치하는 이미지가 없습니다.
              </p>
              <template
                v-for="group in groups"
                :key="group.point"
              >
                <p
                  v-if="groups.length > 1"
                  class="mb-2 flex items-baseline gap-2"
                >
                  <span class="sk-value-num font-semibold">{{ group.point || '기타' }}</span>
                  <span class="sk-meta">{{ group.images.length }}장</span>
                  <span
                    v-if="group.point && group.point === selectedPoint"
                    class="sk-label"
                  >선택 포인트</span>
                </p>
                <div
                  class="mb-4 grid gap-2.5"
                  :style="{ gridTemplateColumns: `repeat(auto-fill, minmax(min(${TILE_PX[density]}px, 100%), 1fr))` }"
                >
                  <button
                    v-for="image in group.images"
                    :key="image.name"
                    type="button"
                    class="overflow-hidden rounded-(--sk-r-chip) border bg-(--sk-surface) text-left transition-colors duration-200"
                    :class="image.name === pickedName
                      ? 'border-(--sk-ink) outline-2 outline-(--sk-ink)'
                      : image.point && image.point === selectedPoint
                        ? 'border-(--sk-ink-muted)'
                        : 'border-(--sk-border) hover:border-(--sk-ink-muted)'"
                    :aria-pressed="image.name === pickedName"
                    :title="image.name"
                    @click="pickedName = image.name"
                  >
                    <img
                      :src="image.url"
                      :alt="image.name"
                      class="aspect-video w-full object-cover"
                      loading="lazy"
                    >
                    <p class="truncate px-2 py-1 sk-value-num">
                      {{ groups.length > 1 ? image.kind : image.point || image.kind }}
                    </p>
                  </button>
                </div>
              </template>
            </div>

            <div class="flex min-h-0 flex-col overflow-y-auto border-(--sk-border) max-lg:max-h-[45vh] max-lg:border-t lg:border-l">
              <div
                v-if="picked"
                class="space-y-3 p-4"
              >
                <div class="overflow-hidden rounded-(--sk-r-chip) bg-(--sk-muted-surface)">
                  <img
                    :src="picked.url"
                    :alt="picked.name"
                    class="aspect-video w-full object-contain"
                  >
                </div>
                <div>
                  <p class="sk-label">
                    포인트
                  </p>
                  <p class="font-mono text-sm font-bold text-(--sk-ink)">
                    {{ picked.point || '–' }}
                  </p>
                </div>
                <div>
                  <p class="sk-label">
                    파일명
                  </p>
                  <p class="break-all sk-value-num">
                    {{ picked.name }}
                  </p>
                </div>
                <div class="flex gap-2">
                  <UButton
                    color="neutral"
                    variant="outline"
                    icon="i-lucide-chevron-left"
                    aria-label="이전 이미지"
                    @click="stepPicked(-1)"
                  />
                  <UButton
                    color="neutral"
                    variant="outline"
                    icon="i-lucide-chevron-right"
                    aria-label="다음 이미지"
                    @click="stepPicked(1)"
                  />
                  <UButton
                    block
                    color="primary"
                    icon="i-lucide-target"
                    label="이 포인트로 보기"
                    class="flex-1"
                    :disabled="!picked.point"
                    @click="usePickedPoint"
                  />
                </div>
                <UButton
                  block
                  :to="picked.url"
                  external
                  :download="`${filename}-${activeType}-${picked.name}`"
                  color="neutral"
                  variant="outline"
                  icon="i-lucide-download"
                  label="이미지 다운로드"
                />
              </div>
              <div
                v-else
                class="flex flex-1 flex-col items-center justify-center gap-2 p-6 text-center text-(--sk-ink-muted)"
              >
                <UIcon
                  name="i-lucide-mouse-pointer-click"
                  class="size-5"
                />
                <p class="text-[13px] leading-relaxed">
                  이미지를 누르면 여기서 크게 봅니다.<br>선택 포인트의 이미지는 테두리가 진하게 표시됩니다.
                </p>
              </div>
            </div>
          </div>
        </div>
      </template>
    </UModal>
  </AfmCard>
</template>

<script setup lang="ts">
import type { AfmAnalysisImage, AfmImageType } from '~/composables/useAfmDetailApi'

const props = defineProps<{
  tool: string
  filename: string
  points: string[]
}>()

// Shared with the rail: a thumbnail of the selected point is outlined, and
// clicking a thumbnail selects its point.
const selectedPoint = defineModel<string>('selectedPoint', { required: true })

const { fetchAnalysisImages } = useAfmDetailApi()

const TYPES: { value: AfmImageType, label: string }[] = [
  { value: 'align', label: 'Align' },
  { value: 'tip', label: 'Tip' },
  { value: 'capture', label: 'Capture' },
  { value: 'tiff', label: 'Result' }
]

// One lazy request per tab, kept while the card lives so re-opening a tab is
// instant. A failed tab is not marked loaded, so re-opening it retries.
const newState = () => ({ images: [] as AfmAnalysisImage[], pending: false, loaded: false, failed: false })
const states = reactive({ align: newState(), tip: newState(), capture: newState(), tiff: newState() })

// Result opens first: it is the one type with an image per point.
const activeType = ref<AfmImageType>('tiff')
const state = computed(() => states[activeType.value])
const tabItems = computed(() =>
  TYPES.map(t => ({ ...t, count: states[t.value].images.length || undefined }))
)

const loadType = async (type: AfmImageType) => {
  const target = states[type]
  if (target.loaded || target.pending) return
  target.pending = true
  target.failed = false
  try {
    target.images = (await fetchAnalysisImages(props.tool, props.filename, type)).data ?? []
    target.loaded = true
  } catch {
    target.failed = true
  } finally {
    target.pending = false
  }
}

watch(activeType, loadType, { immediate: true })

// Each image with the point it shows and the kind its name ends in (`Height`, `tip`).
const stem = measurementStem(props.filename)
const images = computed(() => state.value.images.map(image => ({
  ...image,
  point: imagePoint(image.name, stem, props.points),
  kind: image.name.replace(/\.\w+$/, '').split('_').pop() ?? image.name
})))

// Keep the selected point's thumbnail in view without scrollIntoView, which
// would also scroll the page down to the strip.
const stripEl = ref<HTMLDivElement | null>(null)
watch([selectedPoint, images], async () => {
  await nextTick()
  const thumb = stripEl.value?.querySelector<HTMLElement>('[data-selected]')
  if (thumb) stripEl.value?.scrollTo({ left: thumb.offsetLeft - 16 })
})

// The popup: every image of the tab in a grid, grouped by point.
const browserOpen = ref(false)
const imageQuery = ref('')
const pickedName = ref('')

const DENSITIES = [
  { value: 's', label: '작게' },
  { value: 'm', label: '보통' },
  { value: 'l', label: '크게' }
] as const
const TILE_PX = { s: 130, m: 190, l: 280 }
const density = ref<'s' | 'm' | 'l'>('m')

const openBrowser = (name = '') => {
  imageQuery.value = ''
  pickedName.value = name
  browserOpen.value = true
}

const shown = computed(() => {
  const q = imageQuery.value.trim().toLowerCase()
  return q ? images.value.filter(image => image.name.toLowerCase().includes(q)) : images.value
})

// Grouped by point only where a point has several images. With one image per
// point a heading over every tile would turn the grid into a single column, so
// the tiles run together and each is labelled with its point instead.
const groups = computed(() => {
  const byPoint = new Map<string, typeof shown.value>()
  for (const image of shown.value) byPoint.set(image.point, [...(byPoint.get(image.point) ?? []), image])
  return byPoint.size < shown.value.length
    ? [...byPoint].map(([point, list]) => ({ point, images: list }))
    : [{ point: '', images: shown.value }]
})

// A pick that the search or a tab change filtered away is no longer picked.
const picked = computed(() => shown.value.find(image => image.name === pickedName.value))

const stepPicked = (by: number) => {
  const list = shown.value
  const index = list.findIndex(image => image.name === pickedName.value)
  pickedName.value = list[(index + by + list.length) % list.length]?.name ?? ''
}

const usePickedPoint = () => {
  if (!picked.value?.point) return
  selectedPoint.value = picked.value.point
  browserOpen.value = false
}
</script>
