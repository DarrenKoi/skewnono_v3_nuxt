<script setup lang="ts">
import { readRecipeOwnerFabQuery } from '~/utils/recipeView'

const { primaryFab } = useFabRoute('hv-sem')
const route = useRoute()
const ownerFab = computed(() => readRecipeOwnerFabQuery(route) || primaryFab.value)
</script>

<template>
  <AppAsyncBoundary title="측정 이력을 불러오는 중입니다.">
    <EbeamRecipeMeasHistView
      :fab="ownerFab"
      tool-label="HV-SEM"
      tool-type="hv-sem"
    />
  </AppAsyncBoundary>
</template>
