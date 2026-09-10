<script setup lang="ts">
const { ownerFab } = useRecipeDetailRouting('cd-sem')
</script>

<template>
  <AppAsyncBoundary title="Recipe 횡전개 정보를 불러오는 중입니다.">
    <EbeamRecipeLateralView
      :fab="ownerFab"
      tool-label="CD-SEM"
      tool-type="cd-sem"
    />
  </AppAsyncBoundary>
</template>
