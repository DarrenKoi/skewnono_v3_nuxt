<template>
  <div class="dashboard-surface rounded-[var(--sk-r-card)] px-5 py-4">
    <div class="flex flex-wrap items-baseline justify-between gap-2">
      <p class="sk-title">
        튜닝 목표 — 그룹 중심
      </p>
      <span
        v-if="target?.rows.length"
        class="sk-badge"
        :class="offCount ? 'bg-(--sk-bad-soft) text-(--sk-bad)' : 'bg-(--sk-ok-soft) text-(--sk-ink)'"
      >{{ offCount ? `조정 필요 ${offCount}개` : '전 항목 중심 안쪽' }}</span>
    </div>

    <!-- Every branch below is a DIFFERENT reason for an empty table, and they
         are worded separately on purpose: "no group exists", "no tool picked",
         "this tool is not on the map" and "no member is on the map" would
         otherwise collapse into one line that names the wrong cause. -->
    <p
      v-if="n === 0"
      class="mt-2 sk-body text-(--sk-ink-muted)"
    >
      현재 tolerance에서는 N배화 그룹 자체가 만들어지지 않아, 중심을 정의할 기준이 없습니다.
    </p>

    <p
      v-else-if="!target"
      class="mt-2 sk-body text-(--sk-ink-muted)"
    >
      장비를 선택하면 그 장비를 그룹 중심으로 옮기는 데 필요한 parameter 별 조정량을 보여줍니다.
    </p>

    <p
      v-else-if="!target.placed"
      class="mt-2 sk-body text-(--sk-ink-muted)"
    >
      <strong class="font-mono">{{ labelFor(target.eqp_id) }}</strong> 는 고른 parameter
      ({{ target.parameters.join(', ') }}) 중 측정하지 않은 것이 있어 배치도에 놓이지 않습니다 —
      중심까지의 거리를 낼 수 없습니다. 위 분석 조건에서 이 장비가 측정한 parameter 만 고르시면
      계산됩니다.
    </p>

    <p
      v-else-if="!target.rows.length"
      class="mt-2 sk-body text-(--sk-ink-muted)"
    >
      1차 그룹 구성원 중 이 parameter 들을 모두 측정한 장비가 없어 중심을 낼 수 없습니다.
    </p>

    <template v-else>
      <!-- Stated once above the rows: the target is a POSITION, not a verdict.
           Every row is a distance to that one point, so the reader has to know
           which point before reading any of them — and that it is the point the
           배치도 already draws its ring around, not a second calculation. -->
      <p class="mt-1.5 sk-field-label leading-relaxed">
        왼쪽 <strong>장비 그룹 배치도</strong>의 1차 그룹 {{ target.members }}대가 만드는
        중심(무게중심)이 목표 좌표입니다. parameter 마다 지금 위치와 그 중심의 차이가
        <strong>조정량</strong>입니다.
        <template v-if="target.inGroup">
          이 장비도 구성원이라 중심을 함께 만듭니다 — 유지가 목표입니다.
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
              <td class="px-3 py-2 text-right font-mono tabular-nums text-(--sk-ink-muted)">
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
              <td class="px-3 py-2 text-right font-mono tabular-nums text-(--sk-ink-muted)">
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
        값은 모두 fleet median 기준 offset (nm) 입니다 · 허용은 각 parameter 자신의 CD 대비
        {{ ACTION_LIMIT_PERCENT }}% 에 tolerance 를 곱한 값이라 parameter 마다 다릅니다.
        허용은 원래 <strong>쌍</strong>에 대한 기준이며 여기서는 중심까지의 거리를 재는 잣대로
        쓰므로, 중심 안쪽에 들어와도 개별 쌍 판정(N배화)은 위 요약 바를 보십시오.
      </p>
    </template>
  </div>
</template>

<script setup lang="ts">
// 셀 단위 진입 조건에서 parameter 단위 중심 좌표로 바뀌었습니다 (2026-08-28).
//
// 이전 표는 pmAdmission 의 점유 셀별 "최악 쌍 · 필요 조정량" 목록이었고 고른
// parameter 와 아무 관계가 없었습니다 — 분석 조건에서 parameter 를 골라도 이
// 카드는 그대로였고, 기본 선택 장비(PM 직후 장비)는 대개 이미 1차 그룹
// 구성원이라 표가 아예 없는 문장 한 줄만 남았습니다.
//
// 셀별 미충족 내역은 위 요약 바가 "미충족 셀 N개 · 최대 조정 X nm" 로 계속
// 말합니다 — admissionReport 는 그대로 살아 있습니다. 이 카드는 이제 그 판정이
// 아니라 좌표 하나를 가리킵니다.
import type { TuningTarget } from '~/utils/pmTuningTarget'
import { ACTION_LIMIT_PERCENT, formatSignedNm } from '~/utils/tttmLimits'
import { toolLabels } from '~/utils/toolLabels'

const props = defineProps<{
  /** null = nothing to aim at; `n` says whether that is "no group" or "no pick". */
  target: TuningTarget | null
  /** The primary group's size; 0 = no group exists (a null target means two things). */
  n: number
  tools: { eqp_id: string, label: string }[]
}>()

const labels = computed(() => toolLabels(props.tools))
const labelFor = (eqp: string) => labels.value.labelFor(eqp)

const offCount = computed(() => props.target?.rows.filter(r => !r.withinTolerance).length ?? 0)
</script>
