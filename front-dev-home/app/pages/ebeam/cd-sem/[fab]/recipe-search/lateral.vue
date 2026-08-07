<script setup lang="ts">
const { fabs, primaryFab } = useFabRoute('cd-sem')
</script>

<template>
  <div class="space-y-3">
    <FabScopeNotice
      :fabs="fabs"
      :primary-fab="primaryFab"
    />
    <AppAsyncBoundary title="Recipe 횡전개 정보를 불러오는 중입니다.">
      <EbeamRecipeLateralView
        :fab="primaryFab"
        tool-label="CD-SEM"
        tool-type="cd-sem"
      />
    </AppAsyncBoundary>
  </div>
</template>
