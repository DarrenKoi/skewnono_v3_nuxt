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
  <div class="px-4 md:px-6 lg:px-8 pt-4 pb-3 border-b border-(--sk-border-soft)">
    <div class="max-w-7xl mx-auto">
      <nav
        aria-label="Tool type navigation"
        class="flex gap-1 overflow-x-auto"
      >
        <SkNavPill
          v-for="tool in toolsWithCounts"
          :key="tool.id"
          :label="tool.label"
          :count="tool.count"
          :count-tone="tool.enabled ? 'neutral' : 'brand'"
          :active="toolType === tool.id"
          :disabled="!tool.enabled"
          size="md"
          @click="tool.enabled && navigateToToolType(tool.id)"
        />
      </nav>
    </div>
  </div>
</template>
