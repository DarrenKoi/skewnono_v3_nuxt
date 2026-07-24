<template>
  <div
    ref="viewport"
    class="relative select-none overflow-hidden"
    :class="scale > 1 ? (drag ? 'cursor-grabbing' : 'cursor-grab') : 'cursor-zoom-in'"
    @wheel.prevent="onWheel"
    @pointerdown="onPointerDown"
    @pointermove="onPointerMove"
    @pointerup="onPointerUp"
    @pointercancel="onPointerUp"
    @dblclick="scale > 1 ? reset() : zoomTo(2)"
  >
    <img
      :src="src"
      :alt="alt"
      draggable="false"
      class="pointer-events-none absolute inset-0 h-full w-full object-contain"
      :style="imgStyle"
      @error="emit('error')"
    >

    <!-- Zoom controls -->
    <div class="absolute right-2 bottom-2 flex items-center gap-0.5 rounded-(--sk-r-nav) border border-(--sk-border) bg-(--sk-surface)/90 p-0.5 shadow-sm backdrop-blur-sm">
      <button
        type="button"
        class="rounded-(--sk-r-sidebar) p-1 text-(--sk-ink-muted) transition-colors duration-200 hover:bg-(--sk-chip-bg) hover:text-(--sk-ink) disabled:opacity-40"
        aria-label="축소"
        :disabled="scale <= MIN"
        @click.stop="zoomBy(1 / STEP)"
      >
        <UIcon
          name="i-lucide-minus"
          class="h-4 w-4"
        />
      </button>
      <span class="w-9 text-center font-mono text-[11px] tabular-nums text-(--sk-ink-muted)">{{ Math.round(scale * 100) }}%</span>
      <button
        type="button"
        class="rounded-(--sk-r-sidebar) p-1 text-(--sk-ink-muted) transition-colors duration-200 hover:bg-(--sk-chip-bg) hover:text-(--sk-ink) disabled:opacity-40"
        aria-label="확대"
        :disabled="scale >= MAX"
        @click.stop="zoomBy(STEP)"
      >
        <UIcon
          name="i-lucide-plus"
          class="h-4 w-4"
        />
      </button>
      <button
        type="button"
        class="rounded-(--sk-r-sidebar) p-1 text-(--sk-ink-muted) transition-colors duration-200 hover:bg-(--sk-chip-bg) hover:text-(--sk-ink) disabled:opacity-40"
        aria-label="원래 크기"
        :disabled="scale === MIN"
        @click.stop="reset"
      >
        <UIcon
          name="i-lucide-rotate-ccw"
          class="h-4 w-4"
        />
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
// Pan + zoom an image inside its container. Wheel or the +/− controls zoom
// (toward the cursor for the wheel); drag pans once zoomed in; double-click
// toggles. transform-origin is the top-left so the cursor-anchored math is
// simple: keep the point under the cursor fixed while scaling.
const props = withDefaults(defineProps<{ src: string, alt?: string }>(), { alt: '' })
// Bubbled when the image itself fails to load (missing/failed file on the
// server) so the host can swap in an explicit "이미지 없음" placeholder.
const emit = defineEmits<{ error: [] }>()

const MIN = 1
const MAX = 6
const STEP = 1.4

const viewport = ref<HTMLElement | null>(null)
const scale = ref(1)
const tx = ref(0)
const ty = ref(0)
const drag = ref<{ x: number, y: number } | null>(null)

const imgStyle = computed(() => ({
  transform: `translate(${tx.value}px, ${ty.value}px) scale(${scale.value})`,
  transformOrigin: '0 0'
}))

const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v))

// Zoom to `target`, keeping the viewport point (px, py) fixed. Defaults to centre.
const zoomTo = (target: number, px?: number, py?: number) => {
  const el = viewport.value
  if (!el) return
  const rect = el.getBoundingClientRect()
  const cx = px ?? rect.width / 2
  const cy = py ?? rect.height / 2
  const next = clamp(target, MIN, MAX)
  const ratio = next / scale.value
  scale.value = next
  if (next === MIN) {
    tx.value = 0
    ty.value = 0
    return
  }
  tx.value = cx - (cx - tx.value) * ratio
  ty.value = cy - (cy - ty.value) * ratio
}
const zoomBy = (factor: number) => zoomTo(scale.value * factor)
const reset = () => {
  scale.value = MIN
  tx.value = 0
  ty.value = 0
}

const onWheel = (e: WheelEvent) => {
  const el = viewport.value
  if (!el) return
  const rect = el.getBoundingClientRect()
  zoomTo(scale.value * (e.deltaY < 0 ? STEP : 1 / STEP), e.clientX - rect.left, e.clientY - rect.top)
}

const onPointerDown = (e: PointerEvent) => {
  if (scale.value <= MIN) return
  drag.value = { x: e.clientX - tx.value, y: e.clientY - ty.value }
  ;(e.currentTarget as HTMLElement).setPointerCapture(e.pointerId)
}
const onPointerMove = (e: PointerEvent) => {
  if (!drag.value) return
  tx.value = e.clientX - drag.value.x
  ty.value = e.clientY - drag.value.y
}
const onPointerUp = (e: PointerEvent) => {
  drag.value = null
  try {
    (e.currentTarget as HTMLElement).releasePointerCapture(e.pointerId)
  } catch {
    // pointer capture may already be released
  }
}

// A new image starts fresh at fit-to-container.
watch(() => props.src, reset)
</script>
