<template>
  <div class="space-y-3">
    <NavFabScopeNotice
      :fabs="fabs"
      :primary-fab="primaryFab"
    />
    <AppAsyncBoundary title="PM 계획 데이터를 불러오는 중입니다.">
      <EbeamPmPlanningView
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
