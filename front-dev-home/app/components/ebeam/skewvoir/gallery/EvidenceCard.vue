<template>
  <figure
    class="group flex flex-col overflow-hidden rounded-(--sk-r-chip) border transition-colors duration-200"
    :class="focused
      ? 'border-(--sk-accent) ring-1 ring-(--sk-accent)/40'
      : 'border-(--sk-border) hover:border-(--sk-accent)/50'"
  >
    <!-- Image well — each card owns its own load/error state, so one failed URL
         never blocks the rest of the grid. -->
    <div class="relative aspect-square w-full bg-(--sk-chip-bg)">
      <!-- TIFFs render like everything else since 2026-08-08: the grid's src
           carries preview=1, so the server serves a WebP rendition. The small
           corner tag says the file is a TIFF; the viewer offers the original. -->
      <button
        v-if="entry.image && !failed"
        type="button"
        class="block h-full w-full"
        :aria-label="`${entry.chip} 이미지 열기`"
        @click="emit('open')"
      >
        <!-- Hidden until it paints: `alt` is the image filename, and a pending
             <img> renders it, so the tile would show a wall of text under the
             spinner instead of a clean loading state. -->
        <img
          :src="src ?? undefined"
          :alt="entry.image"
          loading="lazy"
          class="h-full w-full object-cover"
          :class="loaded ? undefined : 'opacity-0'"
          @load="loaded = true"
          @error="onError"
        >
        <div
          v-if="!loaded"
          class="absolute inset-0 flex items-center justify-center"
        >
          <UIcon
            name="i-lucide-loader-circle"
            class="h-4 w-4 animate-spin text-(--sk-ink-subtle)"
          />
        </div>
      </button>

      <!-- Per-image failure → retry THIS image only. -->
      <div
        v-else-if="entry.image && failed"
        class="flex h-full flex-col items-center justify-center gap-1.5 px-2 text-center"
      >
        <UIcon
          name="i-lucide-image-off"
          class="h-5 w-5 text-(--sk-ink-subtle)"
        />
        <span class="sk-meta">이미지 로드 실패</span>
        <button
          type="button"
          class="inline-flex items-center gap-1 rounded-(--sk-r-sidebar) border border-(--sk-border) px-2 py-0.5 font-mono text-[10px] text-(--sk-ink-muted) transition-colors hover:text-(--sk-ink)"
          @click="retry"
        >
          <UIcon
            name="i-lucide-rotate-ccw"
            class="h-3 w-3"
          />
          재시도
        </button>
      </div>

      <!-- No image on this site — the evidence row stays. -->
      <div
        v-else
        class="flex h-full flex-col items-center justify-center gap-1 text-center"
      >
        <UIcon
          name="i-lucide-image-off"
          class="h-5 w-5 text-(--sk-ink-subtle)"
        />
        <span class="sk-meta">이미지 없음</span>
      </div>

      <!-- Reason chips (evidence axis). -->
      <div class="absolute top-1 left-1 flex flex-wrap gap-0.5">
        <span
          v-for="reason in entry.reasons"
          :key="reason"
          class="rounded-(--sk-r-sidebar) px-1 py-0.5 font-mono text-[9px] font-semibold shadow-sm backdrop-blur-sm"
          :class="roleClass(REASON_META[reason].role)"
        >{{ REASON_META[reason].label }}</span>
      </div>

      <!-- Vendor monitoring badge — SEPARATE axis (never a verdict). -->
      <div class="absolute top-1 right-1 flex flex-col items-end gap-0.5">
        <span
          v-if="entry.monitor?.low"
          class="rounded-(--sk-r-sidebar) bg-(--sk-surface)/85 px-1 py-0.5 font-mono text-[9px] text-(--sk-ink-muted) shadow-sm backdrop-blur-sm"
          title="취득 점수 모니터링(판정 아님)"
        >취득↓</span>
        <span
          v-if="isTiff"
          class="rounded-(--sk-r-sidebar) bg-(--sk-surface)/85 px-1 py-0.5 font-mono text-[9px] text-(--sk-ink-muted) shadow-sm backdrop-blur-sm"
          title="TIFF 원본 — 미리보기는 변환본, 원본은 뷰어에서 다운로드"
        >TIFF</span>
      </div>
    </div>

    <!-- Caption: chip/MP, sequence, value, residual. -->
    <figcaption class="flex flex-col gap-0.5 border-t border-(--sk-border-soft) px-1.5 py-1">
      <div class="flex items-center justify-between gap-1">
        <button
          type="button"
          class="truncate font-mono text-[11px] font-medium text-(--sk-ink) hover:text-(--sk-accent)"
          :title="`chip ${entry.chip} 로 이동`"
          @click="emit('focus')"
        >
          {{ entry.chip }}
        </button>
        <span class="shrink-0 sk-meta">seq {{ entry.sequence }}</span>
      </div>
      <div class="flex items-center justify-between gap-1 sk-meta">
        <span class="tabular-nums">
          {{ entry.value != null ? entry.value.toFixed(2) : '—' }}<span
            v-if="entry.unit"
            class="ml-0.5"
          >{{ entry.unit }}</span>
        </span>
        <span
          v-if="entry.residual != null"
          class="tabular-nums"
        >Δ{{ entry.residual >= 0 ? '+' : '' }}{{ entry.residual.toFixed(2) }}</span>
      </div>
    </figcaption>
  </figure>
</template>

<script setup lang="ts">
import { isTiffName } from '~/utils/imageKind'
import { REASON_META, type ReviewEntry } from '~/utils/skewvoirAnalysis/gallery'

const props = defineProps<{
  entry: ReviewEntry
  src: string | null
  focused?: boolean
}>()
const emit = defineEmits<{ open: [], focus: [] }>()

const isTiff = computed(() => isTiffName(props.entry.image))

// Per-image load state, LOCAL to this card so a sibling's failure never
// touches this one (acceptance: independent per-image). Load failures
// auto-retry on a short backoff first — on the cloud a cold image's first
// request can be 502'd by the ingress while Flask completes the fetch into
// the MinIO cache — and only an exhausted budget shows the manual 재시도.
const loaded = ref(false)
const { src, onError, exhausted: failed, reset: retry } = useAutoRetrySrc(() => props.src)

// One watch covers both resets: `src` changes on a new image AND on every
// retry re-request, and `loaded` may only be true for the current src.
watch(src, () => {
  loaded.value = false
})

const roleClass = (role: 'bad' | 'warn' | 'muted'): string => {
  if (role === 'bad') return 'bg-(--sk-bad)/90 text-white'
  if (role === 'warn') return 'bg-(--sk-warn)/90 text-black'
  return 'bg-(--sk-surface)/85 text-(--sk-ink-muted)'
}
</script>
