<template>
  <!-- The Korean-web "N" for an unread post. Text, not a coloured dot, so it never
       signals by colour alone; the hidden words are what a screen reader hears. -->
  <span class="notice-new-badge">
    <span aria-hidden="true">N</span>
    <span class="sr-only">새 공지</span>
  </span>
</template>

<style scoped>
/* Terracotta, the one non-semantic fill (DESIGN.md §Tags): "new" is not a verdict, and
   crimson is trim only. The smallest radius step, so 16px stays a soft square. */
.notice-new-badge {
  display: inline-flex;
  flex: none;
  align-items: center;
  justify-content: center;
  width: 16px;
  height: 16px;
  font-size: 11px;
  font-weight: 700;
  line-height: 1;
  border-radius: var(--sk-r-sidebar);
  background: var(--sk-brand);
  color: var(--sk-brand-fg);
}
</style>
