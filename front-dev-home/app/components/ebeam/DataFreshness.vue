<template>
  <div
    class="sk-fresh"
    :title="tooltip"
  >
    <span
      class="sk-fresh__beacon"
      aria-hidden="true"
    >
      <span class="sk-fresh__ping" />
      <span class="sk-fresh__core" />
    </span>
    <span class="sk-fresh__text">
      <span class="sk-fresh__kicker">{{ label }}</span>
      <span class="sk-fresh__readout">
        <span
          v-if="asOf"
          class="sk-fresh__stamp tabular-nums"
        >{{ asOf }}</span>
        <span
          v-if="asOf && cadence"
          class="sk-fresh__sep"
        >·</span>
        <span
          v-if="cadence"
          class="sk-fresh__cadence"
        >{{ cadence }}</span>
      </span>
    </span>
  </div>
</template>

<script setup lang="ts">
// Compact "telemetry readout" badge for the feature-header #meta slot.
// Surfaces how current the data is — the data-as-of date (`asOf`, e.g. an
// API anchor_date) and/or the refresh cadence (`cadence`, e.g. "1시간 주기").
// Show whichever the caller actually knows; both are optional so we never
// fabricate freshness the backend can't vouch for.
const props = withDefaults(defineProps<{
  asOf?: string
  cadence?: string
  label?: string
}>(), {
  asOf: '',
  cadence: '',
  label: '데이터 기준'
})

const tooltip = computed(() => {
  const parts: string[] = []
  if (props.asOf) parts.push(`데이터 기준 ${props.asOf}`)
  if (props.cadence) parts.push(`${props.cadence}로 갱신`)
  return parts.join(' · ')
})
</script>

<style scoped>
.sk-fresh {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.3125rem 0.625rem 0.3125rem 0.5rem;
  border-radius: 0.625rem;
  border: 1px solid var(--sk-border-soft);
  background: var(--sk-muted-surface);
}

.sk-fresh__beacon {
  position: relative;
  display: inline-flex;
  width: 0.5rem;
  height: 0.5rem;
  flex: none;
}

.sk-fresh__core,
.sk-fresh__ping {
  position: absolute;
  inset: 0;
  border-radius: 9999px;
  background: var(--sk-accent);
}

.sk-fresh__ping {
  opacity: 0.5;
  animation: sk-fresh-ping 2.4s cubic-bezier(0, 0, 0.2, 1) infinite;
}

@keyframes sk-fresh-ping {
  0% { transform: scale(1); opacity: 0.5; }
  70%, 100% { transform: scale(2.6); opacity: 0; }
}

.sk-fresh__text {
  display: flex;
  flex-direction: column;
  line-height: 1.15;
}

.sk-fresh__kicker {
  font-size: 9px;
  font-weight: 600;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--sk-ink-subtle);
}

.sk-fresh__readout {
  display: inline-flex;
  align-items: center;
  gap: 0.3125rem;
  font-size: 11.5px;
  font-weight: 600;
}

.sk-fresh__stamp {
  font-variant-numeric: tabular-nums;
  color: var(--sk-ink);
}

.sk-fresh__sep {
  color: var(--sk-ink-subtle);
}

.sk-fresh__cadence {
  color: var(--sk-accent);
}

@media (prefers-reduced-motion: reduce) {
  .sk-fresh__ping {
    animation: none;
  }
}
</style>
