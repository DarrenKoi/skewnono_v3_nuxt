<script setup lang="ts">
const { fabs } = useFabRoute('cd-sem')
</script>

<template>
  <AppAsyncBoundary title="Recipe 목록을 불러오는 중입니다.">
    <EbeamRecipeSearchView
      :fabs="fabs"
      tool-label="CD-SEM"
      tool-type="cd-sem"
    />
  </AppAsyncBoundary>
</template>
