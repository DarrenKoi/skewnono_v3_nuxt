<script setup lang="ts">
const route = useRoute()
const { setToolType, setFab } = useNavigation()

const fabId = computed(() => (route.params.fab as string).toUpperCase())

onMounted(() => {
  setToolType('cd-sem')
  setFab(fabId.value as any)
})
</script>

<template>
  <div>
    <div class="mb-6">
      <h1 class="text-2xl font-bold">CD-SEM - {{ fabId }}</h1>
      <p class="text-gray-600 dark:text-gray-400">Real-time monitoring</p>
    </div>

    <UCard>
      <div class="flex flex-col items-center justify-center py-12 text-gray-500">
        <UIcon name="i-lucide-activity" class="w-16 h-16 mb-4 text-gray-300" />
        <p class="text-lg font-medium">Real-time Monitoring</p>
        <p class="text-sm">Charts and metrics will be displayed here</p>
      </div>
    </UCard>
  </div>
</template>
