<template>
  <div class="dashboard-surface min-w-0 rounded-[var(--sk-r-card)] px-5 py-4">
    <div class="flex flex-wrap items-baseline justify-between gap-2">
      <div class="flex flex-wrap items-baseline gap-x-2.5 gap-y-1">
        <p class="sk-title">
          튜닝 목표 — 그룹 중심
        </p>
        <template v-if="pickedTool">
          <span class="sk-card-id text-[16px]">{{ pickedTool }}</span>
          <span
            v-if="pickedModel"
            class="sk-field-label"
          >{{ pickedModel }}</span>
        </template>
      </div>
      <span
        v-if="target?.rows.length"
        class="sk-badge"
        :class="offCount ? 'bg-(--sk-bad-soft) text-(--sk-bad)' : 'bg-(--sk-ok-soft) text-(--sk-ink)'"
      >{{ offCount ? `조정 필요 ${offCount}개` : '전 항목 허용 오차 이내' }}</span>
    </div>

    <!-- Every branch below is a DIFFERENT reason for an empty table, and they
         are worded separately on purpose: "no group exists", "no tool picked",
         "this tool is not on the map" and "no member is on the map" would
         otherwise collapse into one line that names the wrong cause. -->
    <p
      v-if="!pickedTool"
      class="mt-2 sk-body text-(--sk-ink-muted)"
    >
      배치도에서 장비를 클릭하면 튜닝 목표를 확인할 수 있습니다.
    </p>
    <p
      v-else-if="n === 0"
      class="mt-2 sk-body text-(--sk-ink-muted)"
    >
      현재 허용 오차로는 그룹이 없어 튜닝 목표를 계산할 수 없습니다.
    </p>
    <p
      v-else-if="!target"
      class="mt-2 sk-body text-(--sk-ink-muted)"
    >
      측정 항목 데이터가 없어 튜닝 목표를 계산할 수 없습니다.
    </p>

    <p
      v-else-if="!target.placed"
      class="mt-2 sk-body text-(--sk-ink-muted)"
    >
      선택한 장비에 누락된 측정 항목이 있어 조정량을 계산할 수 없습니다.
    </p>

    <p
      v-else-if="!target.rows.length"
      class="mt-2 sk-body text-(--sk-ink-muted)"
    >
      그룹에서 선택한 항목을 모두 측정한 장비가 없어 중심을 계산할 수 없습니다.
    </p>

    <template v-else>
      <!-- Stated once above the rows: the target is a POSITION, not a verdict.
           Every row is a distance to that one point, so the reader has to know
           which point before reading any of them — and that it is the point the
           배치도 already draws its ring around, not a second calculation. -->
      <p class="mt-1.5 sk-field-label leading-relaxed">
        그룹 {{ target.members }}대의 중심까지 필요한 항목별 조정량입니다.
        <template v-if="target.inGroup">
          선택한 장비는 이미 이 그룹에 속합니다.
        </template>
      </p>

      <div class="mt-2.5 overflow-x-auto">
        <table class="min-w-full text-left text-xs">
          <thead class="bg-(--sk-muted-surface) text-(--sk-ink-muted)">
            <tr>
              <th class="px-3 py-2 sk-label">
                parameter
              </th>
              <th class="px-3 py-2 text-right sk-label">
                현재
              </th>
              <th class="px-3 py-2 text-right sk-label">
                그룹 중심
              </th>
              <th class="px-3 py-2 text-right sk-label">
                조정량
              </th>
              <th class="px-3 py-2 text-right sk-label">
                허용
              </th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="row in target.rows"
              :key="row.name"
              class="border-t border-(--sk-border-soft)"
              :style="row.withinTolerance ? undefined : { backgroundImage: 'linear-gradient(var(--sk-bad-tint), var(--sk-bad-tint))' }"
            >
              <td class="px-3 py-2">
                <span class="sk-value-num">{{ row.name }}</span>
                <span class="ml-1.5 sk-field-label">CD {{ row.cdNm.toFixed(1) }} nm</span>
              </td>
              <td class="px-3 py-2 text-right font-mono tabular-nums text-(--sk-ink)">
                {{ formatSignedNm(row.currentNm) }}
              </td>
              <!-- Full ink, like every other value in the row. DESIGN.md:
                   "data values always get full ink; muted ink is for labels
                   only" — and this is the one the card is named after. The
                   hierarchy is carried by WEIGHT on 조정량 below, never by
                   dimming a number: muted ink on a value column washes out in
                   dark mode beside its full-ink neighbours. -->
              <td class="px-3 py-2 text-right font-mono tabular-nums text-(--sk-ink)">
                {{ formatSignedNm(row.centroidNm) }}
              </td>
              <!-- The instruction, and the only bold column: everything else on
                   the row exists to explain this one number. -->
              <td
                class="px-3 py-2 text-right font-mono font-semibold tabular-nums"
                :class="row.withinTolerance ? 'text-(--sk-ink)' : 'text-(--sk-bad)'"
              >
                {{ formatSignedNm(row.deltaNm) }}
              </td>
              <td class="px-3 py-2 text-right font-mono tabular-nums text-(--sk-ink)">
                <UIcon
                  :name="row.withinTolerance ? 'i-lucide-check' : 'i-lucide-move-down-right'"
                  class="mr-1 inline-block h-3.5 w-3.5 align-[-2px]"
                  :class="row.withinTolerance ? 'text-(--sk-ok)' : 'text-(--sk-bad)'"
                />±{{ row.toleranceNm.toFixed(3) }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <p class="mt-2 sk-field-label leading-relaxed">
        단위는 nm이며, +는 높임, −는 낮춤입니다. 중심에 맞추어도 모든 장비쌍의 허용 오차 충족을 보장하지는 않습니다.
      </p>
    </template>
  </div>
</template>

<script setup lang="ts">
import type { ToolRef } from '~/composables/useTttmApi'
import type { TuningTarget } from '~/utils/pmTuningTarget'
import { formatSignedNm } from '~/utils/tttmLimits'

const props = defineProps<{
  pickedTool: string | null
  target: TuningTarget | null
  /** The primary group's size; 0 = no group exists (a null target means two things). */
  n: number
  /** The payload's tools, narrowed to the comparison — labels and models. */
  tools: ToolRef[]
}>()

const pickedModel = computed(() =>
  props.tools.find(t => t.eqp_id === props.pickedTool)?.eqp_model_cd ?? ''
)

const offCount = computed(() => props.target?.rows.filter(r => !r.withinTolerance).length ?? 0)
</script>
