<template>
  <div class="flex h-[calc(100dvh-7.5rem)] min-h-[36rem] flex-col overflow-hidden rounded-(--sk-r-card) border border-(--sk-border) bg-(--sk-canvas)">
    <EbeamSkewvoirWorkspaceTopBar :ws="ws" />

    <div class="flex min-h-0 flex-1">
      <EbeamSkewvoirWorkspaceLeftRail :ws="ws" />

      <main class="flex min-w-0 flex-1 flex-col">
        <!-- Main header: breadcrumb + view actions -->
        <div class="flex flex-wrap items-center justify-between gap-2 border-b border-(--sk-border) px-4 py-2.5">
          <p class="flex items-center gap-1.5 text-[13px] font-semibold text-zinc-800 dark:text-zinc-100">
            <span>{{ breadcrumb.head }}</span>
            <UIcon
              name="i-lucide-chevron-right"
              class="h-3.5 w-3.5 text-zinc-300"
            />
            <span class="font-normal text-zinc-500">{{ breadcrumb.tail }}</span>
          </p>

          <div class="flex items-center gap-1.5">
            <UButton
              v-for="action in actions"
              :key="action.label"
              :color="action.primary ? undefined : 'neutral'"
              :variant="action.primary ? 'solid' : 'ghost'"
              :class="action.primary ? 'bg-(--sk-ink) text-(--sk-ink-fg)' : ''"
              :icon="action.icon"
              :label="action.label"
              size="xs"
            />
          </div>
        </div>

        <!-- View body -->
        <div class="min-h-0 flex-1 overflow-auto p-3">
          <EbeamSkewvoirWorkspaceSearchView
            v-if="ws.activeKind.value === 'search'"
            :ws="ws"
          />
          <EbeamSkewvoirWorkspacePlaceholderView
            v-else
            :kind="ws.activeKind.value"
          />
        </div>
      </main>
    </div>

    <EbeamSkewvoirWorkspaceStatusBar :ws="ws" />
  </div>
</template>

<script setup lang="ts">
import type { MeasHistToolType } from '~/composables/useMeasHistApi'

const props = defineProps<{
  toolLabel: string
  toolType: MeasHistToolType
}>()

const ws = useSkewvoirWorkspace(props.toolType, props.toolLabel)

// Keys 1-6 jump to the matching left-rail view mode. usingInput defaults to
// false, so typing a digit inside the search box never switches views.
defineShortcuts(
  Object.fromEntries(
    ws.viewModes.map(mode => [String(mode.index), () => ws.openView(mode.kind)])
  )
)

const BREADCRUMBS: Record<string, { head: string, tail: string }> = {
  'search': { head: '검색', tail: 'Lot / Recipe' },
  'dashboard': { head: 'Dashboard', tail: 'Single Measurement' },
  'position-stack': { head: '위치 비교', tail: 'Position Stack' },
  'time-series': { head: 'Time-Series', tail: 'Multi-measurement Trend' },
  'correlation': { head: '상관 / 분포', tail: 'Correlation & Distribution' },
  'gallery': { head: '이미지 갤러리', tail: 'SEM Gallery' }
}

const breadcrumb = computed(() => BREADCRUMBS[ws.activeKind.value] ?? BREADCRUMBS.search!)

const actions = [
  { label: '+ Annotate', icon: 'i-lucide-message-square-plus', primary: false },
  { label: 'Excel / CSV', icon: 'i-lucide-file-spreadsheet', primary: false },
  { label: 'Skew Check', icon: 'i-lucide-activity', primary: false },
  { label: 'Share', icon: 'i-lucide-share-2', primary: false },
  { label: '+ Save view', icon: 'i-lucide-bookmark', primary: true }
]
</script>
