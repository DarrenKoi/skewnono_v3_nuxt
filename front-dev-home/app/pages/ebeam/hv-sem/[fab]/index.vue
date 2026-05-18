<script setup lang="ts">
const route = useRoute()
const { setToolType, setFab } = useNavigation()

const fabId = computed(() => String(route.params.fab ?? '').toUpperCase())

const applyFab = (next: string) => {
  if (!next) return
  setFab(next)
}

setToolType('hv-sem')
applyFab(fabId.value)

watch(() => route.params.fab, (newFab) => {
  applyFab(String(newFab ?? '').toUpperCase())
})
</script>

<template>
  <div class="space-y-3">
    <EbeamToolInventoryView
      tool-type="hv-sem"
      :fab="fabId"
      :title="`HV-SEM - ${fabId}`"
      subtitle="스큐노노가 현재 접근 가능한 장비 리스트. 업데이트 주기 : 1 시간"
    >
      <template #below-title>
        <EbeamEquipmentStatusSubTabs />
      </template>
    </EbeamToolInventoryView>
  </div>
</template>
