<script setup lang="ts">
definePageMeta({
  layout: 'hub'
})

const { toolTypes } = useToolData()

const ebeamTools = toolTypes

const systemStatus = computed(() => {
  return ebeamTools.map(tool => ({
    ...tool,
    online: tool.count,
    total: tool.count
  }))
})
</script>

<template>
  <div class="max-w-6xl mx-auto px-4 py-8">
    <!-- Category Cards -->
    <div class="grid md:grid-cols-2 gap-6 mb-8">
      <!-- E-Beam Metrology Card -->
      <UCard
        :ui="{
          body: 'p-6'
        }"
      >
        <div class="flex items-start justify-between mb-4">
          <h2 class="text-xl font-semibold">E-Beam Metrology</h2>
          <UIcon name="i-lucide-microscope" class="w-6 h-6 text-primary-500" />
        </div>

        <nav class="space-y-2">
          <NuxtLink
            v-for="tool in ebeamTools"
            :key="tool.id"
            :to="`/ebeam/${tool.id}`"
            class="flex items-center justify-between p-3 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors group"
          >
            <span class="flex items-center gap-2">
              <UIcon name="i-lucide-arrow-right" class="w-4 h-4 text-gray-400 group-hover:text-primary-500 transition-colors" />
              <span class="font-medium">{{ tool.label }}</span>
            </span>
            <UBadge :label="String(tool.count)" color="neutral" variant="subtle" />
          </NuxtLink>
        </nav>
      </UCard>

      <!-- Thickness Metrology Card -->
      <UCard
        :ui="{
          body: 'p-6'
        }"
      >
        <div class="flex items-start justify-between mb-4">
          <h2 class="text-xl font-semibold">Thickness Metrology</h2>
          <UIcon name="i-lucide-ruler" class="w-6 h-6 text-gray-400" />
        </div>

        <div class="flex flex-col items-center justify-center h-32 text-gray-500">
          <UIcon name="i-lucide-construction" class="w-12 h-12 mb-2 text-gray-300" />
          <span class="text-sm">Coming Soon</span>
        </div>
      </UCard>
    </div>

    <!-- Quick Access Section -->
    <h3 class="text-lg font-semibold mb-4">Quick Access</h3>
    <div class="grid md:grid-cols-3 gap-4 mb-8">
      <!-- Favorites -->
      <UCard>
        <template #header>
          <div class="flex items-center gap-2">
            <UIcon name="i-lucide-star" class="w-4 h-4 text-amber-500" />
            <span class="font-medium">Favorites</span>
          </div>
        </template>

        <div class="text-sm text-gray-500 py-4 text-center">
          No favorites yet
        </div>
      </UCard>

      <!-- Recent -->
      <UCard>
        <template #header>
          <div class="flex items-center gap-2">
            <UIcon name="i-lucide-clock" class="w-4 h-4 text-blue-500" />
            <span class="font-medium">Recent</span>
          </div>
        </template>

        <div class="text-sm text-gray-500 py-4 text-center">
          No recent activity
        </div>
      </UCard>

      <!-- Alerts -->
      <UCard>
        <template #header>
          <div class="flex items-center gap-2">
            <UIcon name="i-lucide-alert-triangle" class="w-4 h-4 text-amber-500" />
            <span class="font-medium">Alerts</span>
          </div>
        </template>

        <div class="text-sm text-gray-500 py-4 text-center">
          No active alerts
        </div>
      </UCard>
    </div>

    <!-- System Status -->
    <h3 class="text-lg font-semibold mb-4">System Status</h3>
    <UCard>
      <div class="flex flex-wrap gap-6">
        <div
          v-for="status in systemStatus"
          :key="status.id"
          class="flex items-center gap-2"
        >
          <span class="w-2 h-2 rounded-full bg-green-500" />
          <span class="text-sm">
            <span class="font-medium">{{ status.label }}:</span>
            <span class="text-gray-600 dark:text-gray-400"> {{ status.online }}/{{ status.total }}</span>
          </span>
        </div>
      </div>
    </UCard>
  </div>
</template>
