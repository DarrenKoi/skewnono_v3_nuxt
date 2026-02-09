<script setup lang="ts">
const { setCategory } = useNavigation()

onMounted(() => {
  setCategory('thickness')
})
</script>

<template>
  <div class="flex flex-col items-center justify-center min-h-[60vh]">
    <UIcon name="i-lucide-construction" class="w-24 h-24 mb-6 text-gray-300" />
    <h1 class="text-2xl font-bold mb-2">Thickness Metrology</h1>
    <p class="text-gray-500 mb-8">This module is coming soon</p>
    <NuxtLink to="/">
      <UButton color="primary" variant="outline">
        Return to Dashboard
      </UButton>
    </NuxtLink>
  </div>
</template>
