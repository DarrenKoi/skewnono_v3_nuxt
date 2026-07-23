<template>
  <div class="flex min-h-0 flex-col">
    <EbeamSkewvoirPanelFrame
      class="min-h-0 flex-1"
      title="SEM Image"
      :meta="meta"
      icon="i-lucide-image"
      body-class="flex flex-col"
    >
      <div
        v-if="analysis.focusPending.value"
        class="flex flex-1 items-center justify-center gap-2 sk-body"
      >
        <UIcon
          name="i-lucide-loader-circle"
          class="h-4 w-4 animate-spin"
        />
        불러오는 중…
      </div>
      <div
        v-else-if="measuredName && focusCtx.eqp_ip"
        class="relative min-h-0 flex-1 overflow-hidden rounded-(--sk-r-chip) border border-(--sk-border)"
      >
        <EbeamSkewvoirZoomableImage
          :key="measuredName"
          :src="resolveImageUrl(measuredName)!"
          :alt="measuredName"
          class="h-full w-full"
        />
        <button
          type="button"
          class="absolute top-2 right-2 rounded-(--sk-r-sidebar) border border-(--sk-border) bg-(--sk-surface)/90 p-1.5 text-(--sk-ink-muted) shadow-sm backdrop-blur-sm transition-colors duration-200 hover:text-(--sk-ink)"
          aria-label="전체 화면"
          @click="zoomSrc = resolveImageUrl(measuredName)"
        >
          <UIcon
            name="i-lucide-maximize-2"
            class="h-4 w-4"
          />
        </button>
      </div>
      <div
        v-else
        class="flex flex-1 items-center justify-center sk-body"
      >
        측정 이미지가 없습니다.
      </div>
    </EbeamSkewvoirPanelFrame>

    <EbeamSkewvoirImageLightbox v-model="zoomSrc" />
  </div>
</template>

<script setup lang="ts">
import type { SkewvoirAnalysis } from '~/composables/useSkewvoirAnalysis'
import { measuredRows } from '~/utils/msrRows'

const props = defineProps<{ analysis: SkewvoirAnalysis }>()

const { imageUrl } = useMsrImageApi()

const zoomSrc = ref<string | null>(null)

// The SEM micrograph belongs to the FOCUS MSR — same context as the gallery.
const focusCtx = useFocusImageCtx(props.analysis)

const resolveImageUrl = (name: string): string | null => {
  const ctx = focusCtx.value
  return ctx.eqp_ip ? imageUrl(ctx.eqp_ip, ctx.class_name, ctx.msr, name) : null
}

// The measured micrograph for the active parameter — the focused point's image
// leads, else the first measured point's.
const measuredName = computed(() => {
  const rows = measuredRows(props.analysis.siteRows.value).filter(r => r.parameter === props.analysis.activeParam.value)
  const focused = props.analysis.focusedSequence.value
  const focusedRow = focused != null ? rows.find(r => r.sequence === focused) : null
  return (focusedRow ?? rows[0])?.mp_image_name_01 || null
})

const meta = computed(() => {
  const seq = props.analysis.focusedSequence.value
  return seq != null && measuredName.value ? `seq ${seq}` : (measuredName.value ? '측정 이미지' : '없음')
})
</script>
