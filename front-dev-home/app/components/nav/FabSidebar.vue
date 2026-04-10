<script setup lang="ts">
const { fab, favorites, recent, navigateToFab } = useNavigation()
const { fabs } = useToolData()

const sidebarCollapsed = ref(false)
const sidebarNavId = 'fab-sidebar-navigation'

const fabItems = computed(() => fabs.map(f => ({
  id: f.id,
  label: f.label,
  active: fab.value === f.id,
  hasAlerts: f.hasAlerts
})))
</script>

<template>
  <aside
    class="dashboard-surface border-r border-zinc-200/70 dark:border-zinc-800/70 flex flex-col transition-all duration-200 ml-4 md:ml-6 lg:ml-8 mt-4 mb-4 rounded-2xl overflow-hidden"
    :class="sidebarCollapsed ? 'w-16' : 'w-52'"
  >
    <div class="px-3 py-3 border-b border-zinc-200/70 dark:border-zinc-800/70 flex items-center justify-between">
      <span v-if="!sidebarCollapsed" class="text-xs font-semibold text-zinc-500 dark:text-zinc-400 uppercase tracking-[0.14em]">
        FAB
      </span>
      <button
        :aria-expanded="!sidebarCollapsed"
        :aria-label="sidebarCollapsed ? 'Expand FAB sidebar' : 'Collapse FAB sidebar'"
        :aria-controls="sidebarNavId"
        type="button"
        class="p-1.5 rounded-lg text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100 hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors"
        @click="sidebarCollapsed = !sidebarCollapsed"
      >
        <UIcon
          :name="sidebarCollapsed ? 'i-lucide-panel-left-open' : 'i-lucide-panel-left-close'"
          class="w-4 h-4"
        />
      </button>
    </div>

    <nav :id="sidebarNavId" aria-label="FAB navigation" class="flex-1 overflow-y-auto p-2">
      <!-- Favorites Section -->
      <div v-if="favorites.length > 0 && !sidebarCollapsed" class="mb-4">
        <div class="flex items-center gap-2 px-2 py-1 text-xs font-medium text-zinc-500 dark:text-zinc-400">
          <UIcon name="i-lucide-star" class="w-3 h-3" />
          <span>Favorites</span>
        </div>
        <div
          v-for="fav in favorites.slice(0, 5)"
          :key="fav"
          class="px-3 py-2 text-sm text-zinc-600 dark:text-zinc-300 hover:bg-zinc-100 dark:hover:bg-zinc-800 rounded-lg transition-colors"
        >
          {{ fav }}
        </div>
      </div>

      <!-- Recent Section -->
      <div v-if="recent.length > 0 && !sidebarCollapsed" class="mb-4">
        <div class="flex items-center gap-2 px-2 py-1 text-xs font-medium text-zinc-500 dark:text-zinc-400">
          <UIcon name="i-lucide-clock" class="w-3 h-3" />
          <span>Recent</span>
        </div>
        <div
          v-for="rec in recent.slice(0, 5)"
          :key="rec"
          class="px-3 py-2 text-sm text-zinc-600 dark:text-zinc-300 hover:bg-zinc-100 dark:hover:bg-zinc-800 rounded-lg transition-colors"
        >
          {{ rec }}
        </div>
      </div>

      <!-- Divider -->
      <div v-if="(favorites.length > 0 || recent.length > 0) && !sidebarCollapsed" class="border-t border-zinc-200/70 dark:border-zinc-800/70 my-2" />

      <!-- Fab List -->
      <button
        v-for="item in fabItems"
        :key="item.id"
        :aria-label="sidebarCollapsed ? item.label : undefined"
        :aria-pressed="item.active"
        type="button"
        class="flex items-center gap-2 px-3 py-2.5 rounded-lg cursor-pointer transition-all duration-200"
        :class="item.active
          ? 'bg-zinc-900 text-zinc-100 dark:bg-zinc-100 dark:text-zinc-900 shadow-sm'
          : 'text-zinc-700 dark:text-zinc-300 hover:bg-zinc-100 dark:hover:bg-zinc-800'"
        @click="navigateToFab(item.id)"
      >
        <span v-if="!sidebarCollapsed" class="text-sm font-medium">{{ item.label }}</span>
        <span v-else class="text-[11px] font-semibold tracking-wide">{{ item.label.substring(0, 3) }}</span>
        <UIcon
          v-if="item.hasAlerts && !sidebarCollapsed"
          name="i-lucide-circle"
          class="w-2 h-2 text-zinc-500 fill-current ml-auto"
        />
      </button>
    </nav>
  </aside>
</template>
