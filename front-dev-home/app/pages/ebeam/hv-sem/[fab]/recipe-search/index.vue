<script setup lang="ts">
const { fabs } = useFabRoute('hv-sem')
</script>

<template>
  <AppAsyncBoundary title="Recipe 목록을 불러오는 중입니다.">
    <EbeamRecipeSearchView
      :fabs="fabs"
      tool-label="HV-SEM"
      tool-type="hv-sem"
    />
  </AppAsyncBoundary>
</template>
