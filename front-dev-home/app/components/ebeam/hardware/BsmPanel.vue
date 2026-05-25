<template>
  <div class="mt-3 space-y-3">
    <!-- Category toggle: Daily Monitoring vs PM Confirm (two separate sample sets) -->
    <div class="flex items-center justify-between gap-2">
      <div class="flex items-center gap-2">
        <span class="text-xs font-semibold text-(--sk-ink-muted)">데이터셋</span>
        <div class="flex overflow-hidden rounded-[10px] border border-(--sk-border)">
          <button
            v-for="category in bsm.categories"
            :key="category.key"
            type="button"
            class="px-3.5 py-1.5 text-xs font-semibold transition-colors"
            :class="category.key === selectedKey
              ? 'bg-(--sk-ink) text-white dark:text-zinc-900'
              : 'text-(--sk-ink-muted) hover:bg-(--sk-muted-surface)'"
            @click="selectedKey = category.key"
          >
            {{ category.label }}
            <span class="ml-1 font-mono text-[10px] opacity-70">{{ category.summary.length }}</span>
          </button>
        </div>
      </div>
      <!-- Raw numbers moved off-screen into a CSV export (the trend charts now
           carry the avg/3σ visualization the table used to duplicate). -->
      <UButton
        icon="i-lucide-download"
        size="xs"
        color="neutral"
        variant="outline"
        :disabled="activeRows.length === 0"
        @click="downloadSummaryCsv"
      >
        CSV 다운로드
      </UButton>
    </div>

    <div class="grid gap-3 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
      <!-- Trend charts: sharpness + noise, each avg & 3σ lines -->
      <EbeamHardwareBsmTrendChart
        metric="sharpness"
        label="Sharpness (avg · 3σ)"
        :rows="activeRows"
        :selected="selectedTimestamp"
        class="rounded-xl bg-(--sk-surface) p-2 ring-1 ring-(--sk-border-soft)"
        @select="selectedTimestamp = $event"
      />
      <EbeamHardwareBsmTrendChart
        metric="noise"
        label="Noise (avg · 3σ)"
        :rows="activeRows"
        :selected="selectedTimestamp"
        class="rounded-xl bg-(--sk-surface) p-2 ring-1 ring-(--sk-border-soft)"
        @select="selectedTimestamp = $event"
      />
    </div>

    <!-- Two side-by-side radars for the selected measurement's 360° profile.
         Now full-width (the summary table was retired in favor of CSV export);
         pick the measurement via the trend charts (click) or this dropdown. -->
    <div class="rounded-xl bg-(--sk-surface) p-2 ring-1 ring-(--sk-border-soft)">
      <div class="mb-1 flex items-center justify-between gap-2 px-1">
        <div class="text-xs font-bold text-(--sk-ink)">
          360° 빔 형상
        </div>
        <USelect
          v-model="selectedTimestamp"
          :items="timestampItems"
          size="xs"
          icon="i-lucide-clock"
          placeholder="측정 시각 선택"
          class="w-52"
        />
      </div>
      <div class="grid grid-cols-2 gap-2">
        <EbeamHardwareBsmRadarChart
          title="Sharpness"
          :color-index="0"
          :angles="bsm.angles"
          :values="selectedProfile?.sharpness ?? []"
          :min="7.6"
          :max="8.3"
        />
        <EbeamHardwareBsmRadarChart
          title="Noise"
          :color-index="1"
          :angles="bsm.angles"
          :values="selectedProfile?.noise ?? []"
          :min="6.4"
          :max="7.1"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { BsmBlock, BsmCategory } from '~/composables/useHardwareApi'
import { downloadCsv } from '~/utils/csvDownload'

const props = defineProps<{ bsm: BsmBlock }>()

const selectedKey = ref(props.bsm.categories[0]?.key ?? '')
const selectedTimestamp = ref('')

const activeCategory = computed<BsmCategory | undefined>(() =>
  props.bsm.categories.find(category => category.key === selectedKey.value)
  ?? props.bsm.categories[0]
)

const activeRows = computed(() => activeCategory.value?.summary ?? [])

// Timestamps (desc, newest first) for the radar selector dropdown.
const timestampItems = computed(() => activeRows.value.map(row => row.timestamp))

// Export the active dataset's summary — the 1:1 replacement for the removed
// 측정 요약 table. Reuses the shared util (UTF-8 BOM + CRLF for Excel).
const downloadSummaryCsv = () => {
  const headers = ['timestamp', 'sharpness_avg', 'sharpness_3std', 'noise_avg', 'noise_3std']
  const rows = activeRows.value.map(row => [
    row.timestamp,
    row.sharpness_avg,
    row.sharpness_3std,
    row.noise_avg,
    row.noise_3std
  ])
  const date = new Date().toISOString().slice(0, 10)
  downloadCsv(`bsm-summary-${selectedKey.value || 'all'}-${date}.csv`, headers, rows)
}

const selectedProfile = computed(() =>
  activeCategory.value?.profiles[selectedTimestamp.value]
)

// Default the selection to the most recent measurement (rows are timestamp-desc)
// and reset it whenever the category — or the equipment behind it — changes.
watch(activeRows, (rows) => {
  if (!rows.some(row => row.timestamp === selectedTimestamp.value)) {
    selectedTimestamp.value = rows[0]?.timestamp ?? ''
  }
}, { immediate: true })
</script>
