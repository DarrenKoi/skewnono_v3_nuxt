<script setup lang="ts">
const { fabs, primaryFab } = useFabRoute('provision')
</script>

<template>
  <AppAsyncBoundary title="장비 리스트를 불러오는 중입니다.">
    <EbeamToolInventoryView
      tool-type="provision"
      :fab="primaryFab"
      :title="`Provision - ${fabs.join(' + ')}`"
      subtitle="Mocked backend inventory filtered by fab."
    />
  </AppAsyncBoundary>
</template>
