<template>
  <div class="space-y-2">
    <div class="flex items-center gap-2 px-1">
      <span
        class="inline-flex h-5 w-5 items-center justify-center rounded-full font-mono text-[10px] font-bold transition-colors"
        :class="selectedDeviceLots.length > 0 || presets.length > 0
          ? 'bg-(--sk-accent) text-white'
          : 'bg-zinc-200 text-zinc-500 dark:bg-zinc-700 dark:text-zinc-400'"
      >3</span>
      <h3 class="text-[12.5px] font-semibold text-zinc-900 dark:text-zinc-100">
        {{ text.step3Title }}
      </h3>
      <span class="text-[10.5px] text-zinc-400 dark:text-zinc-500">
        {{ activeTab === 'selection' ? text.step3HintSelection : text.step3HintPresets }}
      </span>
    </div>

    <UCard
      class="dashboard-surface sticky top-2 overflow-hidden rounded-2xl"
      :ui="{ body: 'p-0 sm:p-0' }"
    >
      <nav
        aria-label="Compare cart view"
        class="flex gap-1 border-b border-zinc-100 bg-zinc-50/40 p-1.5 dark:border-zinc-800 dark:bg-zinc-900/30"
      >
        <button
          v-for="tab in tabs"
          :key="tab.id"
          :aria-pressed="activeTab === tab.id"
          type="button"
          class="flex flex-1 items-center justify-center gap-1.5 rounded-full px-3 py-1.5 text-[11px] font-medium transition-colors duration-200"
          :class="activeTab === tab.id
            ? 'bg-zinc-900 text-zinc-100 dark:bg-zinc-100 dark:text-zinc-900 sk-nav-accent'
            : 'text-zinc-600 hover:text-zinc-900 hover:bg-zinc-100/70 dark:text-zinc-400 dark:hover:text-zinc-100 dark:hover:bg-zinc-800/60'"
          @click="activeTab = tab.id"
        >
          <UIcon
            :name="tab.icon"
            class="h-3 w-3"
          />
          {{ tab.label }}
          <UBadge
            v-if="tab.count > 0"
            :label="String(tab.count)"
            size="xs"
            class="rounded-full"
            :color="activeTab === tab.id ? 'primary' : 'neutral'"
            variant="subtle"
          />
        </button>
      </nav>

      <div v-if="activeTab === 'selection'">
        <div class="max-h-[24rem] overflow-y-auto">
          <EbeamCartEmptyState
            v-if="selectedDeviceRows.length === 0"
            icon="i-lucide-plus"
            :title="text.emptySelectionTitle"
            :line1="text.emptySelectionDescLineOne"
            :line2="text.emptySelectionDescLineTwo"
          />
          <div
            v-else
            class="divide-y divide-zinc-100 dark:divide-zinc-800"
          >
            <div
              v-for="(row, index) in selectedDeviceRows"
              :key="row.lot_cd"
              class="group flex items-center gap-2 px-3.5 py-2 hover:bg-zinc-50 dark:hover:bg-zinc-900/40"
            >
              <span class="inline-flex h-4 w-4 shrink-0 items-center justify-center rounded bg-zinc-100 font-mono text-[9px] text-zinc-500 dark:bg-zinc-800 dark:text-zinc-400">
                {{ index + 1 }}
              </span>
              <div class="min-w-0 flex-1">
                <div class="flex items-center gap-1.5">
                  <span class="font-mono text-[12px] font-semibold text-zinc-900 dark:text-zinc-100">{{ row.lot_cd }}</span>
                  <span class="text-[9.5px] uppercase tracking-wide text-zinc-400 dark:text-zinc-500">
                    {{ deviceChipLabel(row) }}
                  </span>
                </div>
                <p class="truncate text-[10px] text-zinc-500 dark:text-zinc-400">
                  {{ row.ctn_desc }}
                </p>
              </div>
              <button
                type="button"
                class="shrink-0 text-zinc-400 opacity-0 transition-opacity group-hover:opacity-100 hover:text-zinc-900 dark:hover:text-zinc-100"
                :aria-label="text.clearAll"
                @click="toggleDeviceSelect(row.lot_cd)"
              >
                <UIcon
                  name="i-lucide-x"
                  class="h-3 w-3"
                />
              </button>
            </div>
          </div>
        </div>

        <div class="space-y-2 border-t border-zinc-100 bg-zinc-50/40 p-2.5 dark:border-zinc-800 dark:bg-zinc-900/30">
          <UButton
            block
            size="md"
            :disabled="selectedDeviceLots.length === 0"
            :trailing-icon="selectedDeviceLots.length > 0 ? 'i-lucide-arrow-right' : undefined"
            class="bg-(--sk-accent) text-white ring-1 ring-(--sk-accent) hover:bg-(--sk-accent)/90 disabled:opacity-50"
            :ui="{ label: 'flex-1 text-center' }"
            @click="emit('proceed')"
          >
            {{ ctaLabel }}
          </UButton>
          <UButton
            block
            size="sm"
            color="neutral"
            variant="outline"
            icon="i-lucide-bookmark-plus"
            :disabled="selectedDeviceLots.length === 0"
            class="disabled:opacity-50"
            @click="showSaveDialog = true"
          >
            {{ text.saveAsPreset }}
          </UButton>
          <button
            v-if="selectedDeviceLots.length > 0"
            type="button"
            class="block w-full text-center text-[10.5px] text-zinc-500 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-200"
            @click="clearDeviceSelection"
          >
            {{ text.clearAll }}
          </button>
        </div>
      </div>

      <div v-else>
        <div class="max-h-[28rem] overflow-y-auto">
          <EbeamCartEmptyState
            v-if="presets.length === 0"
            icon="i-lucide-bookmark"
            :title="text.emptyPresetsTitle"
            :line1="text.emptyPresetsDescLineOne"
            :line2="text.emptyPresetsDescLineTwo"
          />
          <ul
            v-else
            class="space-y-1.5 p-2"
          >
            <li
              v-for="preset in presets"
              :key="preset.id"
              class="group relative flex flex-col gap-1.5 rounded-lg bg-white/70 px-3 py-2.5 ring-1 ring-zinc-100 transition-all duration-150 hover:bg-white hover:ring-zinc-200 hover:shadow-sm dark:bg-zinc-900/40 dark:ring-zinc-800 dark:hover:bg-zinc-900/70 dark:hover:ring-zinc-700"
            >
              <div class="flex items-start gap-2">
                <div class="min-w-0 flex-1">
                  <div class="flex flex-wrap items-center gap-x-1.5 gap-y-1">
                    <span class="truncate text-[12px] font-semibold text-zinc-900 dark:text-zinc-100">{{ preset.name }}</span>
                    <span
                      v-if="preset.fab"
                      class="shrink-0 rounded bg-(--sk-accent-tint) px-1.5 py-0.5 font-mono text-[9.5px] uppercase tracking-wide text-(--sk-accent) ring-1 ring-(--sk-accent-border)"
                    >
                      {{ preset.fab }}
                    </span>
                    <span class="shrink-0 rounded bg-zinc-100 px-1.5 py-0.5 font-mono text-[9.5px] tabular-nums text-zinc-500 dark:bg-zinc-800 dark:text-zinc-400">
                      {{ preset.lots.length }}{{ text.lotsSuffix }}
                    </span>
                  </div>
                  <p
                    v-if="preset.comments"
                    class="mt-1 line-clamp-2 text-[10.5px] leading-snug text-zinc-500 dark:text-zinc-400"
                  >
                    {{ preset.comments }}
                  </p>
                  <p class="mt-1 flex items-center gap-1 text-[9.5px] text-zinc-400 dark:text-zinc-500">
                    <UIcon
                      name="i-lucide-clock-3"
                      class="h-2.5 w-2.5"
                    />
                    {{ formatTimestamp(preset.createdAt) }}
                  </p>
                </div>
                <button
                  type="button"
                  class="shrink-0 rounded p-1 text-zinc-500 transition-colors hover:bg-red-50 hover:text-red-500 focus-visible:bg-red-50 focus-visible:text-red-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-200 dark:text-zinc-400 dark:hover:bg-red-950/40 dark:hover:text-red-400 dark:focus-visible:bg-red-950/40 dark:focus-visible:text-red-400 dark:focus-visible:ring-red-900"
                  :aria-label="`${text.deletePreset}: ${preset.name}`"
                  @click="removePreset(preset.id)"
                >
                  <UIcon
                    name="i-lucide-trash-2"
                    class="h-3.5 w-3.5"
                  />
                </button>
              </div>
              <div class="flex items-center justify-end">
                <UButton
                  size="xs"
                  color="neutral"
                  variant="outline"
                  icon="i-lucide-folder-open"
                  @click="onApplyPreset(preset)"
                >
                  {{ text.applyPreset }}
                </UButton>
              </div>
            </li>
          </ul>
        </div>
      </div>
    </UCard>

    <EbeamSavePresetDialog
      v-model:open="showSaveDialog"
      :selected-lots="selectedDeviceLots"
      :fab="fab"
      @saved="onPresetSaved"
    />
  </div>
</template>

<script setup lang="ts">
import type { DeviceDescRow, R3DeviceGrpRow } from '~/composables/useDeviceStatisticsApi'
import type { DevicePreset } from '~/composables/useDevicePresets'

type DeviceRow = R3DeviceGrpRow | DeviceDescRow

defineProps<{
  selectedDeviceRows: DeviceRow[]
  fab?: string
}>()

const emit = defineEmits<{
  proceed: []
  applyPreset: [preset: DevicePreset]
}>()

const text = {
  step3Title: '비교 + 이동',
  step3HintSelection: '선택된 디바이스',
  step3HintPresets: '저장된 프리셋',
  tabSelection: '비교 디바이스 선택',
  tabPresets: 'Preset 보기',
  emptySelectionTitle: '디바이스 비교 시작하기',
  emptySelectionDescLineOne: '왼쪽 테이블에서',
  emptySelectionDescLineTwo: '2개 이상 선택해 보세요',
  emptyPresetsTitle: '저장된 프리셋이 없습니다',
  emptyPresetsDescLineOne: '디바이스를 선택한 뒤',
  emptyPresetsDescLineTwo: '"저장" 버튼으로 묶음을 보관하세요',
  saveAsPreset: 'Preset으로 저장',
  applyPreset: '불러오기',
  deletePreset: '삭제',
  clearAll: '전체 해제',
  ctaEmpty: '디바이스를 선택하세요',
  ctaSingle: '디바이스 통계 보기',
  ctaMulti: '{count}개 비교 페이지로',
  lotsSuffix: '개'
} as const

const {
  selectedDeviceLots,
  toggleDeviceSelect,
  clearDeviceSelection
} = useDeviceCart()
const { presets, removePreset } = useDevicePresets()

type TabId = 'selection' | 'presets'
const activeTab = ref<TabId>('selection')
const showSaveDialog = ref(false)

const tabs = computed<{ id: TabId, label: string, icon: string, count: number }[]>(() => [
  {
    id: 'selection',
    label: text.tabSelection,
    icon: 'i-lucide-list-checks',
    count: selectedDeviceLots.value.length
  },
  {
    id: 'presets',
    label: text.tabPresets,
    icon: 'i-lucide-bookmark',
    count: presets.value.length
  }
])

const ctaLabel = computed(() => {
  if (selectedDeviceLots.value.length === 0) return text.ctaEmpty
  if (selectedDeviceLots.value.length === 1) return text.ctaSingle
  return text.ctaMulti.replace('{count}', String(selectedDeviceLots.value.length))
})

const deviceChipLabel = (row: DeviceRow): string => {
  if ('prod_catg_cd' in row && row.prod_catg_cd) {
    const tech = (row as R3DeviceGrpRow).tech_cd
    return tech ? `${row.prod_catg_cd} · ${tech}` : row.prod_catg_cd
  }
  const tech = (row as DeviceDescRow).tech_nm
  return tech ? `${row.fac_id} · ${tech}` : row.fac_id
}

const formatTimestamp = (iso: string): string => {
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return ''
  const yyyy = date.getFullYear()
  const mm = String(date.getMonth() + 1).padStart(2, '0')
  const dd = String(date.getDate()).padStart(2, '0')
  const hh = String(date.getHours()).padStart(2, '0')
  const mi = String(date.getMinutes()).padStart(2, '0')
  return `${yyyy}-${mm}-${dd} ${hh}:${mi}`
}

const onApplyPreset = (preset: DevicePreset) => {
  emit('applyPreset', preset)
  activeTab.value = 'selection'
}

const onPresetSaved = () => {
  activeTab.value = 'presets'
}
</script>
