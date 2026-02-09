<script setup lang="ts">
const route = useRoute()
const { setToolType, setFab } = useNavigation()
const { fabs } = useToolData()

const fabId = computed(() => (route.params.fab as string).toUpperCase())

const fabConfig = computed(() => {
  return fabs.find(f => f.id === fabId.value) || { id: fabId.value, label: fabId.value }
})

onMounted(() => {
  setToolType('hv-sem')
  setFab(fabId.value as any)
})

watch(() => route.params.fab, (newFab) => {
  if (newFab) {
    setFab((newFab as string).toUpperCase() as any)
  }
})

const tools = computed(() => {
  return Array.from({ length: 8 }, (_, i) => ({
    id: `${fabId.value}-HVSEM-${String(i + 1).padStart(3, '0')}`,
    status: 'online',
    currentJob: Math.random() > 0.6 ? `JOB-${Math.floor(Math.random() * 1000)}` : null,
    lastUpdate: '1 min ago'
  }))
})
</script>

<template>
  <div>
    <div class="mb-6">
      <h1 class="text-2xl font-bold">HV-SEM - {{ fabConfig.label }}</h1>
      <p class="text-gray-600 dark:text-gray-400">Dashboard view</p>
    </div>

    <!-- Summary Cards -->
    <div class="grid md:grid-cols-4 gap-4 mb-8">
      <UCard>
        <div class="text-center">
          <div class="text-3xl font-bold text-primary-600">{{ tools.length }}</div>
          <div class="text-sm text-gray-500">Tools</div>
        </div>
      </UCard>
      <UCard>
        <div class="text-center">
          <div class="text-3xl font-bold text-green-600">
            {{ tools.filter(t => t.status === 'online').length }}
          </div>
          <div class="text-sm text-gray-500">Online</div>
        </div>
      </UCard>
      <UCard>
        <div class="text-center">
          <div class="text-3xl font-bold text-blue-600">
            {{ tools.filter(t => t.currentJob).length }}
          </div>
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

    <!-- Tool List -->
    <h2 class="text-lg font-semibold mb-4">Tools</h2>
    <UCard>
      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead>
            <tr class="border-b border-gray-200 dark:border-gray-700">
              <th class="text-left py-3 px-4 font-medium text-gray-500">Tool ID</th>
              <th class="text-left py-3 px-4 font-medium text-gray-500">Status</th>
              <th class="text-left py-3 px-4 font-medium text-gray-500">Current Job</th>
              <th class="text-left py-3 px-4 font-medium text-gray-500">Last Update</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="tool in tools"
              :key="tool.id"
              class="border-b border-gray-100 dark:border-gray-800 hover:bg-gray-50 dark:hover:bg-gray-800/50"
            >
              <td class="py-3 px-4 font-medium">{{ tool.id }}</td>
              <td class="py-3 px-4">
                <UBadge
                  :label="tool.status"
                  :color="tool.status === 'online' ? 'success' : 'error'"
                  variant="subtle"
                />
              </td>
              <td class="py-3 px-4 text-gray-600 dark:text-gray-400">
                {{ tool.currentJob || '-' }}
              </td>
              <td class="py-3 px-4 text-gray-500">{{ tool.lastUpdate }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </UCard>
  </div>
</template>
