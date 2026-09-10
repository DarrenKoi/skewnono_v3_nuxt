<template>
  <Teleport to="body">
    <div
      v-if="open && entry"
      class="fixed inset-0 z-50 flex bg-black/80"
      role="dialog"
      aria-modal="true"
      @click.self="emit('close')"
    >
      <!-- Image stage -->
      <div class="relative flex min-w-0 flex-1 flex-col">
        <div class="relative min-h-0 flex-1">
          <EbeamSkewvoirZoomableImage
            v-if="activeName && !failed && blobUrl"
            :key="activeName + nonce"
            :src="blobUrl"
            :alt="activeName"
            class="h-full w-full"
          />
          <div
            v-else-if="activeName && loading"
            class="flex h-full items-center justify-center gap-2 text-white/70"
          >
            <UIcon
              name="i-lucide-loader-circle"
              class="h-6 w-6 animate-spin"
            />
          </div>
          <div
            v-else
            class="flex h-full flex-col items-center justify-center gap-2 text-white/70"
          >
            <UIcon
              name="i-lucide-image-off"
              class="h-8 w-8"
            />
            <span class="text-sm">{{ activeName ? '이미지 로드 실패' : '이미지 없음' }}</span>
            <button
              v-if="activeName"
              type="button"
              class="mt-1 inline-flex items-center gap-1 rounded-md border border-white/30 px-2.5 py-1 font-mono text-xs text-white/80 hover:text-white"
              @click="retry"
            >
              <UIcon
                name="i-lucide-rotate-ccw"
                class="h-3.5 w-3.5"
              />
              재시도
            </button>
          </div>

          <!-- Prev / next -->
          <button
            v-if="entries.length > 1"
            type="button"
            class="absolute top-1/2 left-3 -translate-y-1/2 rounded-full bg-black/50 p-2 text-white transition-colors hover:bg-black/70"
            aria-label="이전"
            @click="step(-1)"
          >
            <UIcon
              name="i-lucide-chevron-left"
              class="h-5 w-5"
            />
          </button>
          <button
            v-if="entries.length > 1"
            type="button"
            class="absolute top-1/2 right-3 -translate-y-1/2 rounded-full bg-black/50 p-2 text-white transition-colors hover:bg-black/70"
            aria-label="다음"
            @click="step(1)"
          >
            <UIcon
              name="i-lucide-chevron-right"
              class="h-5 w-5"
            />
          </button>

          <!-- Physical scale bar (honest: pixel ruler + calibration disclosure). -->
          <div class="absolute bottom-3 left-3 flex flex-col gap-1 rounded-md bg-black/55 px-2.5 py-1.5 backdrop-blur-sm">
            <div class="flex items-center gap-1.5">
              <div class="h-1 w-16 rounded-sm bg-white/90" />
              <span class="font-mono text-xs text-white/85">{{ scaleLabel }}</span>
            </div>
            <span class="font-mono text-xs text-white/50">{{ scaleNote }}</span>
          </div>
        </div>
      </div>

      <!-- Metadata rail -->
      <aside class="flex w-72 shrink-0 flex-col gap-4 overflow-y-auto border-l border-white/10 bg-(--sk-surface) p-4">
        <div class="flex items-center justify-between">
          <h3 class="sk-title">
            이미지 근거
          </h3>
          <button
            type="button"
            class="rounded-(--sk-r-sidebar) p-1 text-(--sk-ink-muted) hover:text-(--sk-ink)"
            aria-label="닫기"
            @click="emit('close')"
          >
            <UIcon
              name="i-lucide-x"
              class="h-4 w-4"
            />
          </button>
        </div>

        <!-- Same chip rule as the grid card: the baseline 측정 순서 tag says
             nothing the sequence row below does not, so it gets no chip. -->
        <div
          v-if="chips.length || entry.monitor?.low"
          class="flex flex-wrap gap-1"
        >
          <span
            v-for="reason in chips"
            :key="reason"
            class="rounded-(--sk-r-sidebar) px-1.5 py-0.5 font-mono text-xs font-semibold"
            :class="roleClass(REASON_META[reason].role)"
          >{{ REASON_META[reason].label }}</span>
          <span
            v-if="entry.monitor?.low"
            class="rounded-(--sk-r-sidebar) border border-(--sk-border) px-1.5 py-0.5 font-mono text-xs text-(--sk-ink-muted)"
          >취득 점수↓</span>
        </div>

        <!-- HV-SEM sub-images of this point (-U/-T/-M/-L). NAVIGATE family:
             picking one changes which image is on stage. -->
        <EbeamSkewvoirVariantChips
          v-if="entry.images.length > 1"
          v-model="variantIndex"
          :names="entry.images"
        />

        <!-- The stage shows the WebP rendition; the original TIFF is served
             untouched here. -->
        <a
          v-if="isTiff && downloadUrl"
          :href="downloadUrl"
          :download="activeName ?? undefined"
          class="inline-flex items-center justify-center gap-1.5 rounded-(--sk-r-nav) border border-(--sk-border) px-3 py-1.5 font-mono text-xs text-(--sk-ink-muted) transition-colors hover:text-(--sk-ink)"
        >
          <UIcon
            name="i-lucide-download"
            class="h-3.5 w-3.5"
          />
          TIFF 원본 다운로드
        </a>

        <dl class="space-y-1.5">
          <div
            v-for="item in meta"
            :key="item.k"
            class="flex items-center justify-between gap-2 text-[12px]"
          >
            <dt class="text-(--sk-ink-muted)">
              {{ item.k }}
            </dt>
            <dd class="truncate font-mono tabular-nums text-(--sk-ink)">
              {{ item.v }}
            </dd>
          </div>
        </dl>

        <div v-if="cond">
          <p class="mb-1 sk-title">
            취득 조건
          </p>
          <pre class="max-h-32 overflow-auto rounded-(--sk-r-chip) border border-(--sk-border) bg-(--sk-chip-bg) p-2 font-mono text-xs whitespace-pre-wrap text-(--sk-ink-muted)">{{ cond }}</pre>
        </div>

        <button
          type="button"
          class="inline-flex items-center justify-center gap-1.5 rounded-(--sk-r-nav) border border-(--sk-accent)/40 bg-(--sk-accent)/10 px-3 py-1.5 font-mono text-xs font-medium text-(--sk-accent) transition-colors hover:bg-(--sk-accent)/20"
          @click="emit('moveToSite', entry.chip)"
        >
          <UIcon
            name="i-lucide-crosshair"
            class="h-3.5 w-3.5"
          />
          wafer 위치 이동
        </button>

        <button
          type="button"
          class="inline-flex items-center justify-center gap-1.5 rounded-(--sk-r-nav) border border-(--sk-border) px-3 py-1.5 font-mono text-xs text-(--sk-ink-muted) transition-colors hover:text-(--sk-ink)"
          @click="emit('evidence', entry)"
        >
          <UIcon
            name="i-lucide-layers"
            class="h-3.5 w-3.5"
          />
          측정 근거 레이어
        </button>

        <p class="mt-auto font-mono text-xs text-(--sk-ink-subtle)">
          {{ index + 1 }} / {{ entries.length }} · ← → 로 이동
        </p>
      </aside>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import type { WaferGeometry } from '~/utils/waferGeometry'
import { isTiffName } from '~/utils/imageKind'
import { REASON_META, chipReasons, reviewImage, type ReviewEntry } from '~/utils/skewvoirAnalysis/gallery'

const props = defineProps<{
  open: boolean
  entries: ReviewEntry[]
  index: number
  geo: WaferGeometry
  eqp_ip: string
  class_name: string
  msr: string
  /** recipe+parameter scope for the remembered sub-image pick. Passed in rather
   * than derived here because this viewer takes review entries, not the
   * analysis context that knows the recipe. Null disables the memory. */
  variantKey: string | null
  /** False while another layer sits ON TOP of this viewer (the 측정 근거 레이어
   * drawer). Arrow/Esc are bound to `window`, so without this the viewer keeps
   * answering keys meant for the layer above it: one Esc tore down the drawer
   * AND the viewer together, and ← → stepped the image behind an open drawer
   * whose contents still described the image it had left. */
  keyboard?: boolean
}>()
const emit = defineEmits<{
  'close': []
  'update:index': [value: number]
  'moveToSite': [chip: string]
  'evidence': [entry: ReviewEntry]
}>()

const { fetchImageWithCond, imageUrl } = useMsrImageApi()

const entry = computed<ReviewEntry | null>(() => props.entries[props.index] ?? null)
const chips = computed(() => (entry.value ? chipReasons(entry.value) : []))

// One point, several sub-images on HV-SEM (-U/-T/-M/-L, 2026-08-08). The pick
// is REMEMBERED per recipe+parameter (2026-08-11) and shared with the SEM Image
// panel and the site drawer, so arrowing through the review queue holds the
// depth the reviewer chose. Derived from the entry's own names, so an entry
// lacking that suffix falls back to its first image without a reset watcher.
const variantIndex = useSkewvoirVariantIndex(
  () => entry.value?.images ?? [],
  () => props.variantKey
)

// The selected variant, falling back to the entry's representative image when
// the index is out of range (a stale index during an entry swap). That fallback
// read `entry.image` until 2026-08-09 — the same value by invariant, which is
// exactly why the second field was worth deleting.
const activeName = computed<string | null>(() => {
  const current = entry.value
  if (!current) return null
  return current.images[variantIndex.value] ?? reviewImage(current)
})

const isTiff = computed(() => isTiffName(activeName.value))
const downloadUrl = computed(() => {
  const name = activeName.value
  return name && props.eqp_ip ? imageUrl(props.eqp_ip, props.class_name, props.msr, name) : null
})

const failed = ref(false)
const loading = ref(false)
const nonce = ref(0)
const blobUrl = ref<string | null>(null)
const cond = ref<string | null>(null)

const revokeBlob = () => {
  if (blobUrl.value) {
    URL.revokeObjectURL(blobUrl.value)
    blobUrl.value = null
  }
}

// Guards against a slow, superseded fetch (retry / rapid prev-next) clobbering
// a newer one's result.
let loadToken = 0

const loadImage = async () => {
  // Bump the token FIRST so any in-flight request is invalidated even when we
  // early-return on an empty context (otherwise a slow prior fetch could
  // resolve and install a stale blob after we've navigated to no image).
  const token = ++loadToken
  const name = activeName.value
  revokeBlob()
  cond.value = null
  failed.value = false
  if (!name || !props.eqp_ip) {
    // A missing context (no focus row resolved yet) is a load failure, same
    // as a missing image name — never silently render a broken image.
    if (name && !props.eqp_ip) failed.value = true
    return
  }
  loading.value = true
  try {
    // preview: the display rendition — the server converts a TIFF original to
    // WebP (2026-08-08) and passes anything else through byte-identical, so
    // the blob always renders. The 원본 다운로드 link (rail, when isTiff)
    // keeps pointing at the unconverted file.
    const res = await fetchImageWithCond(
      props.eqp_ip, props.class_name, props.msr, name, { preview: true }
    )
    if (token !== loadToken) {
      URL.revokeObjectURL(res.blobUrl)
      return
    }
    blobUrl.value = res.blobUrl
    cond.value = res.cond
  } catch {
    if (token === loadToken) failed.value = true
  } finally {
    if (token === loadToken) loading.value = false
  }
}

const retry = () => {
  nonce.value++
  loadImage()
}

const step = (delta: number) => {
  if (props.entries.length === 0) return
  const next = (props.index + delta + props.entries.length) % props.entries.length
  emit('update:index', next)
}

// A new image (a changed MSR context, entry step, or variant pick) reloads.
watch(
  () => `${props.eqp_ip}|${props.class_name}|${props.msr}|${activeName.value ?? ''}`,
  () => {
    nonce.value = 0
    loadImage()
  },
  { immediate: true }
)

onBeforeUnmount(() => {
  loadToken++
  revokeBlob()
})

// Physical scale bar. The image RESOLUTION comes from meas_condition_pixel and
// the FIELD OF VIEW is derived from meas_condition_mag (FOV = 135000/Mag, see
// utils/magPixel.ts), so a real nm/pixel calibration is now available.
//
// The bar itself stays a pixel ruler on purpose: it is a fixed 64 CSS px while
// the image sits inside ZoomableImage, so claiming the BAR spans N nm would be
// wrong at every zoom level but one. nm/px is a property of the acquisition,
// not of the display, so it goes in the note and the metadata rail instead.
const pixelDims = computed(() => entry.value?.pixel ?? '')
const scaleLabel = computed(() => {
  const w = Number(pixelDims.value.split(',')[0])
  return Number.isFinite(w) && w > 0 ? `${Math.round(w / 8)} px` : '— px'
})
const scaleNote = computed(() => {
  const nmPerPx = entry.value?.nmPerPx
  const res = `해상도 ${pixelDims.value || '—'}`
  return nmPerPx != null ? `${res} · ${nmPerPx.toFixed(3)} nm/px` : `${res} · 배율 정보 없음`
})

const meta = computed(() => {
  const e = entry.value
  if (!e) return []
  const items: { k: string, v: string }[] = [
    { k: 'chip / MP', v: `${e.chip} · MP${e.mp}` },
    { k: 'sequence', v: String(e.sequence) },
    { k: e.parameter, v: e.value != null ? `${e.value.toFixed(2)}${e.unit ? ' ' + e.unit : ''}` : '실패' }
  ]
  if (e.residual != null) items.push({ k: '국소 잔차', v: `${e.residual >= 0 ? '+' : ''}${e.residual.toFixed(2)}${e.unit ? ' ' + e.unit : ''}` })
  items.push({ k: '배율', v: e.mag ? `${e.mag.toLocaleString()}x` : '—' })
  items.push({ k: '픽셀 크기', v: e.nmPerPx != null ? `${e.nmPerPx.toFixed(3)} nm/px` : '—' })
  items.push({ k: '진공', v: e.vac ? String(e.vac) : '—' })
  if (e.monitor) {
    items.push({ k: '측정 점수', v: e.monitor.measurementScore != null ? String(e.monitor.measurementScore) : '—' })
  }
  return items
})

const roleClass = (role: 'bad' | 'warn' | 'muted'): string => {
  if (role === 'bad') return 'bg-(--sk-bad)/90 text-white'
  if (role === 'warn') return 'bg-(--sk-warn)/90 text-black'
  return 'bg-(--sk-chip-bg) text-(--sk-ink-muted)'
}

// Keyboard nav — arrows step, Esc closes. Bound only while this viewer is the
// TOP layer: `keyboard` goes false under the 측정 근거 레이어 drawer, so Esc
// dismisses the drawer alone and ← → cannot step the image out from under it.
//
// Deliberately its OWN watcher rather than a wider source on the lifecycle
// watch below: that one also revokes the decoded blob when it goes false, so
// folding `keyboard` into it would blank the micrograph behind the drawer.
const onKey = (e: KeyboardEvent) => {
  if (e.key === 'Escape') emit('close')
  else if (e.key === 'ArrowLeft') step(-1)
  else if (e.key === 'ArrowRight') step(1)
}
watch(() => props.open && props.keyboard !== false, (listening) => {
  if (!import.meta.client) return
  if (listening) window.addEventListener('keydown', onKey)
  else window.removeEventListener('keydown', onKey)
})

// Blob lifecycle — separate concern, keyed on `open` alone.
watch(() => props.open, (isOpen) => {
  if (isOpen) {
    // Reopening on the same image: the image-key watcher won't refire (nothing
    // changed), so the blob a previous close released has to be re-fetched.
    if (!blobUrl.value) loadImage()
    return
  }
  // Closing releases the decoded micrograph immediately. This viewer is a
  // persistent Teleport, so deferring to unmount — or to the next image change
  // — would pin a full-resolution image in memory for the rest of the session.
  loadToken++
  revokeBlob()
  cond.value = null
  failed.value = false
  loading.value = false
})
onBeforeUnmount(() => {
  if (import.meta.client) window.removeEventListener('keydown', onKey)
})
</script>
