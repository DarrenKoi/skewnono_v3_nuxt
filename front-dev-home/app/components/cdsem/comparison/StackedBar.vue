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
        v-if="showValues && seg.share >= VALUE_MIN_SHARE"
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
import { paraTotal } from '~/utils/lotHealth'

// cap 초과 줄무늬는 없어졌습니다. 그 줄무늬는 프런트엔드 mock 의 para 티어별 cap
// (para_16_max …)에서 나왔는데, 실제 룰에는 그런 축이 없습니다 — 파라미터 종류별
// (WAFER/LEVEL/EDGE/…) 상한을 recipe 단위로 봅니다. 티어로 되돌릴 방법이 없어,
// 지어내지 않고 뺐습니다. cap 위반은 이제 health/violations 열이 말합니다.
//
// row 는 para 네 칸만 요구하는 **구조적** 타입입니다. lot 요약 한 행이든 recipe
// 한 줄이든 같은 막대를 그려야 하고, 두 벌로 나뉘면 색이나 서열이 갈라집니다.
const props = withDefaults(defineProps<{
  row: {
    para_16: number
    para_13: number
    para_9: number
    para_5: number
  }
  /** 스크린 리더가 읽을 이름 — lot_cd 또는 recipe_id. */
  label?: string
  height?: number
  showValues?: boolean
  normalize?: boolean
  maxTotal?: number
}>(), {
  label: '',
  height: 18,
  showValues: false,
  normalize: true,
  maxTotal: 0
})

// 값을 띄울지 말지는 막대에서 이 조각이 차지하는 **비율**로 정합니다. 예전에는
// 원시 개수를 0.08 과 비교해서 1 이상이면 무조건 참이었고, 폭이 2px 인 조각
// 안에도 숫자를 밀어 넣어 옆 조각 위로 흘러넘쳤습니다.
//
// 0.04 인 이유: showValues 를 켜는 곳은 상세 모달의 전폭 막대 하나뿐이고
// (약 1300px), 그 4% 는 52px — 네 자리 숫자가 들어가고 남습니다. 더 좁은
// 막대에서 값을 켜게 되면 이 값을 prop 으로 올려야 합니다.
const VALUE_MIN_SHARE = 0.04

const colorMode = useColorMode()

const palette = computed(() => colorMode.value === 'dark' ? paraColorsDark : paraColors)

const total = computed(() => paraTotal(props.row))

const segments = computed(() => {
  const r = props.row
  const sum = total.value
  return paraOrder.map(key => ({
    key,
    label: key,
    value: r[key],
    color: palette.value[key],
    flex: r[key],
    share: sum > 0 ? r[key] / sum : 0
  }))
})

const emptyFlex = computed(() => {
  if (props.normalize || !props.maxTotal) return 0
  return Math.max(0, props.maxTotal - total.value)
})

const ariaLabel = computed(() => {
  const r = props.row
  const name = props.label ? `${props.label} ` : ''
  return `${name}parameter stack — para_16:${r.para_16}, para_13:${r.para_13}, para_9:${r.para_9}, para_5:${r.para_5}`
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
  overflow: hidden;
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
  font: 600 13px/1 var(--font-mono, ui-monospace);
  font-variant-numeric: tabular-nums;
  color: rgba(255, 255, 255, 0.96);
  text-shadow: 0 1px 0 rgba(0, 0, 0, 0.25);
  padding: 0 4px;
}

.stack-bar__empty {
  background: transparent;
}
</style>
