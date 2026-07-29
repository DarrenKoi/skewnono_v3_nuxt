<template>
  <div class="flex min-w-0 flex-col gap-1">
    <button
      type="button"
      class="relative mx-auto block aspect-square w-full max-w-[180px] cursor-zoom-in overflow-hidden rounded-md border border-zinc-300/70 bg-[#23201B] p-0 dark:border-zinc-700"
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
        class="flex h-full w-full items-center justify-center px-2 text-center font-mono text-[10px] text-white/45"
      >
        {{ failed ? '이미지를 불러오지 못했습니다' : '이미지 없음' }}
      </div>
      <span
        class="absolute top-1 left-1 rounded-sm px-1.5 py-px font-mono text-[11px] font-bold tracking-wider"
        :class="isMeas
          ? 'bg-(--sk-brand) text-(--sk-brand-fg)'
          : 'bg-(--sk-ink) text-(--sk-ink-fg)'"
      >{{ isMeas ? 'MEAS' : 'ADDR' }}</span>
      <span class="absolute right-1.5 bottom-1 font-mono text-[10px] text-white/55">⤢</span>
    </button>
    <div class="text-center font-mono text-[11px] font-semibold text-zinc-900 dark:text-zinc-100">
      {{ label }}
    </div>
    <div class="truncate text-center font-mono text-[11px] text-(--sk-ink-muted)">
      {{ name || '—' }}
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
