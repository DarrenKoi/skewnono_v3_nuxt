<script setup lang="ts">
const { toolType, navigateToToolType } = useNavigation()
const { toolTypes } = useToolData()
</script>

<template>
  <div class="border-b border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900">
    <div class="max-w-7xl mx-auto px-4">
      <nav class="flex gap-1 py-2">
        <button
          v-for="tool in toolTypes"
          :key="tool.id"
          class="flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-md transition-colors"
          :class="toolType === tool.id
            ? 'bg-white dark:bg-gray-800 text-primary-600 dark:text-primary-400 shadow-sm'
            : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-800'"
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
