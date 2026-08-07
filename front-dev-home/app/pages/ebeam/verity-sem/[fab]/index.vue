<script setup lang="ts">
const { fabs, primaryFab } = useFabRoute('verity-sem')
</script>

<template>
  <AppAsyncBoundary title="장비 리스트를 불러오는 중입니다.">
    <EbeamToolInventoryView
      tool-type="verity-sem"
      :fab="primaryFab"
      :title="`VeritySEM - ${fabs.join(' + ')}`"
      subtitle="Mocked backend inventory filtered by fab."
    />
  </AppAsyncBoundary>
</template>
