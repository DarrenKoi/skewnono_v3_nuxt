<template>
  <div
    class="stack-bar"
    :style="{ '--bar-height': `${height}px` }"
    :aria-label="ariaLabel"
    role="img"
  >
    <div
      v-for="seg in segments"
      :key="seg.key"
      class="stack-bar__seg"
      :style="{ flex: seg.flex, background: seg.color }"
      :title="`${seg.label}: ${seg.value}`"
    >
      <span
        v-if="showValues && seg.flex >= 0.08"
        class="stack-bar__val"
      >{{ seg.value }}</span>
    </div>
    <div
      v-if="emptyFlex > 0"
      class="stack-bar__empty"
      :style="{ flex: emptyFlex }"
    />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useColorMode } from '#imports'
import { paraColors, paraColorsDark, paraOrder } from './healthTokens'
import { paraTotal, type HealthAugmentedRow } from '~/utils/lotHealth'

// cap 초과 줄무늬는 없어졌습니다. 그 줄무늬는 프런트엔드 mock 의 para 티어별 cap
// (para_16_max …)에서 나왔는데, 실제 룰에는 그런 축이 없습니다 — 파라미터 종류별
// (WAFER/LEVEL/EDGE/…) 상한을 recipe 단위로 봅니다. 티어로 되돌릴 방법이 없어,
// 지어내지 않고 뺐습니다. cap 위반은 이제 health/violations 열이 말합니다.
const props = withDefaults(defineProps<{
  row: HealthAugmentedRow
  height?: number
  showValues?: boolean
  normalize?: boolean
  maxTotal?: number
}>(), {
  height: 18,
  showValues: false,
  normalize: true,
  maxTotal: 0
})

const colorMode = useColorMode()

const palette = computed(() => colorMode.value === 'dark' ? paraColorsDark : paraColors)

const segments = computed(() => {
  const r = props.row
  return paraOrder.map(key => ({
    key,
    label: key,
    value: r[key] as number,
    color: palette.value[key],
    flex: r[key] as number
  }))
})

const emptyFlex = computed(() => {
  if (props.normalize || !props.maxTotal) return 0
  return Math.max(0, props.maxTotal - paraTotal(props.row))
})

const ariaLabel = computed(() => {
  const r = props.row
  return `${r.lot_cd} parameter stack — para_16:${r.para_16}, para_13:${r.para_13}, para_9:${r.para_9}, para_5:${r.para_5}`
})
</script>

<style scoped>
.stack-bar {
  display: flex;
  height: var(--bar-height);
  width: 100%;
  border-radius: 4px;
  overflow: hidden;
  background: var(--sk-muted-surface);
  box-shadow: inset 0 0 0 1px var(--sk-border-soft);
}

.stack-bar__seg {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  min-width: 2px;
  border-right: 1px solid rgba(255, 255, 255, 0.35);
  transition: filter 120ms ease;
}

.stack-bar__seg:last-of-type {
  border-right: none;
}

.stack-bar__seg:hover {
  filter: brightness(1.08);
}

.stack-bar__val {
  font: 600 10px/1 var(--font-mono, ui-monospace);
  font-variant-numeric: tabular-nums;
  color: rgba(255, 255, 255, 0.96);
  text-shadow: 0 1px 0 rgba(0, 0, 0, 0.25);
  padding: 0 4px;
}

.stack-bar__empty {
  background: transparent;
}
</style>
