<template>
  <details class="group dashboard-surface rounded-[var(--sk-r-card)]">
    <summary
      class="flex cursor-pointer list-none items-center gap-2 px-4 py-3 [&::-webkit-details-marker]:hidden"
    >
      <UIcon
        name="i-lucide-chevron-right"
        class="h-3.5 w-3.5 text-(--sk-ink-muted) transition-transform duration-200 group-open:rotate-90"
      />
      <span class="sk-title">{{ title }}</span>
      <slot name="badge" />
      <span
        v-if="meta"
        class="ml-auto sk-meta"
      >{{ meta }}</span>
    </summary>

    <div class="border-t border-(--sk-border-soft) px-4 py-3">
      <slot />
    </div>
  </details>
</template>

<script setup lang="ts">
// A whole card that folds — the reference panels at the foot of the page (MDC
// 이력, 양산 정합도), as against `CaptionMore`, which folds a sentence inside a
// caption.
//
// Extracted because the two panels were byte-identical chrome around different
// bodies, and the proof arrived immediately: a review moved the chevron from
// `duration-150` to the documented `duration-200` and the same edit had to be
// applied twice. A third folded card would have been a third copy.
withDefaults(defineProps<{
  title: string
  /** Right-aligned summary line — enough to decide whether opening is worth it. */
  meta?: string
}>(), { meta: '' })
</script>
