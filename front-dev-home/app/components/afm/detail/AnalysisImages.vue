<template>
  <UCard
    class="dashboard-surface rounded-2xl"
    :ui="{ body: 'p-4 sm:p-5', header: 'px-4 sm:px-5 py-3' }"
  >
    <template #header>
      <div class="flex items-center gap-2">
        <UIcon
          name="i-lucide-images"
          class="h-4 w-4 text-(--sk-ink-muted)"
        />
        <h2 class="sk-title">
          Analysis images
        </h2>
      </div>
    </template>

    <UTabs
      v-model="activeType"
      :items="tabItems"
      class="w-full"
    >
      <template #content="{ item }">
        <div
          v-if="stateFor(item.value).pending"
          class="flex h-56 items-center justify-center sk-body"
        >
          <UIcon
            name="i-lucide-loader-circle"
            class="mr-2 h-4 w-4 animate-spin"
          />
          Loading images…
        </div>
        <div
          v-else-if="stateFor(item.value).images.length === 0"
          class="flex h-56 flex-col items-center justify-center text-center sk-body"
        >
          <UIcon
            name="i-lucide-image-off"
            class="mb-2 h-8 w-8 text-(--sk-ink-muted)"
          />
          No {{ item.label }} images available
        </div>
        <div
          v-else
          class="flex gap-4 overflow-x-auto pb-2"
        >
          <button
            v-for="image in stateFor(item.value).images"
            :key="image.name"
            type="button"
            class="group shrink-0 overflow-hidden rounded-xl border border-zinc-200 bg-zinc-50 text-left transition hover:shadow-md dark:border-zinc-800 dark:bg-zinc-900"
            @click="openLightbox(image)"
          >
            <img
              :src="image.url"
              :alt="image.name"
              class="h-40 w-56 object-cover"
              loading="lazy"
            >
            <p class="w-56 truncate px-2 py-1.5 text-xs sk-body">
              {{ image.name }}
            </p>
          </button>
        </div>
      </template>
    </UTabs>

    <UModal
      v-model:open="lightboxOpen"
      :ui="{ content: 'w-[92vw] sm:max-w-[900px]', body: 'p-0' }"
    >
      <template #content>
        <div
          v-if="selectedImage"
          class="p-4"
        >
          <div class="mb-3 flex items-center justify-between gap-3">
            <p class="truncate sk-title">
              {{ selectedImage.name }}
            </p>
            <div class="flex items-center gap-2">
              <UButton
                size="xs"
                color="neutral"
                variant="ghost"
                icon="i-lucide-download"
                aria-label="Download image"
                @click="downloadImage(selectedImage)"
              />
              <UButton
                size="xs"
                color="neutral"
                variant="ghost"
                icon="i-lucide-x"
                aria-label="Close"
                @click="lightboxOpen = false"
              />
            </div>
          </div>
          <div class="flex max-h-[78vh] items-center justify-center overflow-hidden rounded-xl bg-zinc-50 dark:bg-zinc-900">
            <img
              :src="selectedImage.url"
              :alt="selectedImage.name"
              class="max-h-[78vh] max-w-full object-contain"
            >
          </div>
        </div>
      </template>
    </UModal>
  </UCard>
</template>

<script setup lang="ts">
import type { TabsItem } from '@nuxt/ui'
import type { AfmAnalysisImage, AfmImageType } from '~/composables/useAfmDetailApi'

const props = defineProps<{
  tool: string
  filename: string
}>()

const { fetchAnalysisImages } = useAfmDetailApi()

interface TabState {
  images: AfmAnalysisImage[]
  pending: boolean
  loaded: boolean
}

const TYPES: { value: AfmImageType, label: string, icon: string }[] = [
  { value: 'align', label: 'Align', icon: 'i-lucide-crosshair' },
  { value: 'tip', label: 'Tip', icon: 'i-lucide-pen-tool' },
  { value: 'capture', label: 'Capture', icon: 'i-lucide-camera' },
  { value: 'tiff', label: 'Result', icon: 'i-lucide-scan' }
]

const states = reactive<Record<AfmImageType, TabState>>({
  align: { images: [], pending: false, loaded: false },
  tip: { images: [], pending: false, loaded: false },
  capture: { images: [], pending: false, loaded: false },
  tiff: { images: [], pending: false, loaded: false }
})

const activeType = ref<AfmImageType>('align')

const stateFor = (type: string | number | undefined) => states[type as AfmImageType]

const tabItems = computed<TabsItem[]>(() =>
  TYPES.map(t => ({
    label: t.label,
    icon: t.icon,
    value: t.value,
    badge: states[t.value].loaded && states[t.value].images.length > 0
      ? states[t.value].images.length
      : undefined
  }))
)

const loadType = async (type: AfmImageType) => {
  const state = states[type]
  if (state.loaded || state.pending || !props.filename) return
  state.pending = true
  try {
    const res = await fetchAnalysisImages(props.tool, props.filename, type)
    state.images = res.data ?? []
  } catch {
    state.images = []
  } finally {
    state.loaded = true
    state.pending = false
  }
}

watch(activeType, type => loadType(type), { immediate: true })

const lightboxOpen = ref(false)
const selectedImage = ref<AfmAnalysisImage | null>(null)

const openLightbox = (image: AfmAnalysisImage) => {
  selectedImage.value = image
  lightboxOpen.value = true
}

const downloadImage = async (image: AfmAnalysisImage) => {
  if (!import.meta.client) return
  try {
    const res = await fetch(image.url)
    const blob = await res.blob()
    const objectUrl = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = objectUrl
    const safeName = image.name.replace(/[^a-zA-Z0-9._-]+/g, '_')
    link.download = `${props.filename}-${activeType.value}-${safeName}`
    link.click()
    URL.revokeObjectURL(objectUrl)
  } catch {
    // best-effort download
  }
}
</script>
