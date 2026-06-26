<template>
  <div class="space-y-3">
    <div
      v-if="analysis.setPending.value"
      class="dashboard-surface flex h-72 items-center justify-center gap-2 rounded-(--sk-r-card) text-[12px] text-(--sk-ink-muted)"
    >
      <UIcon
        name="i-lucide-loader-circle"
        class="h-4 w-4 animate-spin"
      />
      세트를 불러오는 중…
    </div>

    <template v-else-if="meanPoints.length">
      <div class="grid grid-cols-1 gap-3 xl:grid-cols-2">
        <EbeamSkewvoirPanelFrame
          title="Composite Mean"
          :meta="`${waferCount} wafers · ${analysis.activeParam.value}`"
          icon="i-lucide-layers"
        >
          <EbeamSkewvoirWaferHeatChart
            :points="meanPoints"
            :unit="analysis.activeUnit.value"
            label="mean"
          />
        </EbeamSkewvoirPanelFrame>

        <EbeamSkewvoirPanelFrame
          title="Site Variability (σ)"
          meta="wafer-to-wafer spread"
          icon="i-lucide-git-compare"
        >
          <EbeamSkewvoirWaferHeatChart
            :points="sigmaPoints"
            :unit="analysis.activeUnit.value"
            label="σ"
          />
        </EbeamSkewvoirPanelFrame>
      </div>

      <EbeamSkewvoirPanelFrame
        title="Wafer Stack"
        :meta="`${analysis.setRows.value.length} measurements`"
        icon="i-lucide-list"
      >
        <div class="max-h-48 overflow-auto">
          <table class="w-full border-collapse text-[11.5px]">
            <tbody>
              <tr
                v-for="row in analysis.setRows.value"
                :key="row.id"
                class="border-b border-(--sk-border-soft) last:border-0"
              >
                <td class="px-2 py-1.5 font-mono font-semibold text-zinc-800 dark:text-zinc-100">
                  {{ row.lot_id }}
                </td>
                <td class="px-2 py-1.5 font-mono text-(--sk-ink-muted)">
                  {{ row.eqp_id }}
                </td>
                <td class="px-2 py-1.5 font-mono text-(--sk-ink-subtle)">
                  {{ row.timestamp }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </EbeamSkewvoirPanelFrame>
    </template>

    <div
      v-else
      class="dashboard-surface flex h-72 items-center justify-center text-center text-[12px] text-(--sk-ink-subtle)"
    >
      <span v-if="analysis.setRows.value.length === 0">비교 세트를 추가하면 합성 맵이 표시됩니다.</span>
      <span v-else>이 세트에는 “{{ analysis.activeParam.value }}” 파라미터 데이터가 없습니다. 다른 파라미터를 선택하세요.</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { SkewvoirAnalysis } from '~/composables/useSkewvoirAnalysis'

const props = defineProps<{ analysis: SkewvoirAnalysis }>()

const waferCount = computed(() => props.analysis.setFiles.value.size)

// Aggregate CD across every wafer in the set, per chip position, for the active
// parameter: composite mean + wafer-to-wafer σ at each site.
const composite = computed(() => {
  const param = props.analysis.activeParam.value
  const acc = new Map<string, { x: number, y: number, sum: number, sumsq: number, n: number }>()
  for (const file of props.analysis.setFiles.value.values()) {
    for (const r of file.rows) {
      if (r.parameter !== param || r.mp_number < 0) continue
      const xy = parseChipXY(r.chip_number)
      if (!xy) continue
      const key = `${xy[0]},${xy[1]}`
      const e = acc.get(key) ?? { x: xy[0], y: xy[1], sum: 0, sumsq: 0, n: 0 }
      e.sum += r.cd_value
      e.sumsq += r.cd_value * r.cd_value
      e.n += 1
      acc.set(key, e)
    }
  }
  const mean: [number, number, number][] = []
  const sigma: [number, number, number][] = []
  for (const e of acc.values()) {
    const m = e.sum / e.n
    const variance = Math.max(0, e.sumsq / e.n - m * m)
    mean.push([e.x, e.y, Number(m.toFixed(3))])
    sigma.push([e.x, e.y, Number(Math.sqrt(variance).toFixed(3))])
  }
  return { mean, sigma }
})

const meanPoints = computed(() => composite.value.mean)
const sigmaPoints = computed(() => composite.value.sigma)
</script>
