<script setup lang="ts">
const { fabs, primaryFab } = useFabRoute('hv-sem')
</script>

<template>
  <div class="space-y-3">
    <FabScopeNotice
      :fabs="fabs"
      :primary-fab="primaryFab"
    />
    <AppAsyncBoundary title="Recipe 목록을 불러오는 중입니다.">
      <EbeamRecipeSearchView
        :fab="primaryFab"
        tool-label="HV-SEM"
        tool-type="hv-sem"
      />
    </AppAsyncBoundary>
  </div>
</template>
