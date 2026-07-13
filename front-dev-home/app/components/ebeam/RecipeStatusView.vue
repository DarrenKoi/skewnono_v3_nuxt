<template>
  <div class="space-y-3">
    <!-- 내부 탭: TAT / Align Fail / Meas Fail -->
    <div
      role="tablist"
      aria-label="Recipe 현황 탭"
      class="inline-flex items-center gap-1 rounded-lg bg-zinc-100/70 p-1 dark:bg-zinc-800/60"
    >
      <button
        v-for="tab in TABS"
        :key="tab.value"
        type="button"
        role="tab"
        :aria-selected="activeTab === tab.value"
        class="inline-flex h-9 items-center gap-2 rounded-md px-4 text-sm font-semibold transition-colors"
        :class="activeTab === tab.value
          ? 'bg-white text-zinc-900 shadow-sm ring-1 ring-zinc-200/80 dark:bg-zinc-900 dark:text-zinc-50 dark:ring-zinc-700/80'
          : 'text-(--sk-ink-muted) hover:text-(--sk-ink)'"
        @click="selectTab(tab.value)"
      >
        <UIcon
          :name="tab.icon"
          class="h-4 w-4"
        />
        {{ tab.label }}
      </button>
    </div>

    <EbeamRecipeTatView
      v-if="activeTab === 'tat'"
      :fab="fab"
      :tool-label="toolLabel"
      :tool-type="toolType"
    />
    <!-- Align/Meas share one FailIssueView instance (only the section prop
         changes), so device/date filters survive switching between the two
         fail tabs. -->
    <EbeamFailIssueView
      v-else
      :fab="fab"
      :tool-label="toolLabel"
      :tool-type="toolType"
      :section="activeTab"
    />
  </div>
</template>

<script setup lang="ts">
import type { FailIssueToolType } from '~/composables/useFailIssueApi'

defineProps<{
  fab: string
  toolLabel: string
  toolType: FailIssueToolType
}>()

type RecipeStatusTab = 'tat' | 'align' | 'meas'

const TABS = [
  { value: 'tat', label: 'Recipe TAT', icon: 'i-lucide-timer' },
  { value: 'align', label: 'Align Fail', icon: 'i-lucide-crosshair' },
  { value: 'meas', label: 'Meas Fail', icon: 'i-lucide-image-off' }
] as const

const isTab = (v: unknown): v is RecipeStatusTab =>
  v === 'tat' || v === 'align' || v === 'meas'

const route = useRoute()
const router = useRouter()

// Last-viewed tab survives navigating away and back (same policy as the
// hardware page's section tabs); an explicit ?tab= deep link overrides it.
const activeTab = useState<RecipeStatusTab>('recipe-status-tab', () => 'tat')
const queryTab = Array.isArray(route.query.tab) ? route.query.tab[0] : route.query.tab
if (isTab(queryTab)) activeTab.value = queryTab

const selectTab = (tab: RecipeStatusTab) => {
  activeTab.value = tab
  // Keep the URL shareable without stacking history entries.
  router.replace({ query: { ...route.query, tab } })
}
</script>
