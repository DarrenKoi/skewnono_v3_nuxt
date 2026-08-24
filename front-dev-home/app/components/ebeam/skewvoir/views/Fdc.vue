<template>
  <!-- Branch-by-abstraction on analysis scope:
       • single → the sequence workbench (MEASUREMENT ORDER within one MSR; the
         MSR file carries no per-sequence timestamp, so it has nothing to say
         about a set)
       • set    → the run × channel status matrix, which compares whole
         measurements to each other and never opens a sequence. -->
  <EbeamSkewvoirFdcSequenceWorkbench
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

    <EbeamSkewvoirPanelFrame
      v-else-if="matrix.channelCount"
      title="측정별 FDC 채널 상태"
      :meta="panelMeta"
      icon="i-lucide-grid-3x3"
    >
      <div class="space-y-2.5">
        <EbeamSkewvoirFdcSetStatusMatrix :matrix="matrix" />

        <p class="sk-meta">
          <!-- The honesty line this view rests on. fdc_params is already one
               summary per measurement, so a cell is one whole run compared with
               another whole run — nothing is pooled across sequences to build
               it. See the GRAIN section of utils/skewvoirAnalysis/fdcSet.ts. -->
          셀 값은 채널의 drift σ이며, 각 셀은 측정 하나 전체의 요약입니다.
          sequence를 합쳐 만든 값이 아닙니다.
        </p>

        <p
          v-if="matrix.partialChannelCount"
          class="sk-meta"
        >
          채널 {{ matrix.partialChannelCount }}개는 일부 측정에만 있습니다. 해당 측정 칸은 비워 두었습니다.
        </p>

        <p
          v-if="unloadedCount"
          class="sk-meta"
        >
          측정 {{ unloadedCount }}개는 아직 불러오지 못해 열에서 제외했습니다.
        </p>
      </div>
    </EbeamSkewvoirPanelFrame>

    <div
      v-else
      class="dashboard-surface flex h-72 items-center justify-center px-4 text-center sk-body"
    >
      <span v-if="analysis.setRows.value.length === 0">비교 세트를 추가하면 측정별 FDC 채널 상태가 표시됩니다.</span>
      <span v-else>이 세트에는 FDC 채널 데이터가 없습니다.</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { SkewvoirAnalysis } from '~/composables/useSkewvoirAnalysis'
import { buildFdcSetMatrix, type FdcSetRunSource } from '~/utils/skewvoirAnalysis/fdcSet'

const props = defineProps<{
  analysis: SkewvoirAnalysis
}>()

// Only measurements whose file has actually landed become columns. A requested
// but unloaded MSR would otherwise render as a column of blanks — and this
// matrix already spends its blanks on "this run does not carry that channel".
// Two different absences sharing one glyph is the one thing the view must not
// do, so the unloaded ones are excluded and COUNTED instead.
const loadedRuns = computed<FdcSetRunSource[]>(() =>
  props.analysis.setRows.value.flatMap((row) => {
    const file = props.analysis.setFiles.value.get(row.msr)
    return file
      ? [{ msr: row.msr, label: props.analysis.msrLabel(row.msr), fdc_params: file.fdc_params }]
      : []
  })
)

const unloadedCount = computed(() =>
  props.analysis.setRows.value.length - loadedRuns.value.length
)

// Column order is the curated set's own order, the same one the Wafer Stack
// table uses — deliberately NOT re-sorted by time here, so the two set views
// never disagree about which measurement is which. Each header carries its
// equipment and timestamp, so the order is readable rather than implied.
const matrix = computed(() => buildFdcSetMatrix(loadedRuns.value))

const panelMeta = computed(() =>
  `${matrix.value.runs.length} runs · ${matrix.value.channelCount} channels`
)
</script>
