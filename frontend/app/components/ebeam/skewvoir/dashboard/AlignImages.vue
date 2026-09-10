<template>
  <div>
    <UButton
      color="neutral"
      variant="subtle"
      size="xs"
      icon="i-lucide-images"
      label="Align 이미지"
      :disabled="!images.length"
      @click="open = true"
    />

    <Teleport to="body">
      <div
        v-if="open"
        class="fixed inset-0 z-40 flex items-center justify-center bg-black/60 p-6"
        role="dialog"
        aria-modal="true"
        @click="open = false"
      >
        <div
          class="dashboard-surface max-h-full w-full max-w-3xl overflow-auto rounded-(--sk-r-card) p-4"
          @click.stop
        >
          <div class="mb-3 flex items-center justify-between">
            <h3 class="sk-title">
              정렬 이미지 · Align
            </h3>
            <button
              type="button"
              class="rounded-(--sk-r-nav) p-1 text-(--sk-ink-muted) transition-colors duration-200 hover:bg-(--sk-chip-bg) hover:text-(--sk-ink)"
              aria-label="닫기"
              @click="open = false"
            >
              <UIcon
                name="i-lucide-x"
                class="h-5 w-5"
              />
            </button>
          </div>

          <div
            v-if="images.length"
            class="grid grid-cols-2 gap-3 sm:grid-cols-3"
          >
            <figure
              v-for="img in images"
              :key="img.key"
              class="space-y-1"
            >
              <!-- TIFF originals can't render in <img>; offer the download. -->
              <a
                v-if="isTiffName(img.name)"
                :href="resolveImageUrl(img.name) ?? undefined"
                :download="img.name"
                class="flex aspect-square w-full flex-col items-center justify-center gap-1 rounded-(--sk-r-chip) border border-(--sk-border) bg-(--sk-chip-bg) text-center"
              >
                <UIcon
                  name="i-lucide-file-image"
                  class="h-5 w-5 text-(--sk-ink-subtle)"
                />
                <span class="sk-meta">TIFF · 다운로드</span>
              </a>
              <img
                v-else
                :src="resolveImageUrl(img.name) ?? undefined"
                :alt="img.label"
                class="w-full cursor-zoom-in rounded-(--sk-r-chip) border border-(--sk-border) transition hover:ring-2 hover:ring-(--sk-brand)"
                @click="zoomSrc = resolveImageUrl(img.name)"
              >
              <figcaption class="sk-meta">
                {{ img.label }} · score {{ img.score }}
              </figcaption>
            </figure>
          </div>
          <p
            v-else
            class="py-8 text-center sk-body"
          >
            정렬 이미지가 없습니다.
          </p>
        </div>
      </div>
    </Teleport>

    <EbeamSkewvoirImageLightbox v-model="zoomSrc" />
  </div>
</template>

<script setup lang="ts">
import type { SkewvoirAnalysis } from '~/composables/useSkewvoirAnalysis'
import { isTiffName } from '~/utils/imageKind'

const props = defineProps<{ analysis: SkewvoirAnalysis }>()

const { imageUrl } = useMsrImageApi()

const open = ref(false)
const zoomSrc = ref<string | null>(null)

// Alignment images belong to the FOCUS MSR — same context as the gallery.
const focusCtx = useFocusImageCtx(props.analysis)

const resolveImageUrl = (name: string): string | null => {
  const ctx = focusCtx.value
  return ctx.eqp_ip ? imageUrl(ctx.eqp_ip, ctx.class_name, ctx.msr, name) : null
}

// The alignment step images (OM / SEM), labelled with method + score.
const images = computed(() => {
  const a = props.analysis.focusFile.value?.alignment
  if (!a) return []
  return Object.entries(a.image_file).map(([key, name]) => ({
    key,
    name,
    label: `ALIGN ${key} · ${a.offset[key]?.[0] ?? ''}`,
    score: a.score[key] ?? '—'
  }))
})

const onKey = (e: KeyboardEvent) => {
  if (e.key === 'Escape') open.value = false
}
watch(open, (v) => {
  if (!import.meta.client) return
  if (v) window.addEventListener('keydown', onKey)
  else window.removeEventListener('keydown', onKey)
})
onBeforeUnmount(() => {
  if (import.meta.client) window.removeEventListener('keydown', onKey)
})
</script>
