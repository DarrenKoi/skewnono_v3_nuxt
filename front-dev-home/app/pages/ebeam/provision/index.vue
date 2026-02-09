<script setup lang="ts">
const { setToolType, setFab } = useNavigation()

onMounted(() => {
  setToolType('provision')
  setFab('all')
})

const { fabs } = useToolData()

const fabStats = computed(() => {
  return fabs.filter(f => f.id !== 'all').map(fab => ({
    ...fab,
    toolCount: Math.floor(Math.random() * 3) + 1,
    activeJobs: Math.floor(Math.random() * 2),
    alerts: 0
  }))
})
</script>

<template>
  <div>
    <div class="mb-6">
      <h1 class="text-2xl font-bold">Provision Overview</h1>
      <p class="text-gray-600 dark:text-gray-400">All fabs - 12 tools</p>
    </div>

    <!-- Summary Cards -->
    <div class="grid md:grid-cols-4 gap-4 mb-8">
      <UCard>
        <div class="text-center">
          <div class="text-3xl font-bold text-primary-600">12</div>
          <div class="text-sm text-gray-500">Total Tools</div>
        </div>
      </UCard>
      <UCard>
        <div class="text-center">
          <div class="text-3xl font-bold text-green-600">12</div>
          <div class="text-sm text-gray-500">Online</div>
        </div>
      </UCard>
      <UCard>
        <div class="text-center">
          <div class="text-3xl font-bold text-blue-600">4</div>
          <div class="text-sm text-gray-500">Active Jobs</div>
        </div>
      </UCard>
      <UCard>
        <div class="text-center">
          <div class="text-3xl font-bold text-amber-600">0</div>
          <div class="text-sm text-gray-500">Alerts</div>
        </div>
      </UCard>
    </div>

    <!-- Fab Breakdown -->
    <h2 class="text-lg font-semibold mb-4">Fab Breakdown</h2>
    <div class="grid md:grid-cols-3 gap-4">
      <UCard
        v-for="fab in fabStats"
        :key="fab.id"
      >
        <div class="flex items-center justify-between mb-3">
          <h3 class="font-semibold">{{ fab.label }}</h3>
        </div>
        <div class="space-y-2 text-sm">
          <div class="flex justify-between">
            <span class="text-gray-500">Tools</span>
            <span class="font-medium">{{ fab.toolCount }}</span>
          </div>
          <div class="flex justify-between">
            <span class="text-gray-500">Active Jobs</span>
            <span class="font-medium">{{ fab.activeJobs }}</span>
          </div>
        </div>
        <div class="mt-4">
          <NuxtLink
            :to="`/ebeam/provision/${fab.id.toLowerCase()}`"
            class="text-sm text-primary-600 hover:text-primary-700 font-medium"
          >
            View Details →
          </NuxtLink>
        </div>
      </UCard>
    </div>
  </div>
</template>
