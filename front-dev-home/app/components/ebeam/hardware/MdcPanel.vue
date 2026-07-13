<template>
  <div class="mt-3 space-y-3">
    <!-- 시계열 | 비교 sub-tabs (same pattern as the FDC fdc_key tabs) -->
    <div class="flex w-fit overflow-hidden rounded-[10px] border border-(--sk-border)">
      <button
        v-for="tab in TABS"
        :key="tab"
        type="button"
        class="px-3.5 py-1.5 text-xs font-semibold transition-colors"
        :class="tab === activeTab
          ? 'bg-(--sk-ink) text-white dark:text-zinc-900'
          : 'text-(--sk-ink-muted) hover:bg-(--sk-muted-surface)'"
        @click="activeTab = tab"
      >
        {{ tab }}
      </button>
    </div>

    <!-- ===== 시계열: family chips + trajectory + per-axis trends ===== -->
    <template v-if="activeTab === '시계열'">
      <div
        v-if="families.length === 0"
        class="rounded-xl bg-(--sk-surface) px-4 py-8 text-center text-sm text-(--sk-ink-muted) ring-1 ring-(--sk-border-soft)"
      >
        MDC 이력 데이터가 없습니다.
      </div>
      <template v-else>
        <div class="flex flex-wrap items-center gap-1.5">
          <SkChip
            v-for="fam in families"
            :key="fam.key"
            size="sm"
            :active="fam.key === activeFamilyKey"
            :count="fam.zero.length"
            @click="activeFamilyKey = fam.key"
          >
            {{ fam.key }}
          </SkChip>
        </div>

        <div
          v-if="activeFamily"
          class="grid gap-3"
          :class="isPaired ? 'lg:grid-cols-[minmax(0,26rem)_minmax(0,1fr)]' : ''"
        >
          <!-- x/y trajectory (paired 0°/90° families only) -->
          <div
            v-if="isPaired"
            class="rounded-xl bg-(--sk-surface) p-2 ring-1 ring-(--sk-border-soft)"
          >
            <div class="mb-1 px-1 text-xs font-bold text-(--sk-ink)">
              0° · 90° Trajectory
            </div>
            <div
              ref="xyEl"
              class="aspect-square w-full"
            />
          </div>

          <!-- per-axis trends -->
          <div class="flex min-w-0 flex-col gap-3">
            <div class="rounded-xl bg-(--sk-surface) p-2 ring-1 ring-(--sk-border-soft)">
              <EbeamHardwareBsmTrendChart
                :label="isPaired ? `${activeFamily.key} · 0°` : activeFamily.key"
                :points="axisPoints(activeFamily.zero)"
                selected=""
                y-mode="tight"
              />
            </div>
            <div
              v-if="isPaired"
              class="rounded-xl bg-(--sk-surface) p-2 ring-1 ring-(--sk-border-soft)"
            >
              <EbeamHardwareBsmTrendChart
                :label="`${activeFamily.key} · 90°`"
                :points="axisPoints(activeFamily.ninety)"
                selected=""
                y-mode="tight"
              />
            </div>
          </div>
        </div>
      </template>
    </template>

    <!-- ===== 비교: fleet snapshot (matrix table — boxplot lands in the next task) ===== -->
    <template v-else>
      <div
        v-if="matrix.tools.length === 0"
        class="rounded-xl bg-(--sk-surface) px-4 py-8 text-center text-sm text-(--sk-ink-muted) ring-1 ring-(--sk-border-soft)"
      >
        MDC 설정 데이터가 없습니다.
      </div>
      <div
        v-else
        class="overflow-x-auto rounded-xl bg-(--sk-surface) ring-1 ring-(--sk-border-soft)"
      >
        <table class="min-w-full text-left text-xs">
          <thead class="bg-(--sk-muted-surface) text-(--sk-ink-muted)">
            <tr>
              <th class="whitespace-nowrap px-3 py-2 font-mono text-[10px] uppercase tracking-[0.05em]">
                EQP
              </th>
              <th
                v-for="cond in matrix.conditions"
                :key="cond"
                class="whitespace-nowrap px-3 py-2 text-right font-mono text-[10px] uppercase tracking-[0.05em]"
              >
                {{ cond }}
              </th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="(tool, row) in matrix.tools"
              :key="tool"
              class="border-t border-(--sk-border-soft)"
              :class="row === 0 ? 'bg-(--sk-muted-surface)' : ''"
            >
              <td class="whitespace-nowrap px-3 py-2 font-mono font-bold text-(--sk-ink)">
                {{ tool }}
                <span
                  v-if="row === 0"
                  class="ml-1 rounded bg-(--sk-ink) px-1 text-[9px] text-white dark:text-zinc-900"
                >선택</span>
              </td>
              <td
                v-for="(cond, col) in matrix.conditions"
                :key="cond"
                class="whitespace-nowrap px-3 py-2 text-right font-mono tabular-nums text-(--sk-ink)"
                :style="cellStyle(row, col)"
              >
                {{ formatCell(matrix.values[row]?.[col]) }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import type { EChartsOption } from 'echarts'
import { buildMdcMatrix, cellDeviation } from '~/utils/mdcMatrix'
import { buildMdcFamilies, trajectoryPoints, type MdcHistoryPoint } from '~/utils/mdcHistory'

const props = defineProps<{
  settings: Record<string, Record<string, unknown>>
  docs: Record<string, unknown>[]
  selectedEqp: string
}>()

const TABS = ['시계열', '비교'] as const
const activeTab = ref<(typeof TABS)[number]>('시계열')

// --- 시계열 ---
const families = computed(() => buildMdcFamilies(props.docs))
const activeFamilyKey = ref('')
watch(families, (fams) => {
  if (!fams.some(f => f.key === activeFamilyKey.value)) {
    activeFamilyKey.value = (fams.find(f => f.key === '800V_HR') ?? fams[0])?.key ?? ''
  }
}, { immediate: true })
const activeFamily = computed(() => families.value.find(f => f.key === activeFamilyKey.value))
const isPaired = computed(() => (activeFamily.value?.ninety.length ?? 0) > 0)

// BsmTrendChart wants {ts, key, value}; MDC has no per-point selection, so
// the timestamp doubles as the key.
const axisPoints = (pts: MdcHistoryPoint[]) => pts.map(p => ({ ts: p.ts, key: p.ts, value: p.value }))

const { palette } = useEchartsTheme()
const c0 = computed(() => palette.value[0] ?? '#C75A3C')
const c1 = computed(() => palette.value[1] ?? '#3F5D52')

const xyEl = ref<HTMLDivElement | null>(null)
const xyOption = computed<EChartsOption>(() => {
  const pts = activeFamily.value ? trajectoryPoints(activeFamily.value) : []
  const n = pts.length
  const latest = pts[n - 1]
  return {
    grid: { left: 56, right: 16, top: 16, bottom: 36 },
    tooltip: {
      trigger: 'item',
      formatter: (params) => {
        const raw = (Array.isArray(params) ? params[0] : params)?.data as unknown
        const v = (raw as { value?: unknown })?.value ?? raw
        return Array.isArray(v) ? `${v[2]}<br/>0° ${v[0]} · 90° ${v[1]}` : ''
      }
    },
    xAxis: { type: 'value', name: '0°', scale: true, axisLabel: { fontSize: 10 } },
    yAxis: { type: 'value', name: '90°', scale: true, axisLabel: { fontSize: 10 } },
    series: [
      {
        type: 'scatter',
        symbolSize: 8,
        // (1.0, 1.0) = no-correction reference crosshair.
        markLine: {
          silent: true,
          symbol: 'none',
          animation: false,
          lineStyle: { type: 'dashed', width: 1, color: '#9ca3af', opacity: 0.6 },
          label: { show: false },
          data: [{ xAxis: 1 }, { yAxis: 1 }]
        },
        data: pts.map((p, i) => ({
          value: [p.x, p.y, p.ts],
          // Older → more transparent, so the path reads oldest→newest.
          itemStyle: { color: c0.value, opacity: n <= 1 ? 1 : 0.2 + 0.7 * (i / (n - 1)) }
        }))
      },
      ...(latest
        ? [{
            type: 'scatter' as const,
            symbolSize: 14,
            itemStyle: { color: c1.value, borderColor: '#fff', borderWidth: 1 },
            data: [{ value: [latest.x, latest.y, `${latest.ts} (latest)`] }]
          }]
        : [])
    ]
  }
})
useEchart(xyEl, xyOption)

// --- 비교 (matrix table — replaced by the fleet boxplot in the next task) ---
const matrix = computed(() => buildMdcMatrix(props.settings, props.selectedEqp))

const formatCell = (v: number | null | undefined) =>
  v === null || v === undefined ? '-' : v.toFixed(4)

// Warm (rose) for above-baseline, cool (sky) for below; alpha = magnitude.
const cellStyle = (row: number, col: number) => {
  if (row === 0) return {}
  const dev = cellDeviation(matrix.value, row, col)
  if (dev === 0) return {}
  const alpha = Math.min(Math.abs(dev) * 0.6, 0.6).toFixed(3)
  const rgb = dev > 0 ? '244, 63, 94' : '56, 189, 248'
  return { backgroundColor: `rgba(${rgb}, ${alpha})` }
}
</script>
