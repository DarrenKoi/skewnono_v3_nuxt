<template>
  <USlideover
    :open="open"
    :title="site ? `Site ${site.chip}` : '측정점 상세'"
    description="선택한 측정점의 값 · 잔차 · 순서 · SEM"
    :ui="{ content: 'w-[92vw] sm:min-w-[420px] sm:max-w-[50vw]' }"
    @update:open="emit('update:open', $event)"
  >
    <template #body>
      <div
        v-if="site"
        class="space-y-4"
      >
        <dl class="grid grid-cols-2 gap-2">
          <div class="rounded-(--sk-r-nav) border border-(--sk-border-soft) px-2.5 py-2">
            <dt class="sk-eyebrow text-[11px]">
              chip · seq
            </dt>
            <dd class="mt-0.5 font-mono text-sm font-semibold text-(--sk-ink)">
              {{ site.chip }} · {{ site.sequence }}
            </dd>
          </div>
          <div class="rounded-(--sk-r-nav) border border-(--sk-border-soft) px-2.5 py-2">
            <dt class="sk-eyebrow text-[11px]">
              sector · R
            </dt>
            <dd class="mt-0.5 font-mono text-sm font-semibold text-(--sk-ink)">
              {{ site.sector ?? '—' }} · {{ site.radiusMm != null ? `${site.radiusMm.toFixed(1)} mm` : '—' }}
            </dd>
          </div>
          <div class="rounded-(--sk-r-nav) border border-(--sk-border-soft) px-2.5 py-2">
            <dt class="sk-eyebrow text-[11px]">
              raw ({{ unit }})
            </dt>
            <dd class="mt-0.5 font-mono text-sm font-semibold text-(--sk-ink)">
              {{ site.raw.toFixed(3) }}
            </dd>
          </div>
          <div class="rounded-(--sk-r-nav) border border-(--sk-border-soft) px-2.5 py-2">
            <dt class="sk-eyebrow text-[11px]">
              중앙값 대비
            </dt>
            <dd
              class="mt-0.5 font-mono text-sm font-semibold"
              :class="site.centered >= 0 ? 'text-(--sk-bad)' : 'text-(--sk-ok)'"
            >
              {{ site.centered >= 0 ? '+' : '' }}{{ site.centered.toFixed(3) }}
            </dd>
          </div>
          <div class="col-span-2 rounded-(--sk-r-nav) border border-(--sk-border-soft) px-2.5 py-2">
            <dt class="sk-eyebrow text-[11px]">
              추세 잔차 (residual)
            </dt>
            <dd class="mt-0.5 font-mono text-sm font-semibold text-(--sk-ink)">
              <span v-if="site.residual != null">{{ site.residual >= 0 ? '+' : '' }}{{ site.residual.toFixed(3) }} {{ unit }}</span>
              <span
                v-else
                class="text-(--sk-ink-subtle)"
              >추세 없음 — 평가 불가</span>
            </dd>
          </div>
        </dl>

        <section>
          <p class="mb-1.5 sk-eyebrow text-[12px]">
            SEM 미리보기
          </p>
          <!-- HV-SEM sub-images of this point (-U/-T/-M/-L). NAVIGATE family. -->
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
              :class="i === variantIndex
                ? 'border-(--sk-ink) bg-(--sk-ink) text-(--sk-ink-fg)'
                : 'border-(--sk-border) text-(--sk-ink-muted) hover:text-(--sk-ink)'"
              :aria-pressed="i === variantIndex"
              :aria-label="`이미지 ${imageVariantLabel(name, i)}`"
              @click="variantIndex = i"
            >
              {{ imageVariantLabel(name, i) }}
            </button>
          </div>
          <!-- Image + 취득 조건 side by side once the drawer is at half-browser
               width; stacked again on narrow screens. -->
          <div
            class="grid grid-cols-1 gap-3"
            :class="imageCond ? 'lg:grid-cols-2' : ''"
          >
            <div>
              <div
                v-if="imageName && blobUrl"
                class="relative aspect-square w-full overflow-hidden rounded-(--sk-r-chip) border border-(--sk-border)"
              >
                <EbeamSkewvoirZoomableImage
                  :key="imageName"
                  :src="blobUrl"
                  :alt="imageName"
                  class="h-full w-full"
                />
              </div>
              <div
                v-else-if="imageName && imageLoading"
                class="flex h-40 items-center justify-center rounded-(--sk-r-chip) border border-dashed border-(--sk-border) sk-body"
              >
                <UIcon
                  name="i-lucide-loader-circle"
                  class="h-5 w-5 animate-spin"
                />
              </div>
              <!-- TIFF originals have no browser preview — hand off to download. -->
              <div
                v-else-if="imageName && isTiffName(imageName) && !imageFailed"
                class="flex h-40 flex-col items-center justify-center gap-1.5 rounded-(--sk-r-chip) border border-dashed border-(--sk-border) sk-body"
              >
                <UIcon
                  name="i-lucide-file-image"
                  class="h-5 w-5 text-(--sk-ink-subtle)"
                />
                <span>TIFF 원본 · 미리보기 미지원</span>
                <a
                  v-if="downloadUrl"
                  :href="downloadUrl"
                  :download="imageName"
                  class="inline-flex items-center gap-1 rounded-(--sk-r-sidebar) border border-(--sk-border) px-2 py-0.5 font-mono text-[10px] text-(--sk-ink-muted) transition-colors hover:text-(--sk-ink)"
                >
                  <UIcon
                    name="i-lucide-download"
                    class="h-3 w-3"
                  />
                  원본 다운로드
                </a>
              </div>
              <div
                v-else
                class="flex h-40 items-center justify-center rounded-(--sk-r-chip) border border-dashed border-(--sk-border) sk-body"
              >
                {{ imageFailed ? '이미지 로드 실패' : '측정 이미지가 없습니다.' }}
              </div>
            </div>

            <div v-if="imageCond">
              <p class="mb-1 sk-eyebrow text-[12px]">
                취득 조건
              </p>
              <pre class="max-h-96 overflow-auto rounded-(--sk-r-chip) border border-(--sk-border) bg-(--sk-chip-bg) p-2.5 font-mono text-[13px] leading-relaxed whitespace-pre-wrap text-(--sk-ink)">{{ imageCond }}</pre>
            </div>
          </div>
        </section>
      </div>
      <div
        v-else
        class="flex h-40 items-center justify-center px-4 text-center sk-body"
      >
        지도나 표에서 측정점을 선택하세요.
      </div>
    </template>
  </USlideover>
</template>

<script setup lang="ts">
import type { SkewvoirAnalysis } from '~/composables/useSkewvoirAnalysis'
import type { SpatialResult } from '~/utils/skewvoirAnalysis/spatial'
import { imageVariantLabel, isTiffName } from '~/utils/imageKind'
import { isMeasuredRow, rowImageNames } from '~/utils/msrRows'

const props = defineProps<{
  open: boolean
  spatial: SpatialResult
  analysis: SkewvoirAnalysis
  unit: string
}>()
const emit = defineEmits<{ 'update:open': [value: boolean] }>()

const { fetchImageWithCond, imageUrl } = useMsrImageApi()

// The focused site (by chip_number) — first measured site on that die.
const site = computed(() => {
  const key = props.analysis.focusedSite.value
  if (!key) return null
  return props.spatial.sites.find(s => s.chip === key) ?? null
})

// SEM micrograph(s) for the focused site's sequence, from the raw row. One on
// CD-SEM; several stem-suffixed sub-images on HV-SEM (user-confirmed
// 2026-08-08), offered as variants below the preview.
const imageNames = computed(() => {
  const s = site.value
  if (!s) return []
  const row = props.analysis.siteRows.value.find(
    r => r.parameter === props.analysis.activeParam.value && isMeasuredRow(r) && r.sequence === s.sequence
  )
  return row ? rowImageNames(row) : []
})

const variantIndex = ref(0)
watch(
  () => `${site.value?.chip ?? ''}#${site.value?.sequence ?? ''}`,
  () => {
    variantIndex.value = 0
  }
)

const imageName = computed(() => imageNames.value[variantIndex.value] ?? imageNames.value[0] ?? null)

// Every image in this drawer belongs to the FOCUS MSR — same context as the
// gallery (focusRow's eqp_ip/class_name + focusMsr).
const focusCtx = useFocusImageCtx(props.analysis)

const downloadUrl = computed(() => {
  const name = imageName.value
  const ctx = focusCtx.value
  return name && ctx.eqp_ip ? imageUrl(ctx.eqp_ip, ctx.class_name, ctx.msr, name) : null
})

const blobUrl = ref<string | null>(null)
const imageCond = ref<string | null>(null)
const imageLoading = ref(false)
const imageFailed = ref(false)

const revokeBlob = () => {
  if (blobUrl.value) {
    URL.revokeObjectURL(blobUrl.value)
    blobUrl.value = null
  }
}

let loadToken = 0

const loadImage = async () => {
  // Bump the token FIRST so an in-flight request is invalidated even on the
  // empty-context early returns below (else a slow prior fetch could resolve
  // and install a stale blob after the drawer moved on).
  const token = ++loadToken
  const name = imageName.value
  const ctx = focusCtx.value
  revokeBlob()
  imageCond.value = null
  imageFailed.value = false
  if (!name) return
  if (!ctx.eqp_ip) {
    // Context not resolved yet (e.g. focus row still pending) — treat as a
    // load failure rather than silently rendering a broken image.
    imageFailed.value = true
    return
  }
  imageLoading.value = true
  try {
    const res = await fetchImageWithCond(ctx.eqp_ip, ctx.class_name, ctx.msr, name)
    if (token !== loadToken) {
      URL.revokeObjectURL(res.blobUrl)
      return
    }
    if (isTiffName(name)) {
      // No browser can render the blob; the fetch still warmed the server
      // cache (instant 다운로드 click) and delivered the cond.
      URL.revokeObjectURL(res.blobUrl)
    } else {
      blobUrl.value = res.blobUrl
    }
    imageCond.value = res.cond
  } catch {
    if (token === loadToken) imageFailed.value = true
  } finally {
    if (token === loadToken) imageLoading.value = false
  }
}

watch(
  () => `${focusCtx.value.eqp_ip}|${focusCtx.value.class_name}|${focusCtx.value.msr}|${imageName.value ?? ''}`,
  () => loadImage(),
  { immediate: true }
)

watch(() => props.open, (isOpen) => {
  if (isOpen) {
    // Reopening on the same site: the key watcher above won't refire, so the
    // blob a previous close released has to be re-fetched.
    if (!blobUrl.value) loadImage()
    return
  }
  // The slideover stays mounted when closed, so releasing the blob here is what
  // keeps a closed drawer from holding a full-resolution micrograph.
  loadToken++
  revokeBlob()
  imageCond.value = null
  imageFailed.value = false
  imageLoading.value = false
})

onBeforeUnmount(() => {
  loadToken++
  revokeBlob()
})
</script>
