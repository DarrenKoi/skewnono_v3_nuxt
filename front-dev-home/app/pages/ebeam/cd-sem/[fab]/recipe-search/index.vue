<script setup lang="ts">
const { fabs, primaryFab } = useFabRoute('cd-sem')
</script>

<template>
  <div class="space-y-3">
    <NavFabScopeNotice
      :fabs="fabs"
      :primary-fab="primaryFab"
    />
    <AppAsyncBoundary title="Recipe 목록을 불러오는 중입니다.">
      <EbeamRecipeSearchView
        :fab="primaryFab"
        tool-label="CD-SEM"
        tool-type="cd-sem"
      />
    </AppAsyncBoundary>
  </div>
</template>
