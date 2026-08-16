<template>
  <div class="dashboard-surface rounded-[var(--sk-r-card)] px-5 py-4">
    <div class="flex flex-wrap items-baseline justify-between gap-2">
      <p class="sk-title">
        튜닝 목표 — 그룹 진입 조건
      </p>
      <span
        v-if="report && !report.inGroup"
        class="sk-badge"
        :class="report.admitted ? 'bg-(--sk-ok-soft) text-(--sk-ink)' : 'bg-(--sk-bad-soft) text-(--sk-bad)'"
      >{{ report.admitted ? '지금 기준 진입 가능' : `미충족 셀 ${blockedCells}개` }}</span>
    </div>

    <p
      v-if="!hasGroup"
      class="mt-2 sk-body text-(--sk-ink-muted)"
    >
      현재 tolerance에서는 N배화 그룹 자체가 만들어지지 않아, 진입 목표를 정의할 기준이 없습니다.
    </p>

    <p
      v-else-if="!report"
      class="mt-2 sk-body text-(--sk-ink-muted)"
    >
      장비를 선택하면 그 장비의 셀별 진입 조건을 보여줍니다.
    </p>

    <template v-else-if="report.inGroup">
      <p class="mt-2 sk-body leading-relaxed">
        <strong class="font-mono">{{ pickedLabel }}</strong> 는 이미 1차 그룹
        {{ report.prospectiveN }}대의 구성원입니다. PM 후에도 모든 점유 셀에서 각 구성원과
        tolerance 안쪽을 유지하는 것이 목표입니다 — 여기서 벗어나면 N이 줄어듭니다.
      </p>
    </template>

    <template v-else>
      <!-- The admission rule, stated once above the rows it explains: a clique
           admits a tool only when EVERY member is within tolerance in EVERY
           occupied cell — so each row below is a necessary condition, not an
           alternative. -->
      <p class="mt-1.5 sk-field-label leading-relaxed">
        모든 점유 셀에서, 그룹의 <strong>모든</strong> 구성원과 측정된 skew가 그 셀의
        허용오차 안쪽이어야 진입합니다. 셀마다 가장 어긋난 구성원 쌍과 필요한 조정량입니다.
      </p>

      <ul class="mt-2.5 space-y-1.5">
        <li
          v-for="row in report.cells"
          :key="row.cell.cell_id"
          class="rounded-lg border border-(--sk-border-soft) px-3 py-2"
          :style="row.admitted ? undefined : { backgroundImage: 'linear-gradient(var(--sk-bad-tint), var(--sk-bad-tint))' }"
        >
          <div class="flex flex-wrap items-center gap-x-2 gap-y-1">
            <span class="sk-value-num">{{ cellLabel(row.cell) }}</span>
            <UIcon
              :name="row.admitted ? 'i-lucide-check' : 'i-lucide-move-down-right'"
              class="h-3.5 w-3.5"
              :class="row.admitted ? 'text-(--sk-ok)' : 'text-(--sk-bad)'"
            />
            <span
              v-if="row.requiredNm > 0"
              class="font-mono text-sm font-semibold tabular-nums text-(--sk-bad)"
            >{{ row.requiredNm.toFixed(3) }} nm 이상 조정</span>
            <span
              v-else-if="row.admitted"
              class="sk-meta"
            >기준 충족</span>
          </div>

          <p class="mt-1 sk-field-label leading-relaxed">
            <template v-if="row.worst">
              최악 쌍 {{ labelFor(row.worst.b) }} 와
              <strong
                class="font-mono"
                :class="row.worst.skewNm > row.thresholdNm ? 'text-(--sk-bad)' : 'text-(--sk-ink)'"
              >{{ row.worst.skewNm.toFixed(3) }} nm</strong>
              (허용 {{ row.thresholdNm.toFixed(3) }} nm<template v-if="row.failingPairs > 1">
                · 초과 쌍 {{ row.failingPairs }}개
              </template>).
            </template>
            <template v-else>
              그룹 구성원과 측정된 쌍이 없습니다.
            </template>
            <template v-if="row.unmeasured.length">
              측정 없음:
              <span
                v-for="member in row.unmeasured"
                :key="member"
                class="sk-badge ml-1 bg-(--sk-chip-bg) text-(--sk-chip-text)"
              >{{ labelFor(member) }}</span>
              — 조정만으로는 부족하고 해당 쌍의 측정이 먼저 필요합니다.
            </template>
          </p>
        </li>
      </ul>
    </template>
  </div>
</template>

<script setup lang="ts">
import type { AdmissionReport } from '~/utils/pmTune'
import { cellLabel } from '~/utils/tttmCells'
import { toolLabels } from '~/utils/toolLabels'

const props = defineProps<{
  report: AdmissionReport | null
  /** True when a primary group exists at all — a null report means two things. */
  hasGroup: boolean
  tools: { eqp_id: string, label: string }[]
  pickedLabel: string
}>()

const labels = computed(() => toolLabels(props.tools))
const labelFor = (eqp: string) => labels.value.labelFor(eqp)

const blockedCells = computed(() =>
  props.report?.cells.filter(row => !row.admitted).length ?? 0
)
</script>
