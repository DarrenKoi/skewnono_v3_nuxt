<template>
  <div
    class="dashboard-surface rounded-[var(--sk-r-card)] px-5 py-4"
    :style="{ backgroundImage: lead ? 'linear-gradient(var(--sk-bad-tint), var(--sk-bad-tint))' : undefined }"
  >
    <p class="sk-eyebrow">
      그룹에서 빠진 장비
    </p>

    <template v-if="lead">
      <p class="mt-1.5 font-mono text-[22px] font-bold leading-tight tracking-[-0.01em] text-(--sk-ink)">
        {{ labelFor(lead.eqp_id) }}
      </p>

      <!-- Why it is out, in the units the decision was made in. The blocking
           pair is against a GROUP MEMBER, never this tool's worst pair overall —
           see excludedTools() in utils/tttmCells. -->
      <p class="mt-2 sk-field-label leading-relaxed">
        <template v-if="lead.blocker && lead.cell">
          {{ cellLabel(lead.cell) }} 셀에서 {{ labelFor(lead.blocker.b) }} 와
          <strong class="font-mono text-(--sk-bad)">{{ lead.blocker.skewNm.toFixed(3) }} nm</strong>
          — tolerance {{ lead.thresholdNm.toFixed(3) }} nm 초과.
        </template>
        <template v-else>
          그룹 안의 어떤 장비와도 겹치는 측정이 없어 N배화를 판정할 수 없습니다.
        </template>
        <template v-if="leadDeviation !== null">
          잔차 {{ signed(leadDeviation) }} nm 로 PM/BM 한계 ±{{ actionLimit.toFixed(3) }} nm
          {{ Math.abs(leadDeviation) > actionLimit ? '초과' : '안쪽' }}.
        </template>
      </p>

      <!-- `label` already spells out whether the MDC moved ("PM + MDC 변경
           (epoch 리셋)"), so nothing is appended to it — doing so printed the
           parenthetical twice. -->
      <p
        v-if="leadEpoch"
        class="mt-2 sk-field-label"
      >
        {{ leadEpoch.date }} {{ leadEpoch.label }}
      </p>

      <!-- Everyone else who is out. The lead gets the explanation because it is
           the pair that most exceeded its own cell's allowance; the rest still
           have to be nameable, or the card reads as if one tool were the only
           thing between the user and a full group. -->
      <div
        v-if="rest.length"
        class="mt-3 flex flex-wrap items-center gap-1.5 border-t border-(--sk-border-soft) pt-3"
      >
        <span class="sk-field-label">함께 빠짐</span>
        <span
          v-for="t in rest"
          :key="t.eqp_id"
          class="rounded-[var(--sk-r-chip)] bg-(--sk-bad-soft) px-2 py-0.5 font-mono text-xs text-(--sk-bad)"
          :title="pairTitle(t)"
        >{{ labelFor(t.eqp_id) }}</span>
      </div>
    </template>

    <p
      v-else
      class="mt-1.5 sk-body text-(--sk-ink-muted)"
    >
      <template v-if="hasGroup">
        선택한 장비가 모두 1차 추천 그룹에 들어 있습니다.
      </template>
      <template v-else>
        현재 tolerance에서는 그룹 자체가 만들어지지 않아, 빠진 장비를 말할 기준이 없습니다.
      </template>
    </p>
  </div>
</template>

<script setup lang="ts">
import { cellLabel, type ExcludedTool } from '~/utils/tttmCells'
import { toolLabels } from '~/utils/toolLabels'
import type { EpochMarker, ToolRef } from '~/composables/useTttmApi'

const props = defineProps<{
  excluded: ExcludedTool[]
  /** True when a primary group exists at all — an empty list means two things. */
  hasGroup: boolean
  tools: ToolRef[]
  /** Re-based consensus deviation for the current selection, by eqp_id. */
  deviations: Record<string, number>
  /** PM/BM limit in nm for the CD behind today's fleet numbers. */
  actionLimit: number
  markers: EpochMarker[]
}>()

const labels = computed(() => toolLabels(props.tools))
const labelFor = (eqp: string) => labels.value.labelFor(eqp)

// Already sorted worst-first by excludedTools().
const lead = computed(() => props.excluded[0] ?? null)
const rest = computed(() => props.excluded.slice(1))

const leadDeviation = computed(() => {
  const eqp = lead.value?.eqp_id
  if (!eqp) return null
  const d = props.deviations[eqp]
  return d === undefined ? null : d
})

// The most recent epoch event for this tool. A PM that reset the MDC epoch is
// usually the answer to "why is it suddenly out", so it belongs on this card
// rather than only in the timeline at the bottom of the page.
const leadEpoch = computed(() => {
  const eqp = lead.value?.eqp_id
  if (!eqp) return null
  return [...props.markers]
    .filter(m => m.eqp_id === eqp)
    .sort((a, b) => b.date.localeCompare(a.date))[0] ?? null
})

const signed = (v: number) => `${v >= 0 ? '+' : '−'}${Math.abs(v).toFixed(3)}`

const pairTitle = (t: ExcludedTool) =>
  t.blocker && t.cell
    ? `${cellLabel(t.cell)} 셀에서 ${labelFor(t.blocker.b)} 와 ${t.blocker.skewNm.toFixed(3)} nm`
    + ` (기준 ${t.thresholdNm.toFixed(3)} nm)`
    : '그룹 안의 장비와 겹치는 측정 없음'
</script>
