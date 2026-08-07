<script setup lang="ts">
const { fabs } = useFabRoute('provision')
</script>

<template>
  <AppAsyncBoundary title="장비 리스트를 불러오는 중입니다.">
    <EbeamToolInventoryView
      tool-type="provision"
      :fabs="fabs"
      :title="`Provision - ${fabs.join(' + ')}`"
      subtitle="Mocked backend inventory filtered by fab."
    />
  </AppAsyncBoundary>
</template>
