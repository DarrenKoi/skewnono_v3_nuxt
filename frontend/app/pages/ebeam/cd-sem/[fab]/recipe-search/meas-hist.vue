<script setup lang="ts">
const { ownerFab } = useRecipeDetailRouting('cd-sem')
</script>

<template>
  <AppAsyncBoundary title="측정 이력을 불러오는 중입니다.">
    <EbeamRecipeMeasHistView
      :fab="ownerFab"
      tool-label="CD-SEM"
      tool-type="cd-sem"
    />
  </AppAsyncBoundary>
</template>
