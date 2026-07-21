<script setup lang="ts">
const route = useRoute()
const { setToolType, setFab } = useNavigation()

const fabName = computed(() => String(route.params.fab ?? '').toUpperCase())

const applyFab = (next: string) => {
  if (!next) return
  setFab(next)
}

setToolType('hv-sem')
applyFab(fabName.value)

watch(() => route.params.fab, (newFab) => {
  applyFab(String(newFab ?? '').toUpperCase())
})
</script>

<template>
  <div class="h-full">
    <EbeamToolInventoryView
      tool-type="hv-sem"
      :fab="fabName"
      :eyebrow="`HV-SEM · ${fabName}`"
      title="장비 상태"
      subtitle="스큐노노가 현재 접근 가능한 장비 리스트입니다."
      cadence="1시간 주기"
    />
  </div>
</template>
