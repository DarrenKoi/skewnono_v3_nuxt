<template>
  <div class="flex min-w-0 flex-col gap-1">
    <button
      type="button"
      class="relative mx-auto block aspect-square w-full max-w-[180px] cursor-zoom-in overflow-hidden rounded-md border border-zinc-300/70 bg-(--sk-field) p-0 dark:border-zinc-700"
      :aria-label="`${stage} 확대해서 보기`"
      @click="emit('open')"
    >
      <!--
        Loaded straight from the tool's own FTP server through recipe-image, as
        a plain <img> so the browser caches repeat views for free. `loading`
        defers the request until the thumbnail scrolls into view — a parameter
        with three images should not cost three round trips before it is looked
        at.
      -->
      <img
        v-if="src && !failed"
        :src="src"
        :alt="`${stage} (${name})`"
        loading="lazy"
        decoding="async"
        class="h-full w-full object-cover"
        @error="failed = true"
      >
      <div
        v-else
        class="flex h-full w-full items-center justify-center px-2 text-center font-mono text-xs text-white/45"
      >
        {{ failed ? '이미지를 불러오지 못했습니다' : '이미지 없음' }}
      </div>
      <span
        class="absolute top-1 left-1 rounded-sm px-1.5 py-px font-mono text-xs font-bold tracking-wider"
        :class="isMeas
          ? 'bg-(--sk-brand) text-(--sk-brand-fg)'
          : 'bg-(--sk-ink) text-(--sk-ink-fg)'"
      >{{ isMeas ? 'MEAS' : 'ADDR' }}</span>
      <!-- Which of a slot's several files this is. Absent for the usual
           one-file slot; a caller that already renders every file side by side
           (ParamSettings) leaves it unset too — the chip answers "which one am
           I NOT seeing", which only a single-thumbnail view has to ask. -->
      <span
        v-if="variant"
        class="absolute top-1 right-1 rounded-sm bg-(--sk-ink) px-1.5 py-px font-mono text-xs font-bold tracking-wider text-(--sk-ink-fg)"
      >{{ variant }}</span>
      <span class="absolute right-1.5 bottom-1 font-mono text-xs text-white/55">⤢</span>
    </button>
    <div class="text-center font-mono text-xs font-semibold text-zinc-900 dark:text-zinc-100">
      {{ label }}
    </div>
    <div class="truncate text-center font-mono text-xs text-(--sk-ink-muted)">
      {{ name || '—' }}
    </div>
    <div
      v-if="variantTotal && variantTotal > 1"
      class="text-center font-mono text-xs text-(--sk-ink-subtle)"
    >
      {{ variantTotal }}개 중 1개
    </div>
  </div>
</template>

<script setup lang="ts">
const props = defineProps<{
  /** Column name, e.g. `img_add1`. */
  label: string
  /** Human stage label, e.g. `Addressing 1`. */
  stage: string
  /** Filename in the raw-recipe folder, e.g. `IMMP0001.jpeg`. */
  name: string
  /** `recipe-image` URL, or empty when the slot names no file. */
  src: string
  role: 'address' | 'measure'
  /** Sub-position label when this thumbnail stands for ONE of a slot's several
   *  files (HV-SEM). Omitted when the slot names a single file. */
  variant?: string
  /** How many files that slot holds, so the caller can say what is hidden. */
  variantTotal?: number
}>()

const emit = defineEmits<{ (e: 'open'): void }>()

const isMeas = computed(() => props.role === 'measure')

// Reset per image: without this, one 404 would blank every thumbnail this
// component is subsequently reused for as the user clicks through parameters.
const failed = ref(false)
watch(() => props.src, () => {
  failed.value = false
})
</script>
