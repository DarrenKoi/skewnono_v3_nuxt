<script setup lang="ts">
const { fabs } = useFabRoute('veritysem')
</script>

<template>
  <AppAsyncBoundary title="Recipe 현황 데이터를 불러오는 중입니다.">
    <EbeamRecipeUsageStatusView
      :fabs="fabs"
      tool-label="VeritySEM"
      tool-type="veritysem"
    />
  </AppAsyncBoundary>
</template>
