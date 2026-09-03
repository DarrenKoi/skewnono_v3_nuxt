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
           header sits OUTSIDE the render branches below so a TIFF-only or
           failed variant can still be switched away from. Both controls are
           NAVIGATE family: they change what is shown, they narrow no data. -->
      <div
        v-if="imageNames.length > 1"
        class="mb-2 flex flex-wrap items-center justify-between gap-2"
      >
        <EbeamSkewvoirVariantChips
          v-if="displayMode === 'single'"
          v-model="variantIndex"
          :names="imageNames"
        />
        <span
          v-else
          class="sk-meta"
        >{{ imageNames.length }}장 전체</span>

        <!-- The reviewer's choice of HOW a multi-image point renders: one
             image with the selector above, or every sub-image at once.
             Persisted — a reviewer who compares depths side by side keeps
             the mode across reloads. -->
        <div
          class="flex items-center gap-1"
          role="group"
          aria-label="표시 방식"
        >
          <button
            type="button"
            class="rounded-(--sk-r-sidebar) border p-1 transition-colors duration-200"
            :class="displayMode === 'single'
              ? 'border-(--sk-ink) bg-(--sk-ink) text-(--sk-ink-fg)'
              : 'border-(--sk-border) text-(--sk-ink-muted) hover:text-(--sk-ink)'"
            :aria-pressed="displayMode === 'single'"
            aria-label="하나씩 보기"
            title="하나씩 보기"
            @click="displayMode = 'single'"
          >
            <UIcon
              name="i-lucide-image"
              class="h-3.5 w-3.5"
            />
          </button>
          <button
            type="button"
            class="rounded-(--sk-r-sidebar) border p-1 transition-colors duration-200"
            :class="displayMode === 'all'
              ? 'border-(--sk-ink) bg-(--sk-ink) text-(--sk-ink-fg)'
              : 'border-(--sk-border) text-(--sk-ink-muted) hover:text-(--sk-ink)'"
            :aria-pressed="displayMode === 'all'"
            aria-label="전체 보기"
            title="전체 보기"
            @click="displayMode = 'all'"
          >
            <UIcon
              name="i-lucide-layout-grid"
              class="h-3.5 w-3.5"
            />
          </button>
        </div>
      </div>
      <AppLoadingState
        v-if="analysis.focusPending.value"
        variant="inline"
        class="flex-1"
        title="불러오는 중입니다."
      />
      <!-- The cache warmer is still pulling this parameter's images off the
           tool. Asking for one now would be a cold in-request FTP fetch, which
           the cloud ingress 502s (and the browser logs, unsuppressably) — so
           wait for the job and turn the first request into a cache hit. TIFFs
           are held too since 2026-08-08: their preview derives server-side
           from the cached original, so the warm is what makes it a cache hit. -->
      <AppLoadingState
        v-else-if="holdForWarm"
        variant="inline"
        class="flex-1"
        :title="warmLabel"
      />
      <!-- 전체 mode: every sub-image of the point at once, labeled by its
           variant. Same preview URLs the single mode uses, so switching modes
           costs no extra fetch. A thumb click enlarges in the lightbox. -->
      <div
        v-else-if="showAllGrid"
        class="grid min-h-0 flex-1 auto-rows-fr content-start gap-2 overflow-auto"
        :class="imageNames.length > 2 ? 'grid-cols-2' : 'grid-cols-1 sm:grid-cols-2'"
      >
        <figure
          v-for="(name, i) in imageNames"
          :key="name"
          class="relative min-h-0 overflow-hidden rounded-(--sk-r-chip) border border-(--sk-border)"
        >
          <button
            type="button"
            class="block h-full w-full cursor-zoom-in"
            :aria-label="`이미지 ${imageLabels[i]} 확대해서 보기`"
            @click="zoomSrc = displayImageUrl(name)"
          >
            <img
              :src="displayImageUrl(name)!"
              :alt="name"
              loading="lazy"
              decoding="async"
              class="h-full w-full object-cover"
            >
          </button>
          <span class="absolute top-1 left-1 rounded-(--sk-r-sidebar) bg-(--sk-ink)/85 px-1.5 py-0.5 font-mono text-xs font-medium text-(--sk-ink-fg)">
            {{ imageLabels[i] }}
          </span>
          <a
            v-if="isTiffName(name)"
            :href="resolveImageUrl(name)!"
            :download="name"
            class="absolute top-1 right-1 rounded-(--sk-r-sidebar) border border-(--sk-border) bg-(--sk-surface)/90 p-1 text-(--sk-ink-muted) shadow-sm backdrop-blur-sm transition-colors duration-200 hover:text-(--sk-ink)"
            aria-label="TIFF 원본 다운로드"
            title="TIFF 원본 다운로드"
          >
            <UIcon
              name="i-lucide-download"
              class="h-3 w-3"
            />
          </a>
        </figure>
      </div>
      <!-- TIFF originals render through the server-side WebP preview
           (?preview=1); the download button serves the untouched file. -->
      <div
        v-else-if="measuredName && focusCtx.eqp_ip && !loadFailed"
        class="relative min-h-0 flex-1 overflow-hidden rounded-(--sk-r-chip) border border-(--sk-border)"
      >
        <EbeamSkewvoirZoomableImage
          :key="measuredName"
          :src="displayImageUrl(measuredName)!"
          :alt="measuredName"
          class="h-full w-full"
          @error="loadFailed = true"
        />
        <div class="absolute top-2 right-2 flex items-center gap-1.5">
          <!-- Erase the crosshair the tool drew onto the micrograph, so the
               structure under it can be read. Server-side, from the image's
               cond.txt; a no-op when the sidecar locates none. -->
          <button
            type="button"
            class="rounded-(--sk-r-sidebar) border p-1.5 shadow-sm backdrop-blur-sm transition-colors duration-200"
            :class="hideCrosshair
              ? 'border-(--sk-ink) bg-(--sk-ink) text-(--sk-ink-fg)'
              : 'border-(--sk-border) bg-(--sk-surface)/90 text-(--sk-ink-muted) hover:text-(--sk-ink)'"
            :aria-pressed="hideCrosshair"
            aria-label="십자선 지우기"
            title="장비가 그린 십자선 지우기"
            @click="hideCrosshair = !hideCrosshair"
          >
            <UIcon
              name="i-lucide-crosshair"
              class="h-4 w-4"
            />
          </button>
          <a
            v-if="isTiffName(measuredName)"
            :href="resolveImageUrl(measuredName)!"
            :download="measuredName"
            class="rounded-(--sk-r-sidebar) border border-(--sk-border) bg-(--sk-surface)/90 p-1.5 text-(--sk-ink-muted) shadow-sm backdrop-blur-sm transition-colors duration-200 hover:text-(--sk-ink)"
            aria-label="TIFF 원본 다운로드"
            title="TIFF 원본 다운로드"
          >
            <UIcon
              name="i-lucide-download"
              class="h-4 w-4"
            />
          </a>
          <button
            type="button"
            class="rounded-(--sk-r-sidebar) border border-(--sk-border) bg-(--sk-surface)/90 p-1.5 text-(--sk-ink-muted) shadow-sm backdrop-blur-sm transition-colors duration-200 hover:text-(--sk-ink)"
            aria-label="전체 화면"
            @click="zoomSrc = displayImageUrl(measuredName)"
          >
            <UIcon
              name="i-lucide-maximize-2"
              class="h-4 w-4"
            />
          </button>
        </div>
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
        <!-- A TIFF that failed to render is not a TIFF that failed to exist:
             the WebP preview is a server-side conversion, so an undecodable or
             unsupported original lands here while the file itself is fine to
             download. Keeping the original reachable is the constraint
             msr_image/preview.py's docstring states, and the same affordance
             ImageViewer and SiteEvidenceDrawer offer from their own failures. -->
        <a
          v-if="downloadName"
          :href="resolveImageUrl(downloadName)!"
          :download="downloadName"
          class="mt-1 inline-flex items-center gap-1.5 rounded-(--sk-r-sidebar) border border-(--sk-border) px-2.5 py-1 text-(--sk-ink-muted) transition-colors duration-200 sk-meta hover:text-(--sk-ink)"
        >
          <UIcon
            name="i-lucide-download"
            class="h-3.5 w-3.5"
          />
          TIFF 원본 다운로드
        </a>
      </div>
    </EbeamSkewvoirPanelFrame>

    <EbeamSkewvoirImageLightbox v-model="zoomSrc" />
  </div>
</template>

<script setup lang="ts">
import type { SkewvoirAnalysis } from '~/composables/useSkewvoirAnalysis'
import type { WarmState } from '~/composables/useMsrImageWarmer'
import { imageVariantLabels, isTiffName } from '~/utils/imageKind'
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

// What the <img>/lightbox loads: the browser-renderable rendition (TIFF →
// server-side WebP; a passthrough otherwise). resolveImageUrl stays the
// untouched original for the 원본 다운로드 link.
const displayImageUrl = (name: string): string | null => {
  const ctx = focusCtx.value
  return ctx.eqp_ip
    ? imageUrl(ctx.eqp_ip, ctx.class_name, ctx.msr, name, { preview: true, clean: hideCrosshair.value })
    : null
}

// Whether the micrograph is served with the tool-drawn crosshair erased
// (?clean=1). A reviewer preference like displayMode: it follows the reviewer
// across points and reloads. Off by default — the crosshair is what the tool
// measured, and erasing it is the exception a reviewer asks for.
const hideCrosshair = persistedFlag('skewvoir-sem-image-clean', 'skewnono:skewvoir:sem-image-clean', false)

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
// (user-confirmed 2026-08-08).
const imageNames = computed(() => (measuredRow.value ? rowImageNames(measuredRow.value) : []))

// List-aware labels (extension-disambiguated where one sub-position is listed
// under several extensions) — the grid badges and the meta caption must say
// the same thing the variant chips say.
const imageLabels = computed(() => imageVariantLabels(imageNames.value))

// How a multi-image point renders: 'single' (one image + variant chips) or
// 'all' (every sub-image as labeled thumbnails). A reviewer PREFERENCE, not
// per-point state, so it persists across points, parameters and reloads.
const displayMode = usePersistedState<'single' | 'all'>(
  'skewvoir-sem-image-display',
  'skewnono:skewvoir:sem-image-display',
  {
    default: () => 'single',
    normalize: parsed => (parsed === 'all' ? 'all' : 'single'),
    isEmpty: value => value === 'single'
  }
)

const showAllGrid = computed(() =>
  displayMode.value === 'all' && imageNames.value.length > 1 && !!focusCtx.value.eqp_ip)

// WHICH sub-image shows, remembered per recipe+parameter (2026-08-11). This
// replaced a `ref(0)` reset on every msr/parameter/point change: which suffixes
// a point even has is a property of the recipe's targeting setup for that
// parameter, so a reviewer comparing one depth across a wafer was re-picking it
// on every site. Nothing resets it here — the index is DERIVED from this
// point's names, so a point without the remembered suffix falls back to its
// first image on its own.
const variantKey = useSkewvoirVariantKey(props.analysis)
const variantIndex = useSkewvoirVariantIndex(imageNames, variantKey)

const measuredName = computed(() => imageNames.value[variantIndex.value] ?? imageNames.value[0] ?? null)

// A failed load is per-image: switching to another image retries cleanly.
const loadFailed = ref(false)
watch(measuredName, () => {
  loadFailed.value = false
})

// The original this point's placeholder can still offer, or null. Requires a
// resolvable URL (a name AND a tool) and a TIFF — for every other kind the
// placeholder means the bytes are genuinely absent, so a download link would
// only 404. This is deliberately NOT gated on `loadFailed`: a TIFF held back
// by a missing preview and one whose <img> errored are the same situation to
// the user, and both leave the original fetchable.
const downloadName = computed(() =>
  measuredName.value && focusCtx.value.eqp_ip && isTiffName(measuredName.value)
    ? measuredName.value
    : null)

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
// delay it. TIFFs are held like every other image (2026-08-08): their WebP
// preview derives server-side from the cached original the warmer pulls.
const holdForWarm = computed(() =>
  props.warm?.status === 'warming' && !!measuredName.value && !!focusCtx.value.eqp_ip)

const warmLabel = computed(() =>
  warmProgressLabel(props.warm?.done ?? 0, props.warm?.total ?? 0))

const meta = computed(() => {
  if (holdForWarm.value) return '준비 중'
  const seq = props.analysis.focusedSequence.value
  if (showAllGrid.value) {
    return seq != null
      ? `seq ${seq} · ${imageNames.value.length}장`
      : `측정 이미지 ${imageNames.value.length}장`
  }
  const ok = measuredName.value && !loadFailed.value
  const variant = imageNames.value.length > 1 && measuredName.value
    ? ` · ${imageLabels.value[variantIndex.value]}`
    : ''
  return seq != null && ok ? `seq ${seq}${variant}` : (ok ? `측정 이미지${variant}` : '없음')
})
</script>
