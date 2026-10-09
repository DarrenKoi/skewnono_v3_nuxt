<template>
  <!-- Branch-by-abstraction on analysis scope:
       • single → the single-MSR spatial workbench (Task 5)
       • set    → the existing composite-mean / σ view (kept until Task 6). -->
  <EbeamSkewvoirPositionSpatialWorkbench
    v-if="analysis.scope.value === 'single'"
    :analysis="analysis"
  />

  <div
    v-else
    class="space-y-3"
  >
    <!-- `setColdLoading` as well as `setPending`, because the batch flag misses
         the first half of a cold wait: until meas_hist answers there is no set
         key to fetch files for, so nothing is pending and this view would
         render its empty state as if the set had resolved to nothing. -->
    <AppLoadingState
      v-if="analysis.setPending.value || analysis.setColdLoading.value"
      variant="inline"
      class="dashboard-surface h-72 rounded-(--sk-r-card)"
      title="세트를 불러오는 중입니다."
    />

    <template v-else-if="sites.length || (!ready && waferCount > 0)">
      <div
        class="grid grid-cols-1 gap-3"
        :class="hasBaseline ? 'xl:grid-cols-3' : 'xl:grid-cols-2'"
      >
        <EbeamSkewvoirPanelFrame
          title="Composite Mean"
          :meta="`${waferCount} wafers · ${analysis.activeParam.value}`"
          icon="i-lucide-layers"
        >
          <div
            v-if="!ready"
            class="flex h-72 items-center justify-center px-4 text-center sk-body"
          >
            {{ NOT_SAME_SITE }} 합성 맵은 그리지 않습니다. {{ SEE_READINESS }}
          </div>
          <EbeamSkewvoirWaferHeatChart
            v-else
            :points="meanPoints"
            :unit="analysis.activeUnit.value"
            label="mean"
          />
        </EbeamSkewvoirPanelFrame>

        <EbeamSkewvoirPanelFrame
          title="Site Variability (σ)"
          meta="같은 측정점의 wafer 간 산포"
          icon="i-lucide-git-compare"
        >
          <div
            v-if="!ready"
            class="flex h-72 items-center justify-center px-4 text-center sk-body"
          >
            {{ NOT_SAME_SITE }} site 별 σ 는 그리지 않습니다. {{ SEE_READINESS }}
          </div>
          <EbeamSkewvoirWaferHeatChart
            v-else-if="sigmaPoints.length"
            :points="sigmaPoints"
            :unit="analysis.activeUnit.value"
            label="σ"
          />
          <div
            v-else
            class="flex h-72 items-center justify-center px-4 text-center sk-body"
          >
            같은 측정점을 두 wafer 이상이 측정한 site 가 없어 σ 를 계산하지 않습니다.
          </div>
        </EbeamSkewvoirPanelFrame>

        <!-- S7 — target group minus the rail's 기준 group, site by site. A site
             only one group measured is left off the map, never drawn as 0. -->
        <EbeamSkewvoirPanelFrame
          v-if="hasBaseline"
          title="기준 대비 Δ"
          :meta="ready ? `대상 − 기준 · ${delta.points.length} sites${delta.unpaired ? ` · 공통 측정점 없음 ${delta.unpaired}` : ''}` : '대상 − 기준 · 비교 불가'"
          icon="i-lucide-diff"
        >
          <div
            v-if="!ready"
            class="flex h-72 items-center justify-center px-4 text-center sk-body"
          >
            {{ NOT_SAME_SITE }} site 단위 Δ 는 그리지 않습니다. {{ SEE_READINESS }}
          </div>
          <EbeamSkewvoirWaferHeatChart
            v-else-if="delta.points.length"
            :points="delta.points"
            :unit="analysis.activeUnit.value"
            label="Δ"
            symmetric
          />
          <div
            v-else
            class="flex h-72 items-center justify-center px-4 text-center sk-body"
          >
            기준과 대상이 함께 측정한 site 가 없습니다.
          </div>
        </EbeamSkewvoirPanelFrame>
      </div>

      <EbeamSkewvoirPanelFrame
        title="Wafer Stack"
        :meta="`${analysis.setRows.value.length} measurements`"
        icon="i-lucide-list"
      >
        <div class="max-h-48 overflow-auto">
          <table class="w-full border-collapse text-xs">
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
      class="dashboard-surface flex h-72 items-center justify-center text-center sk-body"
    >
      <span v-if="analysis.setRows.value.length === 0">비교 세트를 추가하면 합성 맵이 표시됩니다.</span>
      <span v-else>이 세트에는 “{{ analysis.activeParam.value }}” 파라미터 데이터가 없습니다. 다른 파라미터를 선택하세요.</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { SkewvoirAnalysis } from '~/composables/useSkewvoirAnalysis'
import { baselineDeltaMap, compositeSiteMap } from '~/utils/skewvoirAnalysis/baselineCompare'

const props = defineProps<{ analysis: SkewvoirAnalysis }>()

// One wording for all three maps: none of them is drawn unless the set's
// measurements are known to share sites (the readiness the Δ map already asks).
const NOT_SAME_SITE = '세트의 측정들이 같은 위치를 쟀는지 확인할 수 없어'
const SEE_READINESS = '사유는 분석 준비 상태에서 볼 수 있습니다.'
const ready = computed(() => props.analysis.siteDeltaReady.value)

// The compatible members whose files are on hand — what the maps combine.
const includedIds = computed(() => props.analysis.comparedMembers.value)
const waferCount = computed(() => includedIds.value.length)

// Composite mean + wafer-to-wafer σ per chip, a site being (chip, MP) — the
// rule lives in compositeSiteMap, which the review receipt calls too.
const sites = computed(() => ready.value
  ? compositeSiteMap(props.analysis.setFiles.value, includedIds.value, props.analysis.activeParam.value)
  : [])
const meanPoints = computed(() =>
  sites.value.map((s): [number, number, number] => [s.x, s.y, Number(s.mean.toFixed(3))]))
const sigmaPoints = computed(() =>
  sites.value.flatMap((s): [number, number, number][] => s.sigma == null ? [] : [[s.x, s.y, Number(s.sigma.toFixed(3))]]))

const hasBaseline = computed(() => props.analysis.baseline.value.length > 0)
const delta = computed(() => {
  const { base, target } = props.analysis.baselineGroups.value
  return baselineDeltaMap(props.analysis.setFiles.value, base, target, props.analysis.activeParam.value)
})
</script>
