<template>
  <div class="mt-3 space-y-3">
    <div
      v-if="!hasSelected"
      class="rounded-xl bg-(--sk-surface) px-4 py-8 text-center text-sm text-(--sk-ink-muted) ring-1 ring-(--sk-border-soft)"
    >
      SCE 설정 데이터가 없습니다.
    </div>

    <template v-else>
      <!-- Settings compare table: selected vs siblings, diffs flagged -->
      <div class="overflow-x-auto rounded-xl bg-(--sk-surface) ring-1 ring-(--sk-border-soft)">
        <table class="min-w-full text-left text-xs">
          <thead class="bg-(--sk-muted-surface) text-(--sk-ink-muted)">
            <tr>
              <th class="px-3 py-2 font-mono text-[10px] uppercase tracking-[0.05em]">
                Setting
              </th>
              <th class="px-3 py-2 font-mono text-[10px] uppercase tracking-[0.05em]">
                {{ selectedEqp }} (선택)
              </th>
              <th
                v-for="id in siblingIds"
                :key="id"
                class="px-3 py-2 font-mono text-[10px] uppercase tracking-[0.05em]"
              >
                {{ id }}
              </th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="row in rows"
              :key="row.path"
              class="border-t border-(--sk-border-soft)"
              :class="row.differs ? 'bg-amber-50 dark:bg-amber-950/30' : ''"
            >
              <td class="px-3 py-2 font-mono text-(--sk-ink-muted)">
                {{ row.path }}
              </td>
              <td class="px-3 py-2 font-mono font-bold text-(--sk-ink)">
                {{ row.selected !== '' ? row.selected : '-' }}
              </td>
              <td
                v-for="id in siblingIds"
                :key="id"
                class="px-3 py-2 font-mono"
                :class="row.siblings[id] !== row.selected ? 'text-(--sk-bad) font-bold' : 'text-(--sk-ink)'"
              >
                {{ row.siblings[id] !== '' ? row.siblings[id] : '-' }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Coefficients[0..359] overlay: values[0] / values[1], selected vs one sibling -->
      <div class="rounded-xl bg-(--sk-surface) p-2 ring-1 ring-(--sk-border-soft)">
        <div class="mb-1 flex items-center justify-between gap-2 px-1">
          <div class="text-xs font-bold text-(--sk-ink)">
            Coefficients (0–359)
          </div>
          <USelect
            v-model="overlayEqp"
            :items="overlayItems"
            size="xs"
            class="w-44"
          />
        </div>
        <div
          ref="chartEl"
          class="h-80 w-full"
        />
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import type { EChartsOption } from 'echarts'
import { compareSettings, coefficientSeries } from '~/utils/sceCompare'

const props = defineProps<{
  settings: Record<string, Record<string, unknown>>
  selectedEqp: string
}>()

const hasSelected = computed(() => Boolean(props.settings[props.selectedEqp]))
const siblingIds = computed(() => Object.keys(props.settings).filter(id => id !== props.selectedEqp).sort())
const rows = computed(() => compareSettings(props.settings, props.selectedEqp))

const overlayItems = computed(() => [
  { label: 'overlay 없음', value: 'none' },
  ...siblingIds.value.map(id => ({ label: id, value: id }))
])
const overlayEqp = ref('none')

const { palette } = useEchartsTheme()
const c0 = computed(() => palette.value[0] ?? '#C75A3C')
const c1 = computed(() => palette.value[1] ?? '#3F5D52')
const c2 = computed(() => palette.value[2] ?? '#7B6CC4')
const c3 = computed(() => palette.value[3] ?? '#B0843C')

const chartEl = ref<HTMLDivElement | null>(null)
const indices = Array.from({ length: 360 }, (_, i) => i)

const chartOption = computed<EChartsOption>(() => {
  const sel = coefficientSeries(props.settings[props.selectedEqp])
  const sib = overlayEqp.value !== 'none' ? coefficientSeries(props.settings[overlayEqp.value]) : null
  const line = (name: string, data: number[], color: string, dashed = false) => ({
    name, type: 'line' as const, showSymbol: false, smooth: false,
    lineStyle: { color, width: 1.2, type: dashed ? ('dashed' as const) : ('solid' as const) },
    itemStyle: { color }, data
  })
  return {
    grid: { left: 48, right: 16, top: 24, bottom: 36 },
    tooltip: { trigger: 'axis' },
    legend: { top: 0, textStyle: { fontSize: 10 } },
    xAxis: { type: 'category', data: indices, name: 'index', axisLabel: { fontSize: 10 } },
    yAxis: { type: 'value', scale: true, axisLabel: { fontSize: 10 } },
    series: [
      line(`${props.selectedEqp} v0`, sel.v0, c0.value),
      line(`${props.selectedEqp} v1`, sel.v1, c1.value),
      ...(sib ? [line(`${overlayEqp.value} v0`, sib.v0, c2.value, true), line(`${overlayEqp.value} v1`, sib.v1, c3.value, true)] : [])
    ]
  }
})

useEchart(chartEl, chartOption)
</script>
