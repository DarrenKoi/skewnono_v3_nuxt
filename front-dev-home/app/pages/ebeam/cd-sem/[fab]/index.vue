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
  <div class="h-full">
    <EbeamToolInventoryView
      tool-type="cd-sem"
      :fab="fabId"
      :eyebrow="`CD-SEM · ${fabId}`"
      title="장비 상태"
      subtitle="스큐노노가 현재 접근 가능한 장비 리스트입니다."
      cadence="1시간 주기"
    />
  </div>
</template>
