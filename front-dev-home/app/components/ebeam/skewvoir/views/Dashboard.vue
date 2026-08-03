<template>
  <div class="flex flex-col gap-2.5 xl:h-full xl:min-h-0">
    <!-- Top: coverage/outlier/mean/align stats + measurement conditions
         (focus switching lives in the left rail's 비교 세트 for scope=set) -->
    <div class="flex flex-wrap items-stretch gap-2.5">
      <EbeamSkewvoirOverviewStatBar
        class="min-w-0 flex-1"
        :analysis="analysis"
      />
      <EbeamSkewvoirDashboardConditions :analysis="analysis" />
    </div>

    <!-- Parameter navigator — switching it syncs every panel below -->
    <EbeamSkewvoirDashboardParamNav :analysis="analysis" />

    <!-- Inspection zone. On xl the single row is at least 49rem and fills a taller
         viewport (1fr). The floor is 49rem, not 46rem, because col 1 stacks the
         wafer (~477px at this column width) over the radius plot (min 18rem/288px):
         together ~775px, which a 46rem/736px row can't hold, so the radius plot
         used to spill ~38px below cols 2–3. `auto` can't fix this — the wafer's
         height is width-derived, so it contributes nothing to max-content track
         sizing and the row collapses back to its floor. Raising the floor to 49rem
         lets col 1 fit; stretch then carries that height to cols 2–3 so all three
         bottom-align.

         Below xl the columns stack and the workspace scroll takes over, so the
         viewport lock (h-full / flex-1 / min-h-0) is xl-only: with a definite
         grid height but no explicit rows, the implicit `auto` tracks take their
         floor from each column's min-content contribution — which `min-h-0`
         zeroes — so all three collapsed to an even third of the leftover space
         and their content painted over the column below. Each stacked column
         instead gets the same 49rem as a DEFINITE height, which keeps the
         intra-column flex split (and the panels' own overflow-auto panes)
         working exactly as it does at xl.

         Wafer + Radius + Measurement Points are adjacent so the shared
         focusedSequence selection is visible at once. -->
    <div class="grid grid-cols-1 gap-2.5 xl:min-h-0 xl:flex-1 xl:grid-cols-12 xl:grid-rows-[minmax(49rem,1fr)]">
      <!-- Linked cluster, left: wafer over radius -->
      <div class="flex h-[49rem] flex-col gap-2.5 xl:col-span-4 xl:h-auto xl:min-h-0">
        <EbeamSkewvoirDashboardWaferMap :analysis="analysis" />
        <EbeamSkewvoirDashboardRadiusPlot
          class="min-h-[18rem] flex-1"
          :analysis="analysis"
        />
      </div>

      <!-- Linked cluster, middle: the per-parameter stat table (backend
           MsrParamSummary) FIRST — readers scan the summary before the point
           list — with measurement points + 이상·실패 filter beneath it -->
      <div class="flex h-[49rem] flex-col gap-2.5 xl:col-span-4 xl:h-auto xl:min-h-0">
        <EbeamSkewvoirDashboardParamSummary
          class="max-h-96 shrink-0"
          :analysis="analysis"
        />
        <EbeamSkewvoirDashboardMeasurementPoints
          class="min-h-[24rem] flex-1 xl:min-h-0"
          :analysis="analysis"
        />
      </div>

      <!-- Right: SEM image (top, the larger share) over distribution (bottom) -->
      <div class="flex h-[49rem] flex-col gap-2.5 xl:col-span-4 xl:h-auto xl:min-h-0">
        <EbeamSkewvoirDashboardSemImage
          class="min-h-[26rem] flex-[3] xl:min-h-0"
          :analysis="analysis"
          :warm="imageWarm"
        />
        <EbeamSkewvoirDashboardDistribution
          class="min-h-0 flex-[2]"
          :analysis="analysis"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { SkewvoirAnalysis } from '~/composables/useSkewvoirAnalysis'
import { paramImageRows } from '~/utils/msrRows'

const props = defineProps<{ analysis: SkewvoirAnalysis }>()

// Warm the server-side image cache for the ACTIVE parameter's points as soon
// as its rows resolve — and again on every parameter switch — so the SEM
// Image panel asks for a cache hit instead of a cold in-request FTP fetch
// (the cloud ingress 502s those, and the browser logs every one). Other
// parameters' images stay untouched until opened. paramImageRows is the same
// derivation the gallery renders, so what we warm and what we show cannot
// drift. The state is handed to the panel so it can WAIT for the cache rather
// than race it — the warm is the reason the request succeeds.
const imageWarm = useMsrImageWarmer(useFocusImageCtx(props.analysis), computed(() => {
  const active = props.analysis.activeParam.value
  return {
    id: active,
    names: paramImageRows(props.analysis.siteRows.value, active).map(r => r.mp_image_name_01)
  }
}))
</script>
