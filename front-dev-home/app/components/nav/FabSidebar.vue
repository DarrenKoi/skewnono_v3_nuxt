<script setup lang="ts">
const { fab, favorites, recent, navigateToFab } = useNavigation()
const { fabs } = useToolData()

const sidebarCollapsed = ref(false)

const fabItems = computed(() => fabs.map(f => ({
  id: f.id,
  label: f.label,
  active: fab.value === f.id,
  hasAlerts: f.hasAlerts
})))
</script>

<template>
  <aside
    class="bg-gray-50 dark:bg-gray-900 border-r border-gray-200 dark:border-gray-700 flex flex-col transition-all duration-200"
    :class="sidebarCollapsed ? 'w-16' : 'w-48'"
  >
    <div class="p-3 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between">
      <span v-if="!sidebarCollapsed" class="text-xs font-semibold text-gray-500 uppercase tracking-wider">
        FAB
      </span>
      <button
        class="p-1 rounded hover:bg-gray-200 dark:hover:bg-gray-700"
        @click="sidebarCollapsed = !sidebarCollapsed"
      >
        <UIcon
          :name="sidebarCollapsed ? 'i-lucide-panel-left-open' : 'i-lucide-panel-left-close'"
          class="w-4 h-4 text-gray-500"
        />
      </button>
    </div>

    <nav class="flex-1 overflow-y-auto p-2">
      <!-- Favorites Section -->
      <div v-if="favorites.length > 0 && !sidebarCollapsed" class="mb-4">
        <div class="flex items-center gap-2 px-2 py-1 text-xs font-medium text-gray-500">
          <UIcon name="i-lucide-star" class="w-3 h-3" />
          <span>Favorites</span>
        </div>
        <div
          v-for="fav in favorites.slice(0, 5)"
          :key="fav"
          class="px-3 py-1.5 text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-700 rounded cursor-pointer"
        >
          {{ fav }}
        </div>
      </div>

      <!-- Recent Section -->
      <div v-if="recent.length > 0 && !sidebarCollapsed" class="mb-4">
        <div class="flex items-center gap-2 px-2 py-1 text-xs font-medium text-gray-500">
          <UIcon name="i-lucide-clock" class="w-3 h-3" />
          <span>Recent</span>
        </div>
        <div
          v-for="rec in recent.slice(0, 5)"
          :key="rec"
          class="px-3 py-1.5 text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-700 rounded cursor-pointer"
        >
          {{ rec }}
        </div>
      </div>

      <!-- Divider -->
      <div v-if="(favorites.length > 0 || recent.length > 0) && !sidebarCollapsed" class="border-t border-gray-200 dark:border-gray-700 my-2" />

      <!-- Fab List -->
      <div
        v-for="item in fabItems"
        :key="item.id"
        class="flex items-center gap-2 px-3 py-2 rounded cursor-pointer transition-colors"
        :class="item.active
          ? 'bg-primary-100 dark:bg-primary-900/30 text-primary-700 dark:text-primary-300'
          : 'text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700'"
        @click="navigateToFab(item.id)"
      >
        <span v-if="!sidebarCollapsed" class="text-sm font-medium">{{ item.label }}</span>
        <span v-else class="text-xs font-medium">{{ item.label.substring(0, 3) }}</span>
        <UIcon
          v-if="item.hasAlerts && !sidebarCollapsed"
          name="i-lucide-circle"
          class="w-2 h-2 text-amber-500 fill-current ml-auto"
        />
      </div>
    </nav>
  </aside>
</template>
