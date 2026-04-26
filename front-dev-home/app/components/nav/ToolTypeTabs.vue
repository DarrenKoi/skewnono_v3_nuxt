<script setup lang="ts">
const { toolType, navigateToToolType } = useNavigation()
const { toolTypes } = useToolData()

const { data: semRows } = await useSemList()

const countsByToolType = computed(() => {
  const counts = new Map<string, number>()
  for (const row of semRows.value ?? []) {
    const toolType = classifyToolType(row.eqp_model_cd)
    if (!toolType) continue
    counts.set(toolType, (counts.get(toolType) ?? 0) + 1)
  }
  return counts
})

const toolsWithCounts = computed(() => toolTypes.map(tool => ({
  ...tool,
  count: countsByToolType.value.get(tool.id) ?? tool.count
})))
</script>

<template>
  <div class="px-4 md:px-6 lg:px-8 pt-4">
    <div class="max-w-7xl mx-auto">
      <nav
        aria-label="Tool type navigation"
        class="dashboard-surface rounded-full p-1.5 flex gap-1 overflow-x-auto"
      >
        <button
          v-for="tool in toolsWithCounts"
          :key="tool.id"
          :aria-pressed="toolType === tool.id"
          :aria-disabled="!tool.enabled"
          :disabled="!tool.enabled"
          type="button"
          class="flex shrink-0 items-center gap-2 px-4 py-2 text-sm font-medium rounded-full transition-colors duration-200"
          :class="toolType === tool.id
            ? 'bg-zinc-900 text-zinc-100 dark:bg-zinc-100 dark:text-zinc-900 sk-nav-accent'
            : !tool.enabled
              ? 'text-zinc-400 ring-1 ring-zinc-200/70 cursor-not-allowed dark:text-zinc-500 dark:ring-zinc-700/80'
              : 'text-zinc-600 ring-1 ring-zinc-200/80 hover:text-zinc-900 hover:bg-zinc-50 dark:text-zinc-400 dark:ring-zinc-700 dark:hover:text-zinc-100 dark:hover:bg-zinc-800/60'"
          @click="navigateToToolType(tool.id)"
        >
          {{ tool.label }}
          <UBadge
            :label="String(tool.count)"
            size="xs"
            class="rounded-full"
            :color="toolType === tool.id ? 'primary' : tool.enabled ? 'neutral' : 'warning'"
            variant="subtle"
          />
        </button>
      </nav>
    </div>
  </div>
</template>
