<template>
  <div class="dashboard-surface rounded-[var(--sk-r-card)] px-5 py-4">
    <p class="sk-title">
      BM/PM Up gate
    </p>

    <template v-if="gate">
      <div class="mt-2 flex flex-wrap items-center gap-2">
        <span class="sk-card-id text-[18px]">{{ eqpId }}</span>
        <span
          class="sk-badge"
          :class="gate.verdict === 'up' ? 'bg-(--sk-ok-soft) text-(--sk-ink)' : 'bg-(--sk-bad-soft) text-(--sk-bad)'"
        >{{ gate.verdict === 'up' ? 'Up 가능' : 'Hold' }}</span>
      </div>

      <div class="mt-2.5 flex flex-wrap items-center gap-1.5">
        <span
          class="sk-badge"
          :class="gate.cd_in_spec ? 'bg-(--sk-ok-soft) text-(--sk-ink)' : 'bg-(--sk-bad-soft) text-(--sk-bad)'"
          :title="`spec [${gate.cd_spec_lower}, ${gate.cd_spec_upper}] nm`"
        >CD_MON {{ gate.cd_monitoring_value.toFixed(2) }}</span>
        <span
          class="sk-badge"
          :class="gate.bsm_in_spec ? 'bg-(--sk-ok-soft) text-(--sk-ink)' : 'bg-(--sk-bad-soft) text-(--sk-bad)'"
          :title="`sharpness ${gate.bsm_sharpness_avg} · noise ${gate.bsm_noise_avg}`"
        >BSM</span>
        <span
          v-if="gate.mdc_changed"
          class="sk-badge bg-(--sk-warn-soft) text-(--sk-ink)"
          title="이번 epoch에서 MDC가 변경됨 — 참고용."
        >MDC 변경</span>
      </div>

      <p class="mt-2.5 sk-field-label leading-relaxed">
        <template v-if="gate.post_pm_at">
          최근 PM 완료 <span class="font-mono">{{ gate.post_pm_at.slice(0, 10) }}</span>.
        </template>
        <template v-else>
          기록된 PM 이력이 없습니다.
        </template>
        <template v-if="gate.prev_post_delta !== null">
          PM 전후 delta <span class="font-mono">{{ formatSignedNm(gate.prev_post_delta, 2) }}</span> (참고용).
        </template>
      </p>
    </template>

    <p
      v-else
      class="mt-2 sk-body text-(--sk-ink-muted)"
    >
      선택한 장비의 gate 데이터가 없습니다.
    </p>
  </div>
</template>

<script setup lang="ts">
import type { GateBlock } from '~/composables/usePmPlanningApi'
import { formatSignedNm } from '~/utils/tttmLimits'

defineProps<{
  gate: GateBlock | null
  /** The picked tool's id; only rendered when `gate` (found from it) exists. */
  eqpId: string | null
}>()
</script>
