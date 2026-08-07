<template>
  <div class="space-y-3">
    <NavFabScopeNotice
      :fabs="fabs"
      :primary-fab="primaryFab"
    />
    <EbeamSkewCheckView
      :fab="primaryFab"
      tool-label="CD-SEM"
      tool-type="cd-sem"
    />
  </div>
</template>

<script setup lang="ts">
const { fabs, primaryFab } = useFabRoute('cd-sem')
</script>
