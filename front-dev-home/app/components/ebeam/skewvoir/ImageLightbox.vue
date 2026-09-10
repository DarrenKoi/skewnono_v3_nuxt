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
          <!-- 취득 조건 (the image's own .{name}/cond.txt), fetched on the
               first click only. -->
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
                :name="cond === 'pending' ? 'i-lucide-loader-circle' : 'i-lucide-info'"
                class="h-4 w-4"
                :class="{ 'animate-spin': cond === 'pending' }"
              />
            </button>
            <span
              class="mx-0.5 h-4 w-px bg-(--sk-border)"
              aria-hidden="true"
            />
          </template>
        </EbeamSkewvoirZoomableImage>

        <!-- Raw, as the gallery rail and site drawer show the same sidecar:
             cond parsing stays server-side (f9d72bbc, "파서는 하나만"). -->
        <aside
          v-if="showCond"
          class="max-h-full w-72 shrink-0 self-start overflow-auto rounded-xl bg-(--sk-surface) px-4 py-3"
          aria-label="취득 조건"
        >
          <p class="sk-title">
            취득 조건
          </p>
          <p
            v-if="cond === 'error'"
            class="mt-2 text-xs text-(--sk-ink-muted)"
          >
            취득 조건을 불러오지 못했습니다
          </p>
          <p
            v-else-if="cond && cond !== 'pending' && cond.text === null"
            class="mt-2 text-xs text-(--sk-ink-muted)"
          >
            파일 없음
          </p>
          <pre
            v-else-if="cond && cond !== 'pending'"
            class="mt-2 rounded-(--sk-r-chip) border border-(--sk-border) bg-(--sk-chip-bg) p-2 font-mono text-xs break-all whitespace-pre-wrap text-(--sk-ink-muted)"
          >{{ cond.text }}</pre>
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
const props = defineProps<{ modelValue: string | null }>()
const emit = defineEmits<{ 'update:modelValue': [value: string | null] }>()

const { fetchCond } = useMsrImageApi()

const showCond = ref(false)
// undefined = not asked yet; text null = the image has no sidecar.
const cond = ref<{ text: string | null } | 'pending' | 'error'>()

const toggleCond = async () => {
  showCond.value = !showCond.value
  const url = props.modelValue
  if (!showCond.value || !url || cond.value !== undefined) return
  cond.value = 'pending'
  let next: { text: string | null } | 'error'
  try {
    next = { text: await fetchCond(url) }
  } catch {
    next = 'error'
  }
  // The lightbox closed (or moved on) under a slow request: not ours to keep.
  if (url === props.modelValue) cond.value = next
}

const close = () => emit('update:modelValue', null)
const onKey = (e: KeyboardEvent) => {
  if (e.key === 'Escape') close()
}

// Each image is asked for on its own: a new one starts shut and unfetched.
watch(() => props.modelValue, (v) => {
  showCond.value = false
  cond.value = undefined
  if (!import.meta.client) return
  if (v) window.addEventListener('keydown', onKey)
  else window.removeEventListener('keydown', onKey)
})
onBeforeUnmount(() => {
  if (import.meta.client) window.removeEventListener('keydown', onKey)
})
</script>
