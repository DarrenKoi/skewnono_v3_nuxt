<script setup lang="ts">
import type { ToolType } from '~/stores/navigation'

const { toolType, fabs, favorites, navigateToToolType, navigateToFab, toggleFab } = useNavigation()
const { toolTypes } = useToolData()

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
const systemNavId = 'fab-sidebar-system'

const { data: semRows } = await useSemList()
const fabNames = computed(() => extractFabNames(semRows.value ?? []))

const fabItems = computed(() => fabNames.value.map(name => ({
  id: name,
  label: name,
  active: fabs.value.includes(name)
})))

// 일반 클릭 = 단독 선택(기존 습관 유지), Cmd/Ctrl+클릭 = 추가·제거.
const onFabClick = (event: MouseEvent, id: string) => {
  if (event.metaKey || event.ctrlKey) toggleFab(id)
  else navigateToFab(id)
}

const countsByToolType = computed(() => {
  const counts = new Map<string, number>()
  for (const row of semRows.value ?? []) {
    const t = classifyToolType(row.eqp_model_cd)
    if (!t) continue
    counts.set(t, (counts.get(t) ?? 0) + 1)
  }
  return counts
})

const TOOL_SHORT: Record<ToolType, string> = {
  'cd-sem': 'CD',
  'hv-sem': 'HV',
  'veritysem': 'VS',
  'provision': 'PR'
}

const toolItems = computed(() => toolTypes.map(tool => ({
  ...tool,
  short: TOOL_SHORT[tool.id],
  count: countsByToolType.value.get(tool.id) ?? tool.count,
  active: toolType.value === tool.id
})))

const activeToolLabel = computed(() =>
  toolTypes.find(t => t.id === toolType.value)?.label ?? ''
)
</script>

<template>
  <aside
    class="dashboard-surface border-r border-zinc-200/70 dark:border-zinc-800/70 flex flex-col transition-all duration-200 ml-3 md:ml-4 lg:ml-5 mt-4 mb-4 rounded-2xl overflow-hidden shrink-0"
    :class="sidebarCollapsed ? 'w-16' : 'w-52'"
  >
    <div class="px-2 py-2.5 border-b border-zinc-200/70 dark:border-zinc-800/70 flex items-center justify-between">
      <span
        v-if="!sidebarCollapsed"
        class="text-[10px] font-semibold text-(--sk-ink-muted) uppercase tracking-[0.14em] pl-1.5"
      >
        장비모델
      </span>
      <button
        :aria-expanded="!sidebarCollapsed"
        :aria-label="sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'"
        :aria-controls="sidebarNavId"
        type="button"
        class="p-1.5 rounded-lg text-(--sk-ink-muted) hover:text-zinc-900 dark:hover:text-zinc-100 hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors"
        :class="sidebarCollapsed ? 'mx-auto' : ''"
        @click="sidebarCollapsed = !sidebarCollapsed"
      >
        <UIcon
          :name="sidebarCollapsed ? 'i-lucide-panel-left-open' : 'i-lucide-panel-left-close'"
          class="w-4 h-4"
        />
      </button>
    </div>

    <nav
      :id="systemNavId"
      aria-label="Tool type navigation"
      class="p-1.5 flex flex-col gap-1"
    >
      <button
        v-for="tool in toolItems"
        :key="tool.id"
        :aria-label="sidebarCollapsed ? tool.label : undefined"
        :aria-pressed="tool.active"
        :aria-disabled="!tool.enabled || undefined"
        :disabled="!tool.enabled"
        :title="sidebarCollapsed ? tool.label : undefined"
        type="button"
        class="relative flex items-center rounded-lg transition-all duration-200 w-full"
        :class="[
          sidebarCollapsed ? 'justify-center px-0 py-2' : 'justify-between gap-2 px-3 py-1.5',
          tool.active
            ? 'bg-zinc-900 text-zinc-100 dark:bg-zinc-100 dark:text-zinc-900 font-semibold shadow-sm sk-fab-active'
            : 'text-zinc-700 dark:text-zinc-300 hover:bg-zinc-100 dark:hover:bg-zinc-800',
          !tool.enabled ? 'opacity-55 cursor-not-allowed' : 'cursor-pointer'
        ]"
        @click="tool.enabled && navigateToToolType(tool.id)"
      >
        <template v-if="sidebarCollapsed">
          <span class="text-[11px] font-semibold tracking-tight">{{ tool.short }}</span>
        </template>
        <template v-else>
          <span class="text-sm truncate">{{ tool.label }}</span>
          <span
            class="inline-flex items-center justify-center min-w-[22px] h-[18px] px-1.5 rounded text-[11px] font-semibold tabular-nums"
            :class="tool.active
              ? 'bg-white/15 text-zinc-100/90 dark:bg-zinc-900/15 dark:text-zinc-900/90'
              : tool.enabled
                ? 'bg-(--sk-border-soft) text-(--sk-ink-subtle)'
                : 'bg-(--sk-brand-soft) text-(--sk-brand-ink)'"
          >{{ tool.count }}</span>
        </template>
      </button>
    </nav>

    <div class="border-t border-zinc-200/70 dark:border-zinc-800/70">
      <div
        v-if="!sidebarCollapsed"
        class="px-3.5 pt-2 pb-1 text-[10px] font-semibold text-(--sk-ink-muted) uppercase tracking-[0.14em]"
      >
        Fab<span
          v-if="activeToolLabel"
          class="text-(--sk-ink-muted) normal-case font-medium tracking-normal"
        > · {{ activeToolLabel }}</span>
      </div>
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
        <div class="flex items-center gap-1.5 px-2 py-1 text-[10px] font-medium text-(--sk-ink-muted)">
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

      <div
        v-for="item in fabItems"
        :key="item.id"
        class="group/fab relative flex items-center rounded-lg transition-all duration-200 w-full"
        :class="item.active
          ? 'bg-zinc-900 text-zinc-100 dark:bg-zinc-100 dark:text-zinc-900 shadow-sm sk-fab-active'
          : 'text-zinc-700 dark:text-zinc-300 hover:bg-zinc-100 dark:hover:bg-zinc-800'"
      >
        <button
          :aria-label="sidebarCollapsed ? item.label : undefined"
          :aria-pressed="item.active"
          :title="sidebarCollapsed ? `${item.label} (Cmd/Ctrl+클릭: 추가 선택)` : undefined"
          type="button"
          class="flex items-center flex-1 min-w-0 cursor-pointer"
          :class="sidebarCollapsed ? 'justify-center px-0 py-2' : 'gap-2 px-3 py-1.5'"
          @click="onFabClick($event, item.id)"
        >
          <span
            v-if="!sidebarCollapsed"
            class="text-sm font-semibold tracking-wide tabular-nums truncate"
          >{{ item.label }}</span>
          <span
            v-else
            class="text-[11px] font-semibold tracking-tight"
          >{{ item.label }}</span>
        </button>
        <button
          v-if="!sidebarCollapsed"
          type="button"
          role="checkbox"
          :aria-checked="item.active"
          :aria-label="`${item.label} 다중 선택 토글`"
          class="mr-2 flex items-center justify-center w-4 h-4 rounded border transition-colors shrink-0"
          :class="item.active
            ? 'bg-white/20 border-white/40 dark:bg-zinc-900/20 dark:border-zinc-900/40 opacity-100'
            : 'border-(--sk-border-soft) opacity-0 group-hover/fab:opacity-100'"
          @click.stop="toggleFab(item.id)"
        >
          <UIcon
            v-if="item.active"
            name="i-lucide-check"
            class="w-3 h-3"
          />
        </button>
      </div>
    </nav>
  </aside>
</template>
