<template>
  <div class="dashboard-surface rounded-2xl p-5">
    <p class="text-xs text-(--sk-ink-subtle)">
      오늘 함대 skew 현황
    </p>
    <div class="mt-3 space-y-2">
      <div
        v-for="d in sorted"
        :key="d.eqp_id"
        class="flex items-center gap-3 text-sm"
      >
        <span class="w-24 text-(--sk-ink-muted)">{{ labelFor(d.eqp_id) }}</span>
        <div class="flex-1 relative h-4">
          <div
            class="absolute inset-y-0 left-1/2 w-px"
            :style="{ background: 'var(--sk-border)' }"
          />
          <div
            class="absolute inset-y-0.5 rounded"
            :style="barStyle(d.deviation)"
          />
        </div>
        <span
          class="w-16 text-right tabular-nums"
          :style="{ color: Math.abs(d.deviation) > 0.05 ? 'var(--sk-bad)' : 'var(--sk-ink)' }"
        >{{ d.deviation >= 0 ? '+' : '' }}{{ d.deviation.toFixed(3) }}</span>
      </div>
    </div>
    <p class="mt-2 text-[11px] text-(--sk-ink-subtle)">
      잔차 = tool − consensus(기준값). 0 = 함대 합의와 일치.
    </p>
  </div>
</template>

<script setup lang="ts">
import type { FleetToday, ToolRef } from '~/composables/useSkewCheckApi'

const props = defineProps<{ fleet: FleetToday, tools: ToolRef[] }>()

const labelFor = (eqp: string) => props.tools.find(t => t.eqp_id === eqp)?.label ?? eqp

const maxAbs = computed(() =>
  Math.max(0.05, ...props.fleet.consensus_deviation.map(d => Math.abs(d.deviation)))
)
const sorted = computed(() =>
  [...props.fleet.consensus_deviation].sort((a, b) => a.deviation - b.deviation)
)

// Bar grows from the center line toward the sign direction.
const barStyle = (dev: number) => {
  const half = (Math.abs(dev) / maxAbs.value) * 50
  const ok = Math.abs(dev) <= 0.05
  const bg = ok ? 'var(--sk-ok)' : 'var(--sk-bad)'
  return dev >= 0
    ? { left: '50%', width: `${half}%`, background: bg }
    : { right: '50%', width: `${half}%`, background: bg }
}
</script>
