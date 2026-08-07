<script setup lang="ts">
const { fabs } = useFabRoute('cd-sem')
</script>

<template>
  <AppAsyncBoundary title="비교 데이터를 불러오는 중입니다.">
    <EbeamRecipeCompareView
      :fabs="fabs"
      tool-label="CD-SEM"
      tool-type="cd-sem"
    />
  </AppAsyncBoundary>
</template>
