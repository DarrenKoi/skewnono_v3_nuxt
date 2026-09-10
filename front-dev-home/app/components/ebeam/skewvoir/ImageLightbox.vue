<template>
  <Teleport to="body">
    <div
      v-if="modelValue"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-6"
      role="dialog"
      aria-modal="true"
      @click="close"
    >
      <div
        class="relative flex h-full w-full max-w-5xl gap-3"
        @click.stop
      >
        <EbeamSkewvoirZoomableImage
          :key="modelValue"
          :src="modelValue"
          class="h-full min-w-0 flex-1"
        >
          <!-- 취득 조건 (the image's own .{name}/cond.txt). Fetched on the
               FIRST click only — see fetchCond for why that costs no tool
               visit — so an enlarged image that is never asked stays one
               request. -->
          <template #controls>
            <button
              type="button"
              class="rounded-(--sk-r-sidebar) p-1 transition-colors duration-200 hover:bg-(--sk-chip-bg) hover:text-(--sk-ink)"
              :class="showCond ? 'text-(--sk-ink)' : 'text-(--sk-ink-muted)'"
              :aria-pressed="showCond"
              aria-label="취득 조건"
              title="취득 조건 (cond.txt)"
              @click.stop="toggleCond"
            >
              <UIcon
                :name="condPending ? 'i-lucide-loader-circle' : 'i-lucide-info'"
                class="h-4 w-4"
                :class="condPending ? 'animate-spin' : undefined"
              />
            </button>
            <span
              class="mx-0.5 h-4 w-px bg-(--sk-border)"
              aria-hidden="true"
            />
          </template>
        </EbeamSkewvoirZoomableImage>

        <aside
          v-if="showCond"
          class="w-72 shrink-0 overflow-auto rounded-(--sk-r-chip) bg-(--sk-surface) p-2"
          aria-label="취득 조건"
        >
          <p
            v-if="condError"
            class="px-3.5 py-3 text-xs text-(--sk-ink-muted)"
          >
            취득 조건을 불러오지 못했습니다
          </p>
          <EbeamRecipeOpenSettingTable
            v-else-if="!condPending"
            title="취득 조건"
            :block="condBlock"
          />
        </aside>
      </div>
      <button
        type="button"
        class="absolute top-4 right-4 rounded-(--sk-r-nav) bg-black/50 p-2 text-white transition-colors duration-200 hover:bg-black/70"
        aria-label="닫기"
        @click="close"
      >
        <UIcon
          name="i-lucide-x"
          class="h-5 w-5"
        />
      </button>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
// A single enlarged, pan/zoomable image over a dimmed backdrop. `modelValue` is
// the image URL (null = closed); backdrop / ✕ / Esc all dismiss. The zoom bar
// carries a 취득 조건 toggle that lazily reads the image's cond.txt sidecar.
import type { SettingBlock } from '~/composables/useRecipeParamDetail'
import { parseCondText } from '~/utils/condText'

const props = defineProps<{ modelValue: string | null }>()
const emit = defineEmits<{ 'update:modelValue': [value: string | null] }>()

const { fetchCond } = useMsrImageApi()

const showCond = ref(false)
const condPending = ref(false)
const condError = ref(false)
const condBlock = ref<SettingBlock | null>(null)

const toggleCond = async () => {
  showCond.value = !showCond.value
  const url = props.modelValue
  // Already fetched for this image (a re-open of the panel), or nothing to ask.
  if (!showCond.value || !url || condBlock.value || condPending.value) return
  condPending.value = true
  condError.value = false
  try {
    const text = await fetchCond(url)
    // The image changed underneath a slow request: its result is not ours.
    if (url !== props.modelValue) return
    condBlock.value = text ? parseCondText(text) : null
  } catch {
    if (url === props.modelValue) condError.value = true
  } finally {
    if (url === props.modelValue) condPending.value = false
  }
}

const close = () => emit('update:modelValue', null)
const onKey = (e: KeyboardEvent) => {
  if (e.key === 'Escape') close()
}

// A new image (or a close) starts with the panel shut and nothing cached:
// the sidecar belongs to one image, and lazy means each one is asked for.
watch(() => props.modelValue, (v) => {
  showCond.value = false
  condPending.value = false
  condError.value = false
  condBlock.value = null
  if (!import.meta.client) return
  if (v) window.addEventListener('keydown', onKey)
  else window.removeEventListener('keydown', onKey)
})
onBeforeUnmount(() => {
  if (import.meta.client) window.removeEventListener('keydown', onKey)
})
</script>
