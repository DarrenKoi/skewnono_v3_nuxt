<template>
  <AfmCard
    icon="i-lucide-images"
    title="분석 이미지"
  >
    <template #actions>
      <SkNavPillGroup
        v-model="activeType"
        :items="tabItems"
        label="분석 이미지 종류"
      />
    </template>

    <AppLoadingState
      v-if="state.pending"
      variant="inline"
      class="h-56"
      title="이미지를 불러오는 중입니다."
    />
    <p
      v-else-if="state.failed"
      class="flex h-56 items-center justify-center text-sm text-rose-600 dark:text-rose-400"
    >
      이미지를 불러오지 못했습니다.
    </p>
    <p
      v-else-if="state.images.length === 0"
      class="flex h-56 items-center justify-center sk-body"
    >
      이미지가 없습니다.
    </p>
    <div
      v-else
      class="flex gap-4 overflow-x-auto pb-2"
    >
      <button
        v-for="image in state.images"
        :key="image.name"
        type="button"
        class="shrink-0 overflow-hidden rounded-(--sk-r-chip) border border-(--sk-border) bg-(--sk-muted-surface) text-left transition-colors duration-200 hover:border-(--sk-ink-muted)"
        @click="selectedImage = image"
      >
        <img
          :src="image.url"
          :alt="image.name"
          class="h-40 w-56 object-cover"
          loading="lazy"
        >
        <p class="w-56 truncate px-2 py-1.5 sk-value">
          {{ image.name }}
        </p>
      </button>
    </div>

    <UModal
      :open="selectedImage !== null"
      :title="selectedImage?.name"
      :ui="{ content: 'w-[92vw] sm:max-w-[900px]', footer: 'justify-end' }"
      @update:open="selectedImage = null"
    >
      <template #body>
        <img
          v-if="selectedImage"
          :src="selectedImage.url"
          :alt="selectedImage.name"
          class="mx-auto max-h-[70vh] max-w-full object-contain"
        >
      </template>
      <template #footer>
        <UButton
          v-if="selectedImage"
          :to="selectedImage.url"
          external
          :download="`${filename}-${activeType}-${selectedImage.name}`"
          color="neutral"
          variant="outline"
          icon="i-lucide-download"
          label="이미지 다운로드"
        />
      </template>
    </UModal>
  </AfmCard>
</template>

<script setup lang="ts">
import type { AfmAnalysisImage, AfmImageType } from '~/composables/useAfmDetailApi'

const props = defineProps<{
  tool: string
  filename: string
}>()

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

const activeType = ref<AfmImageType>('align')
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

const selectedImage = ref<AfmAnalysisImage | null>(null)
</script>
