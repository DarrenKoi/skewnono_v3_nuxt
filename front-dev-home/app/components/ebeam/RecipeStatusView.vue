<template>
  <div class="space-y-3">
    <EbeamMetaBar
      :eyebrow="`${toolLabel} · ${fabs.join(' + ')}`"
      title="Recipe 현황"
    >
      <template #toggle>
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
      </template>
    </EbeamMetaBar>

    <!-- KeepAlive stays outside Suspense so a new tab root can trigger the
         fallback while cached views retain filters, table state, and data.
         Align/Meas share one FailIssueView instance (only section changes). -->
    <KeepAlive>
      <Suspense :timeout="0">
        <EbeamRecipeTatView
          v-if="activeTab === 'tat'"
          v-model:include-today="includeToday"
          :fabs="fabs"
          :tool-label="toolLabel"
          :tool-type="toolType"
        />
        <EbeamFailIssueView
          v-else
          v-model:include-today="includeToday"
          :fabs="fabs"
          :tool-label="toolLabel"
          :tool-type="toolType"
          :section="activeTab"
        />

        <template #fallback>
          <AppLoadingState title="Recipe 현황 데이터를 불러오는 중입니다." />
        </template>
      </Suspense>
    </KeepAlive>
  </div>
</template>

<script setup lang="ts">
import type { FailIssueToolType } from '~/composables/useFailIssueApi'
import { matchFeatureFromPath } from '~/utils/features'

defineProps<{
  fabs: string[]
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

// The URL is the single source of truth for the active tab. The useState only
// remembers the last-viewed tab (same policy as the hardware page's section
// tabs) as the fallback when a navigation arrives without ?tab=.
const lastTab = useState<RecipeStatusTab>('recipe-status-tab', () => 'tat')

// Chart-only display preference. It is shared across the three kept-alive
// views for this page visit but deliberately resets on reload/re-entry.
const includeToday = ref(false)

const queryTab = computed(() => {
  const raw = Array.isArray(route.query.tab) ? route.query.tab[0] : route.query.tab
  return isTab(raw) ? raw : null
})

const activeTab = computed<RecipeStatusTab>(() => queryTab.value ?? lastTab.value)

watch(activeTab, (tab) => {
  lastTab.value = tab
}, { immediate: true })

// Keep the URL carrying the visible tab (shareable/reload-safe) without
// stacking history entries. Runs on mount (deep link without ?tab=) and when
// a same-route navigation drops or garbles the query. Path guard: this
// watcher must never rewrite the query of a route we are navigating away to.
watch(() => [route.path, route.query.tab] as const, ([path]) => {
  if (matchFeatureFromPath(path) !== 'recipe-status') return
  if (queryTab.value !== activeTab.value) {
    router.replace({ query: { ...route.query, tab: activeTab.value } })
  }
}, { immediate: true })

const selectTab = (tab: RecipeStatusTab) => {
  router.replace({ query: { ...route.query, tab } })
}
</script>
