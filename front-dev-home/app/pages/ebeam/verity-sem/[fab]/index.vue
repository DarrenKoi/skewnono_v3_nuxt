<script setup lang="ts">
const route = useRoute()
const { setToolType, setFab } = useNavigation()

const fabName = computed(() => String(route.params.fab ?? '').toUpperCase())

const applyFab = (next: string) => {
  if (!next) return
  setFab(next)
}

setToolType('verity-sem')
applyFab(fabName.value)

watch(() => route.params.fab, (newFab) => {
  applyFab(String(newFab ?? '').toUpperCase())
})
</script>

<template>
  <AppAsyncBoundary title="장비 리스트를 불러오는 중입니다.">
    <EbeamToolInventoryView
      tool-type="verity-sem"
      :fab="fabName"
      :title="`VeritySEM - ${fabName}`"
      subtitle="Mocked backend inventory filtered by fab."
    />
  </AppAsyncBoundary>
</template>
