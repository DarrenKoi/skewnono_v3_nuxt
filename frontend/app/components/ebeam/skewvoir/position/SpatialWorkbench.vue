<template>
  <div class="space-y-3">
    <AppLoadingState
      v-if="analysis.focusPending.value"
      variant="inline"
      class="dashboard-surface h-72 rounded-(--sk-r-card)"
      title="측정을 불러오는 중입니다."
    />

    <div
      v-else-if="analysis.focusError.value"
      class="dashboard-surface flex h-72 flex-col items-center justify-center gap-2 rounded-(--sk-r-card) text-center sk-body"
    >
      <span>측정을 불러오지 못했습니다.</span>
      <UButton
        color="primary"
        variant="soft"
        size="sm"
        icon="i-lucide-rotate-cw"
        label="다시 시도"
        @click="analysis.retryFocus()"
      />
    </div>

    <div
      v-else-if="!hasData"
      class="dashboard-surface flex h-72 items-center justify-center px-4 text-center sk-body"
    >
      “{{ analysis.activeParamLabel.value }}” 측정점이 없습니다. 다른 파라미터를 선택하세요.
    </div>

    <template v-else>
      <!-- Answer strip — four SEPARATE evidence chips, never one merged score. -->
      <div class="grid grid-cols-2 gap-2 xl:grid-cols-4">
        <div
          v-for="chip in evidenceChips"
          :key="chip.key"
          class="dashboard-surface rounded-(--sk-r-card) px-3 py-2.5"
        >
          <p class="sk-label">
            {{ chip.label }}
          </p>
          <p
            v-if="chip.status === 'ok'"
            class="mt-0.5 font-mono text-lg font-semibold text-(--sk-ink) tabular-nums"
          >
            {{ formatValue(chip) }}
          </p>
          <p
            v-else
            class="mt-0.5 font-mono text-[15px] font-semibold text-(--sk-ink-subtle)"
          >
            평가 불가
          </p>
          <p
            class="mt-0.5 text-[13px] text-(--sk-ink-muted)"
            :title="chip.detail"
          >
            {{ chip.detail }}
          </p>
        </div>
      </div>

      <div class="grid grid-cols-1 gap-3 xl:grid-cols-2">
        <EbeamSkewvoirPositionSpatialLayerMap
          :spatial="spatial"
          :geo="analysis.waferGeo.value"
          :focused-site="analysis.focusedSite.value"
          :unit="analysis.activeUnit.value"
          @focus="onFocus"
        />
        <div class="grid grid-cols-1 gap-3">
          <EbeamSkewvoirPositionRadialProfile
            :spatial="spatial"
            :parameter="analysis.activeParam.value"
            :unit="analysis.activeUnit.value"
          />
          <EbeamSkewvoirPositionSectorProfile
            :spatial="spatial"
            :unit="analysis.activeUnit.value"
          />
        </div>
      </div>

      <!-- Site table — linked to focusedSite. -->
      <EbeamSkewvoirPanelFrame
        title="Site Detail"
        :meta="`${spatial.sites.length} sites · ${spatial.failures.length} 실패`"
        icon="i-lucide-table"
      >
        <div class="max-h-64 overflow-auto">
          <table class="w-full border-collapse text-xs">
            <thead class="sticky top-0 z-10 bg-(--sk-surface)">
              <tr class="border-b border-(--sk-border) sk-label">
                <th
                  scope="col"
                  class="px-1.5 py-1.5 text-left font-semibold"
                >
                  SEQ
                </th>
                <th
                  scope="col"
                  class="px-1.5 py-1.5 text-left font-semibold"
                >
                  CHIP
                </th>
                <th
                  scope="col"
                  class="px-1.5 py-1.5 text-right font-semibold"
                >
                  R (mm)
                </th>
                <th
                  scope="col"
                  class="px-1.5 py-1.5 text-left font-semibold"
                >
                  SECTOR
                </th>
                <th
                  scope="col"
                  class="px-1.5 py-1.5 text-right font-semibold"
                >
                  RAW
                </th>
                <th
                  scope="col"
                  class="px-1.5 py-1.5 text-right font-semibold"
                >
                  CENTERED
                </th>
                <th
                  scope="col"
                  class="px-1.5 py-1.5 text-right font-semibold"
                >
                  RESIDUAL
                </th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="s in spatial.sites"
                :key="s.sequence"
                class="cursor-pointer border-b border-(--sk-border-soft) transition-colors duration-200 last:border-0"
                :class="s.chip === analysis.focusedSite.value ? 'bg-(--sk-brand)/15' : 'hover:bg-(--sk-chip-bg)'"
                @click="onFocus(s.chip)"
              >
                <td class="px-1.5 py-1.5 font-mono tabular-nums">
                  {{ s.sequence }}
                </td>
                <td class="px-1.5 py-1.5 font-mono">
                  {{ s.chip }}
                </td>
                <td class="px-1.5 py-1.5 text-right font-mono tabular-nums">
                  {{ s.radiusMm != null ? s.radiusMm.toFixed(1) : '—' }}
                </td>
                <td class="px-1.5 py-1.5 font-mono text-(--sk-ink-muted)">
                  {{ s.sector ?? '—' }}
                </td>
                <td class="px-1.5 py-1.5 text-right font-mono font-medium tabular-nums">
                  {{ s.raw.toFixed(3) }}
                </td>
                <td
                  class="px-1.5 py-1.5 text-right font-mono tabular-nums"
                  :class="s.centered >= 0 ? 'text-(--sk-bad)' : 'text-(--sk-ok)'"
                >
                  {{ s.centered >= 0 ? '+' : '' }}{{ s.centered.toFixed(3) }}
                </td>
                <td class="px-1.5 py-1.5 text-right font-mono tabular-nums text-(--sk-ink-muted)">
                  {{ s.residual != null ? `${s.residual >= 0 ? '+' : ''}${s.residual.toFixed(3)}` : '—' }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </EbeamSkewvoirPanelFrame>
    </template>

    <EbeamSkewvoirPositionSiteEvidenceDrawer
      v-model:open="drawerOpen"
      :spatial="spatial"
      :analysis="analysis"
      :unit="analysis.activeUnit.value"
    />
  </div>
</template>

<script setup lang="ts">
import type { SkewvoirAnalysis } from '~/composables/useSkewvoirAnalysis'
import { isMeasuredRow } from '~/utils/msrRows'
import { analyzeSpatial, type SpatialEvidence } from '~/utils/skewvoirAnalysis/spatial'

const props = defineProps<{ analysis: SkewvoirAnalysis }>()

const drawerOpen = ref(false)

const hasData = computed(() =>
  props.analysis.siteRows.value.some(
    r => r.parameter === props.analysis.activeParam.value && isMeasuredRow(r)
  )
)

// The single-MSR spatial diagnosis for the FOCUS file + active parameter.
const spatial = computed(() =>
  analyzeSpatial(
    props.analysis.siteRows.value,
    props.analysis.activeParam.value,
    props.analysis.waferGeo.value,
    { unit: props.analysis.activeUnit.value }
  )
)

const evidenceChips = computed<SpatialEvidence[]>(() => {
  const e = spatial.value.evidence
  return [e.centerEdgeDelta, e.directionContrast, e.largestLocalResidual, e.coverage]
})

const formatValue = (chip: SpatialEvidence): string => {
  if (chip.value == null) return '—'
  if (chip.unit === 'ratio') return `${(chip.value * 100).toFixed(0)}%`
  const sign = chip.value > 0 && chip.key !== 'largestLocalResidual' ? '+' : ''
  return `${sign}${chip.value.toFixed(3)} ${chip.unit}`.trim()
}

// Link map ↔ table ↔ drawer ↔ SEM through focusedSite (chip) + focusedSequence.
const onFocus = (chip: string) => {
  props.analysis.setFocusedSite(chip)
  const site = spatial.value.sites.find(s => s.chip === chip)
  if (site) props.analysis.setFocusedSequence(site.sequence)
  drawerOpen.value = true
}
</script>
