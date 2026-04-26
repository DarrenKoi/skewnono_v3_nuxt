<script setup lang="ts">
const { fab, favorites, navigateToFab } = useNavigation()

const SIDEBAR_COLLAPSED_KEY = 'skewnono:fabSidebar.collapsed'

const sidebarCollapsed = ref(true)

onMounted(() => {
  try {
    const saved = localStorage.getItem(SIDEBAR_COLLAPSED_KEY)
    if (saved !== null) sidebarCollapsed.value = saved === '1'
  } catch { /* noop */ }
})

watch(sidebarCollapsed, (value) => {
  try {
    localStorage.setItem(SIDEBAR_COLLAPSED_KEY, value ? '1' : '0')
  } catch { /* noop */ }
})

const sidebarNavId = 'fab-sidebar-navigation'

const { data: semRows } = await useSemList()
const fabNames = computed(() => extractFabNames(semRows.value ?? []))

const fabItems = computed(() => fabNames.value.map(name => ({
  id: name,
  label: name,
  active: fab.value === name
})))
</script>

<template>
  <aside
    class="dashboard-surface border-r border-zinc-200/70 dark:border-zinc-800/70 flex flex-col transition-all duration-200 ml-3 md:ml-4 lg:ml-5 mt-4 mb-4 rounded-2xl overflow-hidden shrink-0"
    :class="sidebarCollapsed ? 'w-16' : 'w-44'"
  >
    <div class="px-2 py-2.5 border-b border-zinc-200/70 dark:border-zinc-800/70 flex items-center justify-between">
      <span
        v-if="!sidebarCollapsed"
        class="text-[10px] font-semibold text-zinc-500 dark:text-zinc-400 uppercase tracking-[0.14em] pl-1.5"
      >
        FAB
      </span>
      <button
        :aria-expanded="!sidebarCollapsed"
        :aria-label="sidebarCollapsed ? 'Expand FAB sidebar' : 'Collapse FAB sidebar'"
        :aria-controls="sidebarNavId"
        type="button"
        class="p-1.5 rounded-lg text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100 hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors mx-auto"
        @click="sidebarCollapsed = !sidebarCollapsed"
      >
        <UIcon
          :name="sidebarCollapsed ? 'i-lucide-panel-left-open' : 'i-lucide-panel-left-close'"
          class="w-4 h-4"
        />
      </button>
    </div>

    <nav
      :id="sidebarNavId"
      aria-label="FAB navigation"
      class="flex-1 overflow-y-auto p-1.5"
    >
      <div
        v-if="favorites.length > 0 && !sidebarCollapsed"
        class="mb-3"
      >
        <div class="flex items-center gap-1.5 px-2 py-1 text-[10px] font-medium text-zinc-500 dark:text-zinc-400">
          <UIcon
            name="i-lucide-star"
            class="w-3 h-3"
          />
          <span>Favorites</span>
        </div>
        <div
          v-for="fav in favorites.slice(0, 3)"
          :key="fav"
          class="px-2 py-1.5 text-xs text-zinc-600 dark:text-zinc-300 hover:bg-zinc-100 dark:hover:bg-zinc-800 rounded-md transition-colors truncate"
        >
          {{ fav }}
        </div>
      </div>

      <div
        v-if="favorites.length > 0 && !sidebarCollapsed"
        class="border-t border-zinc-200/70 dark:border-zinc-800/70 my-2"
      />

      <button
        v-for="item in fabItems"
        :key="item.id"
        :aria-label="sidebarCollapsed ? item.label : undefined"
        :aria-pressed="item.active"
        :title="sidebarCollapsed ? item.label : undefined"
        type="button"
        class="relative flex items-center rounded-lg cursor-pointer transition-all duration-200 w-full"
        :class="[
          sidebarCollapsed ? 'justify-center px-0 py-2' : 'gap-2 px-2.5 py-1.5',
          item.active
            ? 'bg-zinc-900 text-zinc-100 dark:bg-zinc-100 dark:text-zinc-900 shadow-sm sk-fab-active'
            : 'text-zinc-700 dark:text-zinc-300 hover:bg-zinc-100 dark:hover:bg-zinc-800'
        ]"
        @click="navigateToFab(item.id)"
      >
        <span
          v-if="!sidebarCollapsed"
          class="text-xs font-medium truncate"
        >{{ item.label }}</span>
        <span
          v-else
          class="text-[11px] font-semibold tracking-tight"
        >{{ item.label }}</span>
      </button>
    </nav>
  </aside>
</template>
