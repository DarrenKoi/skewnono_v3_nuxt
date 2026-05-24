<template>
  <div class="mt-3 space-y-3">
    <!-- Category toggle: Daily Monitoring vs PM Confirm (two separate sample sets) -->
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

    <div class="grid gap-3 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)]">
      <!-- Summary table — click a row to drive the radar -->
      <div class="overflow-hidden rounded-xl bg-(--sk-surface) ring-1 ring-(--sk-border-soft)">
        <div class="border-b border-(--sk-border-soft) px-3 py-2 text-xs font-bold text-(--sk-ink)">
          측정 요약 ({{ activeRows.length }}건)
        </div>
        <div class="max-h-72 overflow-auto">
          <table class="min-w-full text-left text-xs">
            <thead class="sticky top-0 bg-zinc-100 text-zinc-500 dark:bg-zinc-900 dark:text-zinc-400">
              <tr>
                <th class="whitespace-nowrap px-3 py-2 font-mono text-[10px] uppercase tracking-[0.05em]">Timestamp</th>
                <th class="whitespace-nowrap px-3 py-2 text-right font-mono text-[10px] uppercase tracking-[0.05em]">Sharp avg</th>
                <th class="whitespace-nowrap px-3 py-2 text-right font-mono text-[10px] uppercase tracking-[0.05em]">Sharp 3σ</th>
                <th class="whitespace-nowrap px-3 py-2 text-right font-mono text-[10px] uppercase tracking-[0.05em]">Noise avg</th>
                <th class="whitespace-nowrap px-3 py-2 text-right font-mono text-[10px] uppercase tracking-[0.05em]">Noise 3σ</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="row in activeRows"
                :key="row.timestamp"
                class="cursor-pointer border-t border-(--sk-border-soft) border-l-2 transition-colors"
                :class="row.timestamp === selectedTimestamp
                  ? 'border-l-(--sk-ink) bg-(--sk-muted-surface)'
                  : 'border-l-transparent hover:bg-zinc-50 dark:hover:bg-zinc-800/40'"
                @click="selectedTimestamp = row.timestamp"
              >
                <td class="whitespace-nowrap px-3 py-1.5 font-mono text-(--sk-ink)">{{ row.timestamp }}</td>
                <td class="whitespace-nowrap px-3 py-1.5 text-right font-mono tabular-nums text-(--sk-ink)">{{ row.sharpness_avg.toFixed(3) }}</td>
                <td class="whitespace-nowrap px-3 py-1.5 text-right font-mono tabular-nums text-(--sk-ink-muted)">{{ row.sharpness_3std.toFixed(3) }}</td>
                <td class="whitespace-nowrap px-3 py-1.5 text-right font-mono tabular-nums text-(--sk-ink)">{{ row.noise_avg.toFixed(3) }}</td>
                <td class="whitespace-nowrap px-3 py-1.5 text-right font-mono tabular-nums text-(--sk-ink-muted)">{{ row.noise_3std.toFixed(3) }}</td>
              </tr>
              <tr v-if="activeRows.length === 0">
                <td colspan="5" class="px-3 py-8 text-center text-(--sk-ink-muted)">측정 데이터가 없습니다.</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Two side-by-side radars for the selected measurement's 360° profile -->
      <div class="rounded-xl bg-(--sk-surface) p-2 ring-1 ring-(--sk-border-soft)">
        <div class="mb-1 px-1 text-xs font-bold text-(--sk-ink)">
          360° 빔 형상
          <span class="ml-1 font-mono text-[10px] font-normal text-(--sk-ink-muted)">{{ selectedTimestamp || '—' }}</span>
        </div>
        <div class="grid grid-cols-2 gap-2">
          <EbeamHardwareBsmRadarChart
            title="Sharpness"
            color="#6366f1"
            :angles="bsm.angles"
            :values="selectedProfile?.sharpness ?? []"
          />
          <EbeamHardwareBsmRadarChart
            title="Noise"
            color="#f59e0b"
            :angles="bsm.angles"
            :values="selectedProfile?.noise ?? []"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { BsmBlock, BsmCategory } from '~/composables/useHardwareApi'

const props = defineProps<{ bsm: BsmBlock }>()

const selectedKey = ref(props.bsm.categories[0]?.key ?? '')
const selectedTimestamp = ref('')

const activeCategory = computed<BsmCategory | undefined>(() =>
  props.bsm.categories.find(category => category.key === selectedKey.value)
  ?? props.bsm.categories[0]
)

const activeRows = computed(() => activeCategory.value?.summary ?? [])

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
