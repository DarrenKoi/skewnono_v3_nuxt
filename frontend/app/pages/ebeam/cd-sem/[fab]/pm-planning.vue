<template>
  <div />
</template>

<script setup lang="ts">
// PM 플래닝 merged into 장비간 스큐 (2026-09-01): it is the PM 튜닝 chip there,
// not a screen of its own. Redirect keeps old bookmarks/deep links working.
// Neither screen reads the query, so nothing is carried over.
definePageMeta({
  middleware: [
    to => navigateTo(
      { path: `/ebeam/cd-sem/${to.params.fab}/tttm` },
      { replace: true }
    )
  ]
})
</script>
