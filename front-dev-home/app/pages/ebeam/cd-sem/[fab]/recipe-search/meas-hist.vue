<script setup lang="ts">
import { readRecipeOwnerFabQuery } from '~/utils/recipeView'

const { primaryFab } = useFabRoute('cd-sem')
const route = useRoute()
const ownerFab = computed(() => readRecipeOwnerFabQuery(route) || primaryFab.value)
</script>

<template>
  <AppAsyncBoundary title="측정 이력을 불러오는 중입니다.">
    <EbeamRecipeMeasHistView
      :fab="ownerFab"
      tool-label="CD-SEM"
      tool-type="cd-sem"
    />
  </AppAsyncBoundary>
</template>
