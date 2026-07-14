<template>
  <div class="flex h-[calc(100dvh-7.5rem)] min-h-[36rem] flex-col overflow-hidden rounded-(--sk-r-card) border border-(--sk-border) bg-(--sk-canvas)">
    <EbeamSkewvoirWorkspaceTopBar :ws="ws" />

    <div class="flex min-h-0 flex-1">
      <EbeamSkewvoirWorkspaceLeftRail :ws="ws" />

      <main class="flex min-w-0 flex-1 flex-col">
        <!-- Main header: breadcrumb + view actions -->
        <div class="flex flex-wrap items-center justify-between gap-2 border-b border-(--sk-border) px-4 py-2.5">
          <div class="flex items-center gap-2.5">
            <p class="flex items-center gap-1.5 text-[13px] font-semibold text-zinc-800 dark:text-zinc-100">
              <span>{{ breadcrumb.head }}</span>
              <UIcon
                name="i-lucide-chevron-right"
                class="h-3.5 w-3.5 text-(--sk-ink-subtle)"
              />
              <span class="font-normal text-(--sk-ink-muted)">{{ breadcrumb.tail }}</span>
            </p>
            <USelect
              v-if="analysis.availableParams.value.length"
              :model-value="analysis.activeParam.value"
              :items="analysis.availableParams.value"
              size="xs"
              icon="i-lucide-ruler"
              class="min-w-[9rem]"
              @update:model-value="ws.setParam"
            />
          </div>

          <div class="flex items-center gap-1.5">
            <UButton
              v-for="action in actions"
              :key="action.label"
              color="neutral"
              variant="ghost"
              :icon="action.icon"
              :label="action.label"
              size="xs"
              @click="action.onClick?.()"
            />
          </div>
        </div>

        <!-- View body — the active analysis view, driven by the URL `view` param -->
        <div class="min-h-0 flex-1 overflow-auto p-3">
          <div
            v-if="!ws.selection.value"
            class="flex h-full flex-col items-center justify-center gap-3 py-20 text-center"
          >
            <span class="flex h-12 w-12 items-center justify-center rounded-(--sk-r-card) bg-(--sk-chip-bg) text-(--sk-ink-muted)">
              <UIcon
                name="i-lucide-mouse-pointer-click"
                class="h-6 w-6"
              />
            </span>
            <div>
              <p class="text-[14px] font-semibold text-zinc-700 dark:text-zinc-200">
                분석할 측정을 먼저 선택하세요.
              </p>
              <p class="mt-0.5 text-[12px] text-(--sk-ink-muted)">
                검색에서 결과를 열면 이 워크스페이스가 해당 측정으로 채워집니다.
              </p>
            </div>
            <UButton
              color="neutral"
              variant="outline"
              icon="i-lucide-search"
              label="검색으로"
              size="sm"
              @click="ws.goSearch()"
            />
          </div>

          <template v-else>
            <EbeamSkewvoirViewsDashboard
              v-if="ws.activeKind.value === 'dashboard'"
              :analysis="analysis"
            />
            <EbeamSkewvoirViewsPositionStack
              v-else-if="ws.activeKind.value === 'position-stack'"
              :analysis="analysis"
            />
            <EbeamSkewvoirViewsTimeSeries
              v-else-if="ws.activeKind.value === 'time-series'"
              :ws="ws"
              :analysis="analysis"
            />
            <EbeamSkewvoirViewsCorrelation
              v-else-if="ws.activeKind.value === 'correlation'"
              :analysis="analysis"
            />
            <EbeamSkewvoirViewsGallery
              v-else
              :analysis="analysis"
            />
          </template>
        </div>
      </main>
    </div>

    <EbeamSkewvoirWorkspaceStatusBar :ws="ws" />
  </div>
</template>

<script setup lang="ts">
import type { MeasHistToolType } from '~/composables/useMeasHistApi'
import {
  skewvoirRecentItemId,
  toSkewvoirRecentMeasurement,
  type SkewvoirRecentMeasurement,
  type SkewvoirRecentMode
} from '~/utils/skewvoirRecent'

const props = defineProps<{
  toolLabel: string
  toolType: MeasHistToolType
}>()

const ws = useSkewvoirWorkspace(props.toolType, props.toolLabel)
const analysis = useSkewvoirAnalysis(ws)
const toast = useToast()

// Shared links bypass the landing page, so the workspace records the opened
// analysis too. If the landing page already wrote a rich single/group entry,
// reuse its metadata; candidate rows can enrich a deep-link placeholder once
// the measurement history finishes loading.
const recent = useSkewvoirRecentlyViewed(props.toolType)
const { anchor } = useMeasHistFacets(props.toolType)
const openedAt = new Date().toISOString()

watch(anchor, value => recent.setAnchor(value), { immediate: true })

const recordCurrentAnalysis = () => {
  const sel = ws.selection.value
  if (!sel?.msr) return

  const msrs = ws.msrList.value.length ? ws.msrList.value : [sel.msr]
  const mode: SkewvoirRecentMode = msrs.length > 1 || ws.activeKind.value === 'time-series'
    ? 'time-series'
    : 'single'
  const id = skewvoirRecentItemId(props.toolType, mode, msrs)
  const existing = recent.items.value.find(item => item.id === id)
  const previousByMsr = new Map(existing?.measurements.map(item => [item.msr, item]) ?? [])
  const rowByMsr = new Map(analysis.candidateRows.value.map(row => [row.msr, row]))

  const measurements = msrs.map<SkewvoirRecentMeasurement>((msr) => {
    const row = rowByMsr.get(msr)
    if (row) return toSkewvoirRecentMeasurement(row)
    const previous = previousByMsr.get(msr)
    if (previous) return previous
    if (msr === sel.msr) {
      return {
        msr,
        lot: sel.lot,
        recipe: sel.recipe,
        eq: sel.eq,
        fab: '',
        capturedAt: sel.capturedAt
      }
    }
    return { msr, lot: '', recipe: '', eq: '', fab: '', capturedAt: '' }
  })

  recent.record(mode, measurements, existing?.viewedAt ?? openedAt)
}

onMounted(recordCurrentAnalysis)
watch(analysis.candidateRows, (rows) => {
  if (rows.length) recordCurrentAnalysis()
})

// USelect/USelectMenu triggers render as <button role="combobox">, not <input>,
// so defineShortcuts' usingInput guard does NOT suppress digit keys while one is
// focused/open — a digit typed for option type-ahead would also switch the view.
const selectorFocused = (): boolean => {
  if (!import.meta.client) return false
  const el = document.activeElement
  if (!el) return false
  return el.getAttribute('role') === 'combobox'
    || el.getAttribute('aria-haspopup') === 'listbox'
    || !!el.closest('[role="listbox"]')
}

// Keys 1-5 jump to the matching left-rail view mode.
defineShortcuts(
  Object.fromEntries(
    ws.viewModes.map(mode => [String(mode.index), () => {
      if (selectorFocused()) return
      ws.openView(mode.kind)
    }])
  )
)

const BREADCRUMBS: Record<string, { head: string, tail: string }> = {
  'dashboard': { head: 'Dashboard', tail: 'Single Measurement' },
  'position-stack': { head: '위치 비교', tail: 'Position Stack' },
  'time-series': { head: 'Time-Series', tail: 'Multi-measurement Trend' },
  'correlation': { head: '상관 / 분포', tail: 'Correlation & Distribution' },
  'gallery': { head: '이미지 갤러리', tail: 'SEM Gallery' }
}

const breadcrumb = computed(() => BREADCRUMBS[ws.activeKind.value] ?? BREADCRUMBS.dashboard!)

const share = async () => {
  const url = ws.shareUrl()
  try {
    await navigator.clipboard.writeText(url)
    toast.add({ title: '링크가 복사되었습니다', description: url, icon: 'i-lucide-link', color: 'success' })
  } catch {
    toast.add({ title: '복사하지 못했습니다', description: url, icon: 'i-lucide-triangle-alert', color: 'warning' })
  }
}

const actions = [
  { label: '+ Annotate', icon: 'i-lucide-message-square-plus' },
  { label: 'Excel / CSV', icon: 'i-lucide-file-spreadsheet' },
  { label: 'Skew Check', icon: 'i-lucide-activity' },
  { label: 'Share', icon: 'i-lucide-share-2', onClick: share }
]
</script>
