<script setup lang="ts">
import type { Fab } from '~/stores/navigation'

const route = useRoute()
const { setToolType, setFab } = useNavigation()

const fabName = computed(() => String(route.params.fab ?? '').toUpperCase())

setToolType('hv-sem')
setFab(fabName.value as Fab)

watch(fabName, (next) => {
  setFab(next as Fab)
})
</script>

<template>
  <div class="space-y-3">
    <AppAsyncBoundary title="스토리지 정보를 불러오는 중입니다.">
      <EbeamStorageView
        :fab="fabName"
        tool-label="HV-SEM"
        tool-type="hv-sem"
      />
    </AppAsyncBoundary>
  </div>
</template>
