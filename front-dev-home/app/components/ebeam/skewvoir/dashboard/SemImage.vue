<template>
  <div class="flex min-h-0 flex-col">
    <EbeamSkewvoirPanelFrame
      class="min-h-0 flex-1"
      title="SEM Image"
      :meta="meta"
      icon="i-lucide-image"
      body-class="flex flex-col"
    >
      <!-- One targeting point, several images (HV-SEM: -U/-T/-M/-L). The
           selector sits OUTSIDE the render branches below so a TIFF-only or
           failed variant can still be switched away from. NAVIGATE family:
           picking a sub-image changes the view, it narrows no data. -->
      <div
        v-if="imageNames.length > 1"
        class="mb-2 flex flex-wrap items-center gap-1"
        role="group"
        aria-label="측정 이미지 선택"
      >
        <button
          v-for="(name, i) in imageNames"
          :key="name"
          type="button"
          class="rounded-(--sk-r-sidebar) border px-2 py-0.5 font-mono text-[11px] font-medium transition-colors duration-200"
          :class="i === selectedIndex
            ? 'border-(--sk-ink) bg-(--sk-ink) text-(--sk-ink-fg)'
            : 'border-(--sk-border) text-(--sk-ink-muted) hover:text-(--sk-ink)'"
          :aria-pressed="i === selectedIndex"
          :aria-label="`이미지 ${imageVariantLabel(name, i)}`"
          @click="selectedIndex = i"
        >
          {{ imageVariantLabel(name, i) }}
        </button>
      </div>
      <AppLoadingState
        v-if="analysis.focusPending.value"
        variant="inline"
        class="flex-1"
        title="불러오는 중입니다."
      />
      <!-- TIFF originals have no browser preview — hand off to download. -->
      <div
        v-else-if="measuredName && focusCtx.eqp_ip && isTiffName(measuredName)"
        class="flex flex-1 flex-col items-center justify-center gap-2 rounded-(--sk-r-chip) border border-(--sk-border) sk-body"
      >
        <UIcon
          name="i-lucide-file-image"
          class="h-6 w-6 text-(--sk-ink-subtle)"
        />
        <span>TIFF 원본 — 브라우저 미리보기 미지원</span>
        <a
          :href="resolveImageUrl(measuredName)!"
          :download="measuredName"
          class="inline-flex items-center gap-1 rounded-(--sk-r-sidebar) border border-(--sk-border) px-2 py-0.5 font-mono text-[10px] text-(--sk-ink-muted) transition-colors hover:text-(--sk-ink)"
        >
          <UIcon
            name="i-lucide-download"
            class="h-3 w-3"
          />
          원본 다운로드
        </a>
      </div>
      <!-- The cache warmer is still pulling this parameter's images off the
           tool. Asking for one now would be a cold in-request FTP fetch, which
           the cloud ingress 502s (and the browser logs, unsuppressably) — so
           wait for the job and turn the first request into a cache hit. -->
      <AppLoadingState
        v-else-if="holdForWarm"
        variant="inline"
        class="flex-1"
        :title="warmLabel"
      />
      <div
        v-else-if="measuredName && focusCtx.eqp_ip && !loadFailed"
        class="relative min-h-0 flex-1 overflow-hidden rounded-(--sk-r-chip) border border-(--sk-border)"
      >
        <EbeamSkewvoirZoomableImage
          :key="measuredName"
          :src="resolveImageUrl(measuredName)!"
          :alt="measuredName"
          class="h-full w-full"
          @error="loadFailed = true"
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
      <!-- Explicit missing-image state: the selected point has no image (failed
           measurement, no file, or the file itself failed to load). Never fall
           back to a DIFFERENT point's image — that would misattribute it. -->
      <div
        v-else
        class="flex flex-1 flex-col items-center justify-center gap-2 rounded-(--sk-r-chip) border border-dashed border-(--sk-border)"
      >
        <UIcon
          name="i-lucide-image-off"
          class="h-7 w-7 text-(--sk-ink-subtle)"
        />
        <span class="font-medium text-(--sk-ink-muted) sk-body">이미지 없음 · No Image</span>
        <span
          v-if="missingReason"
          class="sk-meta"
        >{{ missingReason }}</span>
      </div>
    </EbeamSkewvoirPanelFrame>

    <EbeamSkewvoirImageLightbox v-model="zoomSrc" />
  </div>
</template>

<script setup lang="ts">
import type { SkewvoirAnalysis } from '~/composables/useSkewvoirAnalysis'
import type { WarmState } from '~/composables/useMsrImageWarmer'
import { imageVariantLabel, isTiffName } from '~/utils/imageKind'
import { warmProgressLabel } from '~/utils/imageWarm'
import { measuredRows, rowImageNames } from '~/utils/msrRows'

// `warm` is optional so the panel still renders standalone; without it the
// image is requested straight away, which is the pre-gate behaviour.
const props = defineProps<{ analysis: SkewvoirAnalysis, warm?: WarmState }>()

const { imageUrl } = useMsrImageApi()

const zoomSrc = ref<string | null>(null)

// The SEM micrograph belongs to the FOCUS MSR — same context as the gallery.
const focusCtx = useFocusImageCtx(props.analysis)

const resolveImageUrl = (name: string): string | null => {
  const ctx = focusCtx.value
  return ctx.eqp_ip ? imageUrl(ctx.eqp_ip, ctx.class_name, ctx.msr, name) : null
}

// The micrograph's row for the active parameter. With a focused point, ONLY
// that point qualifies — a focused point with a failed/missing image shows
// the 이미지 없음 state instead of silently borrowing another point's image.
// With no focus, the first measured point leads.
const measuredRow = computed(() => {
  const rows = measuredRows(props.analysis.siteRows.value).filter(r => r.parameter === props.analysis.activeParam.value)
  const focused = props.analysis.focusedSequence.value
  if (focused != null) {
    return rows.find(r => r.sequence === focused) ?? null
  }
  return rows[0] ?? null
})

// A point's image files: one on CD-SEM, several stem-suffixed on HV-SEM
// (user-confirmed 2026-08-08). The selection is per-point — moving to another
// point (or parameter/MSR) starts back at the first image.
const imageNames = computed(() => (measuredRow.value ? rowImageNames(measuredRow.value) : []))

const selectedIndex = ref(0)
watch(
  () => `${focusCtx.value.msr}|${props.analysis.activeParam.value}|${measuredRow.value?.sequence ?? ''}`,
  () => {
    selectedIndex.value = 0
  }
)

const measuredName = computed(() => imageNames.value[selectedIndex.value] ?? imageNames.value[0] ?? null)

// A failed load is per-image: switching to another image retries cleanly.
const loadFailed = ref(false)
watch(measuredName, () => {
  loadFailed.value = false
})

// Why the placeholder is showing, for the small line under 이미지 없음.
const missingReason = computed(() => {
  const focused = props.analysis.focusedSequence.value
  if (loadFailed.value) return '이미지를 불러오지 못했습니다'
  if (measuredName.value && !focusCtx.value.eqp_ip) return '장비 정보 없음'
  if (focused != null) return `seq ${focused} — 측정 실패 또는 이미지 누락`
  return null
})

// Hold the <img> back only when there is something to hold: with no image or
// no tool, 이미지 없음 is already the right answer and waiting would just
// delay it. TIFF is excluded by branch order — its card requests no bytes.
const holdForWarm = computed(() =>
  props.warm?.status === 'warming' && !!measuredName.value && !!focusCtx.value.eqp_ip)

const warmLabel = computed(() =>
  warmProgressLabel(props.warm?.done ?? 0, props.warm?.total ?? 0))

const meta = computed(() => {
  if (holdForWarm.value) return '준비 중'
  const seq = props.analysis.focusedSequence.value
  const ok = measuredName.value && !loadFailed.value
  const variant = imageNames.value.length > 1 && measuredName.value
    ? ` · ${imageVariantLabel(measuredName.value, selectedIndex.value)}`
    : ''
  return seq != null && ok ? `seq ${seq}${variant}` : (ok ? `측정 이미지${variant}` : '없음')
})
</script>
