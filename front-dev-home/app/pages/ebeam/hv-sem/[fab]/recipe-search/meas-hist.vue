<script setup lang="ts">
const { ownerFab } = useRecipeDetailRouting('hv-sem')
</script>

<template>
  <AppAsyncBoundary title="측정 이력을 불러오는 중입니다.">
    <EbeamRecipeMeasHistView
      :fab="ownerFab"
      tool-label="HV-SEM"
      tool-type="hv-sem"
    />
  </AppAsyncBoundary>
</template>
