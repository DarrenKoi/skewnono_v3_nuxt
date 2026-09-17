<template>
  <!-- Inline so it continues the caption's sentence rather than starting a
       block after it; the body below opens as its own line. -->
  <details class="inline">
    <!-- Underlined ink-muted, NOT the crimson the source mock used: DESIGN.md
         §Do's and Don'ts keeps `--sk-accent` to trim in three sanctioned spots
         and rules out crimson text outright. Underline is how the rest of this
         page (기본값으로) already says "clickable". -->
    <summary
      class="inline cursor-pointer list-none text-(--sk-ink-muted) underline underline-offset-2 hover:text-(--sk-ink) [&::-webkit-details-marker]:hidden"
    >
      {{ label }}
    </summary>
    <span class="mt-1.5 block leading-relaxed text-(--sk-ink-subtle)">
      <slot />
    </span>
  </details>
</template>

<script setup lang="ts">
defineProps<{ label: string }>()
</script>
