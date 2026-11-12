<script setup lang="ts">
const { fabs } = useFabRoute('provision')
</script>

<template>
  <AppAsyncBoundary title="Recipe 목록을 불러오는 중입니다.">
    <EbeamRecipeUsageSearchView
      :fabs="fabs"
      tool-label="Provision"
      tool-type="provision"
    />
  </AppAsyncBoundary>
</template>
