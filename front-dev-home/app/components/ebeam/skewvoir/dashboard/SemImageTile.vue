<template>
  <!-- One tile of the 전체 보기 grid. Owns its own load/retry state so a
       transient failure on one sub-image (ingress 502 on a cold fetch, a 503
       from a busy tool) reloads on the same 2.5s/5s budget the single-image
       panel and the gallery cards already use — before this the grid was a
       bare <img>, and one failed tile stayed blank until a page refresh. -->
  <button
    v-if="!failed"
    type="button"
    class="relative block h-full w-full cursor-zoom-in"
    :aria-label="`이미지 ${label} 확대해서 보기`"
    @click="emit('open')"
  >
    <!-- Hidden until it paints: `alt` is the filename, and a pending or
         retrying <img> renders it as a wall of text. -->
    <img
      :src="displaySrc ?? undefined"
      :alt="name"
      loading="lazy"
      decoding="async"
      class="h-full w-full object-cover"
      :class="loaded ? undefined : 'opacity-0'"
      @load="loaded = true"
      @error="onError"
    >
    <div
      v-if="!loaded"
      class="pointer-events-none absolute inset-0 flex items-center justify-center"
    >
      <UIcon
        name="i-lucide-loader-circle"
        class="h-4 w-4 animate-spin text-(--sk-ink-subtle)"
      />
    </div>
  </button>
  <div
    v-else
    class="flex h-full flex-col items-center justify-center gap-1.5 px-2 text-center"
  >
    <UIcon
      name="i-lucide-image-off"
      class="h-5 w-5 text-(--sk-ink-subtle)"
    />
    <span class="sk-meta">이미지 로드 실패</span>
    <button
      type="button"
      class="inline-flex items-center gap-1 rounded-(--sk-r-sidebar) border border-(--sk-border) px-2 py-0.5 font-mono text-xs text-(--sk-ink-muted) transition-colors hover:text-(--sk-ink)"
      @click="retry"
    >
      <UIcon
        name="i-lucide-refresh-cw"
        class="h-3 w-3"
      />
      재시도
    </button>
  </div>
</template>

<script setup lang="ts">
const props = defineProps<{ src: string, name: string, label: string }>()
const emit = defineEmits<{ open: [] }>()

const { src: displaySrc, onError, exhausted: failed, reset } = useAutoRetrySrc(() => props.src)
const loaded = ref(false)
watch(() => props.src, () => {
  loaded.value = false
})
const retry = () => {
  loaded.value = false
  reset()
}
</script>
