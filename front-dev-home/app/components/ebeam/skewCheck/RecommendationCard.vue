<template>
  <div class="dashboard-surface rounded-2xl p-5">
    <p class="text-xs text-(--sk-ink-subtle)">
      1차 추천 (최대 N배화)
    </p>

    <div
      v-if="primary"
      class="mt-2"
    >
      <div class="flex items-center gap-2 flex-wrap">
        <span
          v-for="t in primary.tools"
          :key="t"
          class="px-2.5 py-1 rounded-lg text-sm font-medium"
          :style="{ background: 'var(--sk-ok-soft)', color: 'var(--sk-ok)' }"
        >{{ labelFor(t) }}</span>
        <span class="ml-1 text-sm text-(--sk-ink-muted)">N = {{ primary.n }}</span>
      </div>
      <p class="mt-2 text-sm text-(--sk-ink-muted)">
        최약 장비쌍 스큐 {{ primary.weakestPairSkew.toFixed(3) }} nm ·
        신뢰도 <span :style="{ color: confColor }">{{ primary.confidence }}</span>
        <span v-if="primary.tier === 'predicted'"> · 예측 tier</span>
      </p>
    </div>

    <p
      v-else
      class="mt-2 text-sm text-(--sk-bad)"
    >
      현재 tolerance에서 모든 점유 셀을 동시에 만족하는 N배화 그룹이 없습니다.
    </p>

    <div
      v-if="others.length"
      class="mt-4"
    >
      <p class="text-xs text-(--sk-ink-subtle)">
        다른 후보 그룹
      </p>
      <div class="mt-1 flex flex-wrap gap-2">
        <span
          v-for="(g, i) in others"
          :key="i"
          class="px-2 py-0.5 rounded-md text-xs text-(--sk-ink-muted)"
          :style="{ background: 'var(--sk-muted-surface)' }"
        >{{ g.tools.map(labelFor).join(' · ') }} (N={{ g.n }})</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { NbaGroup } from '~/utils/skewGrouping'
import type { ToolRef } from '~/composables/useSkewCheckApi'

const props = defineProps<{
  primary: NbaGroup | null
  others: NbaGroup[]
  tools: ToolRef[]
}>()

const labelFor = (eqp: string) =>
  props.tools.find(t => t.eqp_id === eqp)?.label ?? eqp

const confColor = computed(() => {
  if (!props.primary) return 'var(--sk-ink)'
  return props.primary.confidence === 'High'
    ? 'var(--sk-ok)'
    : props.primary.confidence === 'Low'
      ? 'var(--sk-bad)'
      : 'var(--sk-accent)'
})
</script>
