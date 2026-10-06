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
        <UButton
          v-if="originalCount"
          size="sm"
          color="neutral"
          variant="outline"
          icon="i-lucide-file-archive"
          :to="tiffZipUrl(tool, filename)"
          external
          :label="`원본 TIFF 전체 · ${originalCount}장`"
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
          :class="isSelected(image.point)
            ? 'border-(--sk-ink) outline-1 outline-(--sk-ink)'
            : 'border-(--sk-border) hover:border-(--sk-ink-muted)'"
          :data-selected="isSelected(image.point) ? '' : undefined"
          :title="image.name"
          @click="openBrowser(image.name)"
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
        이미지를 누르면 팝업에서 원본 크기로 봅니다. 테두리가 진한 이미지가 선택 포인트입니다.
      </p>
    </template>

    <UModal
      v-model:open="browserOpen"
      title="분석 이미지"
      description="포인트별로 묶은 분석 이미지 목록입니다."
      :ui="{ content: 'h-[90vh] max-h-[1000px] w-[94vw] sm:max-w-[1720px]' }"
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
              :model-value="activeType"
              :items="tabItems"
              label="분석 이미지 종류"
              @update:model-value="switchType"
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
              label="이미지 크기"
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
            <!-- A picked image takes the whole pane at its own pixel size; the
                 pane scrolls when the image is larger. -->
            <div
              v-if="picked"
              class="relative flex min-h-0 flex-col bg-(--sk-muted-surface)"
            >
              <div class="flex flex-wrap items-center gap-x-4 gap-y-1 border-b border-(--sk-border) px-4 py-2.5">
                <UButton
                  color="neutral"
                  variant="outline"
                  icon="i-lucide-layout-grid"
                  label="목록으로 돌아가기"
                  @click="pick('')"
                />
                <p class="sk-meta">
                  <b class="font-semibold text-(--sk-ink)">← →</b> 이전 · 다음 이미지
                  <span class="mx-1.5">·</span>
                  <template
                    v-for="(type, index) in TYPES"
                    :key="type.value"
                  >
                    <b class="font-semibold text-(--sk-ink)">{{ index + 1 }}</b> {{ type.label }}
                    <span
                      v-if="index < TYPES.length - 1"
                      class="mx-1"
                    >·</span>
                  </template>
                </p>
                <span class="ml-auto whitespace-nowrap sk-value-num">{{ pickedIndex + 1 }} / {{ shown.length }}</span>
                <span class="whitespace-nowrap sk-meta">원본 크기 {{ pickedSize }} · {{ ZOOM[density] * 100 }}%</span>
              </div>
              <div class="flex min-h-0 flex-1 overflow-auto px-20 py-4">
                <img
                  :src="picked.url"
                  :alt="picked.name"
                  class="m-auto max-w-none shrink-0"
                  :style="{ zoom: ZOOM[density] }"
                  @load="onPickedLoad"
                >
              </div>
              <!-- Over the pane, not inside the scroller, so they stay put
                   while a large image scrolls. -->
              <UButton
                v-for="arrow in ARROWS"
                :key="arrow.by"
                size="xl"
                color="neutral"
                variant="outline"
                :icon="arrow.icon"
                :aria-label="arrow.label"
                class="absolute top-1/2 -translate-y-1/2 rounded-full"
                :class="arrow.side"
                @click="stepPicked(arrow.by)"
              />
            </div>
            <div
              v-else
              class="overflow-y-auto bg-(--sk-muted-surface) p-4"
            >
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
                    v-if="isSelected(group.point)"
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
                      : isSelected(image.point)
                        ? 'border-(--sk-ink-muted)'
                        : 'border-(--sk-border) hover:border-(--sk-ink-muted)'"
                    :aria-pressed="image.name === pickedName"
                    :title="image.name"
                    @click="pick(image.name)"
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
                <UButton
                  block
                  :to="imagesZipUrl(tool, filename, activeType)"
                  external
                  color="neutral"
                  variant="outline"
                  icon="i-lucide-file-archive"
                  :label="`전체 다운로드 · ${images.length}장`"
                />
                <UButton
                  v-if="picked.original_url"
                  block
                  :to="picked.original_url"
                  external
                  color="neutral"
                  variant="outline"
                  icon="i-lucide-file-down"
                  label="원본 TIFF 다운로드"
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
                  이미지를 누르면 원본 크기로 봅니다.<br>선택 포인트의 이미지는 테두리가 진하게 표시됩니다.
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

// Shared with the rail: a thumbnail of the selected point is outlined. The
// popup's 이 포인트로 보기 is what changes it from here.
const selectedPoint = defineModel<string>('selectedPoint', { required: true })

const { fetchAnalysisImages, tiffZipUrl, imagesZipUrl } = useAfmDetailApi()

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
// How many originals the zip will hold — only Result images have one.
const originalCount = computed(() => state.value.images.filter(image => image.original_url).length)
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
const images = computed(() => state.value.images.map(image => ({
  ...image,
  point: imagePoint(image.name, props.points),
  kind: image.name.replace(/\.\w+$/, '').split('_').pop() ?? image.name
})))

// '' is "no point", on an image and before the payload lands alike, so it never
// counts as the selected one.
const isSelected = (point: string) => !!point && point === selectedPoint.value

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
let carriedPoint: string | undefined
const pick = (name: string) => {
  carriedPoint = undefined
  pickedName.value = name
}

const DENSITIES = [
  { value: 's', label: '작게' },
  { value: 'm', label: '보통' },
  { value: 'l', label: '크게' }
] as const
const TILE_PX = { s: 130, m: 190, l: 280 }
// The same control sizes an open image: 보통 is its own pixel size.
const ZOOM = { s: 0.5, m: 1, l: 2 }
const density = ref<'s' | 'm' | 'l'>('m')

const openBrowser = (name = '') => {
  imageQuery.value = ''
  pick(name)
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
  for (const image of shown.value) {
    const list = byPoint.get(image.point)
    if (list) list.push(image)
    else byPoint.set(image.point, [image])
  }
  return byPoint.size < shown.value.length
    ? [...byPoint].map(([point, list]) => ({ point, images: list }))
    : [{ point: '', images: shown.value }]
})

// A pick that the search or a tab change filtered away is no longer picked.
const picked = computed(() => shown.value.find(image => image.name === pickedName.value))

const pickedSize = ref('')
const onPickedLoad = (event: Event) => {
  const { naturalWidth, naturalHeight } = event.target as HTMLImageElement
  pickedSize.value = `${naturalWidth} × ${naturalHeight}px`
}

const ARROWS = [
  { by: -1, icon: 'i-lucide-chevron-left', label: '이전 이미지', side: 'left-4' },
  { by: 1, icon: 'i-lucide-chevron-right', label: '다음 이미지', side: 'right-4' }
]

const pickedIndex = computed(() => shown.value.findIndex(image => image.name === pickedName.value))

// Wraps around; with nothing picked, → opens the first image and ← the last.
const stepPicked = (by: number) => {
  const list = shown.value
  const from = pickedIndex.value < 0 && by < 0 ? 0 : pickedIndex.value
  pick(list[(from + by + list.length) % list.length]?.name ?? '')
}

// Switching type while an image is open keeps the viewer open, on the same
// point's image where the new type has one. The point the user last chose is
// carried across types that lack it (or have no images at all), so cycling
// back lands on it again; choosing an image by hand (`pick`) resets it.
const switchType = async (type: AfmImageType) => {
  const point = carriedPoint ?? picked.value?.point
  activeType.value = type
  if (point === undefined) return
  await loadType(type)
  if (activeType.value !== type) return
  carriedPoint = point
  pickedName.value = (images.value.find(image => image.point === point) ?? images.value[0])?.name ?? ''
}

// While the popup is open: ← → step through the images, 1–4 pick the type in
// tab order. Not while typing in the search box, where both are text input.
const onPopupKey = (event: KeyboardEvent) => {
  if (event.target instanceof HTMLInputElement || event.ctrlKey || event.metaKey || event.altKey) return
  const type = TYPES[Number(event.key) - 1]
  if (type) {
    event.preventDefault()
    switchType(type.value)
  } else if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') {
    event.preventDefault()
    stepPicked(event.key === 'ArrowLeft' ? -1 : 1)
  }
}
watch(browserOpen, (open) => {
  if (open) window.addEventListener('keydown', onPopupKey, true)
  else window.removeEventListener('keydown', onPopupKey, true)
})
onBeforeUnmount(() => window.removeEventListener('keydown', onPopupKey, true))

const usePickedPoint = () => {
  if (!picked.value?.point) return
  selectedPoint.value = picked.value.point
  browserOpen.value = false
}
</script>
