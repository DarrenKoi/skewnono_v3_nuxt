<template>
  <div class="space-y-3">
    <FabScopeNotice
      :fabs="fabs"
      :primary-fab="primaryFab"
    />
    <AppAsyncBoundary title="비교 데이터를 불러오는 중입니다.">
      <EbeamRecipeCompareView
        :fab="primaryFab"
        tool-label="CD-SEM"
        tool-type="cd-sem"
      />
    </AppAsyncBoundary>
  </div>
</template>

<script setup lang="ts">
const { fabs, primaryFab } = useFabRoute('cd-sem')
</script>
