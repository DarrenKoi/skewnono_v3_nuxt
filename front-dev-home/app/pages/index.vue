<script setup lang="ts">
definePageMeta({
  layout: 'hub'
})

const { toolTypes } = useToolData()
const { toolTypeHref } = useNavigation()

const { data: semRows } = await useSemList()

const rowsByToolType = computed(() => {
  const groups = new Map<string, typeof semRows.value>()
  for (const tool of toolTypes) {
    groups.set(tool.id, [])
  }

  for (const row of semRows.value ?? []) {
    const toolType = classifyToolType(row.eqp_model_cd)
    if (!toolType) continue
    groups.get(toolType)?.push(row)
  }

  return groups
})

const ebeamTools = computed(() => {
  return toolTypes.map(tool => ({
    ...tool,
    count: rowsByToolType.value.get(tool.id)?.length ?? tool.count
  }))
})

const todayLabel = useState('hub-today-label', () => new Intl.DateTimeFormat('ko-KR', {
  year: 'numeric',
  month: 'long',
  day: 'numeric'
}).format(new Date()))

const systemStatus = computed(() => {
  return ebeamTools.value
    .filter(tool => tool.enabled)
    .map((tool) => {
      const rows = rowsByToolType.value.get(tool.id) ?? []

      return {
        ...tool,
        online: rows.filter(row => row.available === 'On').length,
        total: rows.length
      }
    })
})
</script>

<template>
  <div class="max-w-7xl mx-auto px-4 md:px-6 lg:px-8 py-6 md:py-8 space-y-6">
    <section class="dashboard-surface rounded-3xl p-6 md:p-8">
      <div class="flex flex-col md:flex-row md:items-end md:justify-between gap-4">
        <div>
          <p class="text-xs uppercase tracking-[0.18em] text-zinc-500 dark:text-zinc-400 font-semibold mb-2">
            기반기술센터 SKEWNONO v3
          </p>
          <h1 class="text-2xl md:text-3xl font-semibold tracking-tight">
            - CD Metrology Solution -
          </h1>
        </div>
        <UBadge
          :label="todayLabel"
          color="neutral"
          variant="outline"
          class="w-fit"
        />
      </div>
    </section>

    <!-- Category Cards -->
    <div class="grid md:grid-cols-2 gap-6">
      <!-- E-Beam Metrology Card -->
      <UCard
        class="dashboard-surface rounded-3xl"
        :ui="{
          body: 'p-6'
        }"
      >
        <div class="flex items-start justify-between mb-4">
          <h2 class="text-xl font-semibold">
            E-Beam Metrology
          </h2>
          <UIcon
            name="i-lucide-microscope"
            class="w-6 h-6 text-zinc-700 dark:text-zinc-300"
          />
        </div>

        <nav class="space-y-2">
          <template
            v-for="tool in ebeamTools"
            :key="tool.id"
          >
            <NuxtLink
              v-if="tool.enabled"
              :to="toolTypeHref(tool.id)"
              class="flex items-center justify-between p-3 rounded-xl hover:bg-zinc-100 dark:hover:bg-zinc-800/80 transition-colors group"
            >
              <span class="flex items-center gap-2">
                <UIcon
                  name="i-lucide-arrow-right"
                  class="w-4 h-4 text-zinc-400 group-hover:text-zinc-800 dark:group-hover:text-zinc-200 transition-colors"
                />
                <span class="font-medium">
                  {{ tool.label }}
                </span>
              </span>
              <UBadge
                :label="String(tool.count)"
                color="neutral"
                variant="subtle"
              />
            </NuxtLink>
            <div
              v-else
              :aria-disabled="true"
              class="flex items-center justify-between p-3 rounded-xl text-zinc-400 dark:text-zinc-500 cursor-not-allowed"
            >
              <span class="flex items-center gap-2">
                <UIcon
                  name="i-lucide-construction"
                  class="w-4 h-4"
                />
                <span class="font-medium">
                  {{ tool.label }}
                </span>
              </span>
              <UBadge
                label="개발 예정"
                color="neutral"
                variant="soft"
              />
            </div>
          </template>
        </nav>
      </UCard>

      <!-- Thickness Metrology Card -->
      <UCard
        class="dashboard-surface rounded-3xl"
        :ui="{
          body: 'p-6'
        }"
      >
        <div class="flex items-start justify-between mb-4">
          <h2 class="text-xl font-semibold">
            Thickness Metrology
          </h2>
          <UIcon
            name="i-lucide-ruler"
            class="w-6 h-6 text-zinc-500"
          />
        </div>

        <div class="flex flex-col items-center justify-center h-32 text-zinc-500">
          <UIcon
            name="i-lucide-construction"
            class="w-12 h-12 mb-2 text-zinc-400"
          />
          <span class="text-sm">
            개발 예정
          </span>
        </div>
      </UCard>
    </div>

    <!-- Quick Access Section -->
    <h3 class="text-lg font-semibold">
      Quick Access
    </h3>
    <div class="grid md:grid-cols-3 gap-4">
      <!-- Favorites -->
      <UCard class="dashboard-surface rounded-3xl">
        <template #header>
          <div class="flex items-center gap-2">
            <UIcon
              name="i-lucide-star"
              class="w-4 h-4 text-zinc-500"
            />
            <span class="font-medium">
              Favorites
            </span>
          </div>
        </template>

        <div class="text-sm text-zinc-500 dark:text-zinc-400 py-4 text-center">
          No favorites yet
        </div>
      </UCard>

      <!-- Recent -->
      <UCard class="dashboard-surface rounded-3xl">
        <template #header>
          <div class="flex items-center gap-2">
            <UIcon
              name="i-lucide-clock"
              class="w-4 h-4 text-zinc-500"
            />
            <span class="font-medium">
              Recent
            </span>
          </div>
        </template>

        <div class="text-sm text-zinc-500 dark:text-zinc-400 py-4 text-center">
          No recent activity
        </div>
      </UCard>

      <!-- Alerts -->
      <UCard class="dashboard-surface rounded-3xl">
        <template #header>
          <div class="flex items-center gap-2">
            <UIcon
              name="i-lucide-alert-triangle"
              class="w-4 h-4 text-zinc-500"
            />
            <span class="font-medium">
              Alerts
            </span>
          </div>
        </template>

        <div class="text-sm text-zinc-500 dark:text-zinc-400 py-4 text-center">
          No active alerts
        </div>
      </UCard>
    </div>

    <!-- System Status -->
    <h3 class="text-lg font-semibold">
      System Status
    </h3>
    <UCard class="dashboard-surface rounded-3xl">
      <div class="flex flex-wrap gap-6">
        <div
          v-for="status in systemStatus"
          :key="status.id"
          class="flex items-center gap-2"
        >
          <span class="w-2 h-2 rounded-full bg-zinc-900 dark:bg-zinc-100" />
          <span class="text-sm">
            <span class="font-medium">{{ status.label }}:</span>
            <span class="text-zinc-600 dark:text-zinc-400"> {{ status.online }}/{{ status.total }}</span>
          </span>
        </div>
      </div>
    </UCard>
  </div>
</template>
