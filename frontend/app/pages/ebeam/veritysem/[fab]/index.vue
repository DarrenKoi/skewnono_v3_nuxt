<script setup lang="ts">
const { fabs } = useFabRoute('veritysem')
</script>

<template>
  <AppAsyncBoundary title="장비 리스트를 불러오는 중입니다.">
    <EbeamToolInventoryView
      tool-type="veritysem"
      :fabs="fabs"
      :title="`VeritySEM - ${fabs.join(' + ')}`"
      subtitle="스큐노노가 현재 접근 가능한 장비 리스트입니다."
    />
  </AppAsyncBoundary>
</template>
