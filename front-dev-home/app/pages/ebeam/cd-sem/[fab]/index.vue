<script setup lang="ts">
const route = useRoute()
const { setToolType, setFab } = useNavigation()

const fabId = computed(() => String(route.params.fab ?? '').toUpperCase())

const applyFab = (next: string) => {
  if (!next) return
  setFab(next)
}

setToolType('cd-sem')
applyFab(fabId.value)

watch(() => route.params.fab, (newFab) => {
  applyFab(String(newFab ?? '').toUpperCase())
})
</script>

<template>
  <div class="space-y-3">
    <EbeamToolInventoryView
      tool-type="cd-sem"
      :fab="fabId"
      :title="`CD-SEM - ${fabId}`"
      subtitle="전산 시스템에 등록된 장비 기준으로 보여줍니다. 업데이트 주기: 1시간"
    >
      <template #below-title>
        <EbeamEquipmentStatusSubTabs />
      </template>
    </EbeamToolInventoryView>
  </div>
</template>
