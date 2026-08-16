<template>
  <!-- Inline so it continues the caption's sentence rather than starting a
       block after it; the body below opens as its own line. -->
  <details class="inline">
    <summary
      class="inline cursor-pointer list-none text-(--sk-accent) [&::-webkit-details-marker]:hidden"
    >
      {{ label }}
    </summary>
    <span class="mt-1.5 block leading-relaxed text-(--sk-ink-subtle)">
      <slot />
    </span>
  </details>
</template>

<script setup lang="ts">
// The second paragraph of a caption, folded away until asked for.
//
// Four surfaces on this page carry an explanation that is genuinely needed the
// first time and pure noise on the tenth — what the map's axes are not, why the
// index ranks but does not judge, what the faint line on the residual track
// means. Printing all four leaves the page arguing with itself; deleting them
// leaves a metrology screen whose numbers cannot be checked. So they fold.
//
// A <details>, not a click-to-toggle ref: it keeps the text in the DOM for
// Ctrl-F and for the accessibility tree, and browsers already own the state.
withDefaults(defineProps<{ label?: string }>(), { label: '자세히' })
</script>
