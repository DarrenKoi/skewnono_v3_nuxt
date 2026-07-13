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
            <UButton
              class="bg-(--sk-ink) text-(--sk-ink-fg)"
              icon="i-lucide-bookmark"
              label="Save view"
              size="xs"
              :disabled="!ws.selection.value"
              @click="openSave"
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

    <!-- Save view modal -->
    <UModal
      v-model:open="saveOpen"
      title="뷰 저장"
      description="현재 분석 화면을 이름을 붙여 저장합니다. 저장된 뷰는 링크로 다시 열 수 있습니다."
    >
      <template #body>
        <div class="space-y-3">
          <UInput
            v-model="saveName"
            placeholder="예: RK2W016.13 edge roll-off"
            autofocus
            class="w-full"
            @keydown.enter="confirmSave"
          />
          <p class="font-mono text-[11px] text-(--sk-ink-subtle)">
            {{ ws.selection.value?.lot }} · {{ ws.selection.value?.recipe }}
          </p>
        </div>
      </template>
      <template #footer>
        <div class="flex justify-end gap-2">
          <UButton
            color="neutral"
            variant="ghost"
            label="취소"
            @click="saveOpen = false"
          />
          <UButton
            class="bg-(--sk-ink) text-(--sk-ink-fg)"
            label="저장"
            :disabled="!saveName.trim()"
            @click="confirmSave"
          />
        </div>
      </template>
    </UModal>
  </div>
</template>

<script setup lang="ts">
import type { MeasHistToolType } from '~/composables/useMeasHistApi'

const props = defineProps<{
  toolLabel: string
  toolType: MeasHistToolType
}>()

const ws = useSkewvoirWorkspace(props.toolType, props.toolLabel)
const analysis = useSkewvoirAnalysis(ws)
const savedViews = useSkewvoirSavedViews(props.toolType)
const route = useRoute()
const toast = useToast()

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

// --- Save view ---
const saveOpen = ref(false)
const saveName = ref('')

const openSave = () => {
  const sel = ws.selection.value
  saveName.value = sel ? `${sel.lot} · ${ws.activeKind.value}` : ''
  saveOpen.value = true
}

const confirmSave = () => {
  const name = saveName.value.trim()
  if (!name) return
  savedViews.save(name, { ...route.query })
  saveOpen.value = false
  toast.add({ title: '뷰를 저장했습니다', description: name, icon: 'i-lucide-bookmark-check', color: 'success' })
}
</script>
