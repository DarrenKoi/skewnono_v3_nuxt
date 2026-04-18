<script setup lang="ts">
const { toolType, navigateToToolType } = useNavigation()
const { activeToolTypes } = useToolData()
const { fetchSemList } = useSemListApi()

const { data: semRows } = await useAsyncData('sem-list-tool-types', () => fetchSemList())

const countsByToolType = computed(() => {
  const counts = new Map<string, number>()
  for (const row of semRows.value ?? []) {
    const toolType = classifyToolType(row.eqp_model_cd)
    if (!toolType) continue
    counts.set(toolType, (counts.get(toolType) ?? 0) + 1)
  }
  return counts
})

const toolsWithCounts = computed(() => activeToolTypes.map(tool => ({
  ...tool,
  count: countsByToolType.value.get(tool.id) ?? tool.count
})))
</script>

<template>
  <div class="px-4 md:px-6 lg:px-8 pt-4">
    <div class="max-w-7xl mx-auto">
      <nav
        aria-label="Tool type navigation"
        class="dashboard-surface rounded-2xl p-2 flex gap-1 overflow-x-auto"
      >
        <button
          v-for="tool in toolsWithCounts"
          :key="tool.id"
          :aria-pressed="toolType === tool.id"
          type="button"
          class="flex shrink-0 items-center gap-2 px-4 py-2 text-sm font-medium rounded-xl transition-all duration-200"
          :class="toolType === tool.id
            ? 'bg-zinc-900 text-zinc-100 dark:bg-zinc-100 dark:text-zinc-900 shadow-sm'
            : 'text-zinc-600 dark:text-zinc-400 hover:text-zinc-900 dark:hover:text-zinc-100 hover:bg-zinc-100/80 dark:hover:bg-zinc-800/60'"
          @click="navigateToToolType(tool.id)"
        >
          {{ tool.label }}
          <UBadge
            :label="String(tool.count)"
            size="xs"
            :color="toolType === tool.id ? 'primary' : 'neutral'"
            variant="subtle"
          />
        </button>
      </nav>
    </div>
  </div>
</template>
