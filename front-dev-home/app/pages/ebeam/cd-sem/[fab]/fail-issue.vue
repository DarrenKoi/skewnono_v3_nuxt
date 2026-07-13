<template>
  <div />
</template>

<script setup lang="ts">
// Merged into Recipe 현황 — redirect keeps old bookmarks/deep links working.
definePageMeta({
  middleware: [
    to => navigateTo(
      { path: `/ebeam/cd-sem/${to.params.fab}/recipe-status`, query: { ...to.query, tab: 'align' } },
      { replace: true }
    )
  ]
})
</script>
