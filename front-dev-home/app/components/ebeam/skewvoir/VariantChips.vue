<template>
  <div
    class="flex flex-wrap items-center gap-1"
    role="group"
    aria-label="측정 이미지 선택"
  >
    <button
      v-for="(name, i) in names"
      :key="name"
      type="button"
      class="rounded-(--sk-r-sidebar) border px-2 py-0.5 font-mono text-[11px] font-medium transition-colors duration-200"
      :class="i === index
        ? 'border-(--sk-ink) bg-(--sk-ink) text-(--sk-ink-fg)'
        : 'border-(--sk-border) text-(--sk-ink-muted) hover:text-(--sk-ink)'"
      :aria-pressed="i === index"
      :aria-label="`이미지 ${imageVariantLabel(name, i)}`"
      @click="index = i"
    >
      {{ imageVariantLabel(name, i) }}
    </button>
  </div>
</template>

<script setup lang="ts">
// The sub-image switcher for a measurement point shot as several files
// (HV-SEM -U/-T/-M/-L). NAVIGATE family: it changes what is shown and narrows
// no data.
//
// One component because this was copied verbatim into the dashboard card, the
// gallery viewer and the position drawer, and the copies had already started
// to drift — two called the index `variantIndex`, one `selectedIndex`, one day
// after landing. Interactive markup with local state is the most expensive
// thing to triplicate: every keyboard, focus or aria fix would otherwise have
// to be made three times or silently not be.
//
// WHAT THIS DOES NOT OWN: when to show at all, and where the index comes from.
// Showing is context-specific — the dashboard hides the bar in 전체 mode while
// its outer header still gates on `names.length > 1`. The index is now the
// shared per-recipe+parameter memory (composables/useSkewvoirVariantMemory.ts),
// which every host binds through the same writable computed; before 2026-08-11
// each host instead owned a `ref(0)` and reset it on a different change, which
// is the behaviour that memory replaced.
import { imageVariantLabel } from '~/utils/imageKind'

defineProps<{ names: string[] }>()

/** Index into `names`. Bound by the host — normally to the remembered-variant
 * computed, which re-resolves it whenever `names` changes. */
const index = defineModel<number>({ required: true })
</script>
