<script setup lang="ts">
// 두 제약을 각각 담당하는 2단 구성이다.
//   ① 전체 FOV      — 패턴 N개 + 마진이 들어오는가 (FOV 제약)
//   ② Pitch 1개 확대 — CD에 픽셀이 몇 개 얹히는가 (픽셀 제약)
const props = defineProps<{
  cdNm: number
  pitchNm: number
  patternCount: number
  marginRatio: number
  fovNm: number
  nmPerPx: number
}>()

/** 패턴 밴드가 FOV에서 차지하는 비율. 나머지는 좌우 마진으로 나뉜다. */
const bandPct = computed(() => (1 - 2 * props.marginRatio) * 100)
const marginPct = computed(() => props.marginRatio * 100)
const marginNm = computed(() => Math.round(props.fovNm * props.marginRatio))
const spanNm = computed(() => Math.round(props.patternCount * props.pitchNm))

const barPct = computed(() => (props.cdNm / props.pitchNm) * 100)
const spacePct = computed(() => 100 - barPct.value)

/** 확대 뷰에서 pitch 하나에 걸치는 픽셀 수. */
const pxPerPitch = computed(() => props.pitchNm / props.nmPerPx)
const pxStepPct = computed(() => 100 / pxPerPitch.value)
const pxPerCdValue = computed(() => props.cdNm / props.nmPerPx)

const patterns = computed(() => Array.from({ length: props.patternCount }, (_, i) => i))
const unitPct = computed(() => 100 / props.patternCount)
const hatch = 'repeating-linear-gradient(45deg,rgba(99,102,241,.18) 0 4px,transparent 4px 8px)'
const barFill = 'linear-gradient(90deg,#e8eef7,#9aa8bd 55%,#e8eef7)'
</script>

<template>
  <div>
    <div class="mb-1.5 font-mono text-[10px] tracking-wide text-(--sk-ink-muted)">
      ① 전체 FOV {{ Math.round(fovNm).toLocaleString() }} nm — 패턴 {{ patternCount }}개 · 마진 {{ marginNm }} nm
    </div>
    <div class="flex h-14 overflow-hidden rounded bg-slate-900">
      <div
        :style="{ width: `${marginPct}%`, background: hatch }"
        class="border-r border-dashed border-indigo-400/70"
      />
      <div
        class="flex"
        :style="{ width: `${bandPct}%` }"
      >
        <div
          v-for="i in patterns"
          :key="i"
          class="flex"
          :style="{ width: `${unitPct}%` }"
        >
          <div :style="{ width: `${barPct}%`, background: barFill }" />
          <div :style="{ width: `${spacePct}%` }" />
        </div>
      </div>
      <div
        :style="{ width: `${marginPct}%`, background: hatch }"
        class="border-l border-dashed border-indigo-400/70"
      />
    </div>
    <div class="mt-1.5 flex font-mono text-[10px]">
      <div
        class="text-center text-indigo-400"
        :style="{ width: `${marginPct}%` }"
      >
        {{ marginNm }}
      </div>
      <div
        class="text-center text-(--sk-ink-muted)"
        :style="{ width: `${bandPct}%` }"
      >
        패턴 {{ spanNm.toLocaleString() }} nm
      </div>
      <div
        class="text-center text-indigo-400"
        :style="{ width: `${marginPct}%` }"
      >
        {{ marginNm }}
      </div>
    </div>

    <div class="mb-1.5 mt-4 font-mono text-[10px] tracking-wide text-(--sk-ink-muted)">
      ② Pitch {{ pitchNm }} nm 확대 — 픽셀 경계 {{ pxPerPitch.toFixed(1) }} px
    </div>
    <div class="relative h-16 overflow-hidden rounded bg-slate-900">
      <div class="absolute inset-0 flex">
        <div :style="{ width: `${barPct}%`, background: barFill }" />
        <div :style="{ width: `${spacePct}%` }" />
      </div>
      <div
        class="absolute inset-0"
        :style="{ background: `repeating-linear-gradient(90deg,rgba(239,68,68,.8) 0 1px,transparent 1px ${pxStepPct}%)` }"
      />
      <div
        class="absolute inset-y-0 left-0 border-r border-dashed border-indigo-400"
        :style="{ width: `${barPct}%` }"
      />
    </div>
    <div class="mt-1.5 flex font-mono text-[11px]">
      <div
        class="text-center text-indigo-400"
        :style="{ width: `${barPct}%` }"
      >
        CD {{ cdNm }} · <strong>{{ pxPerCdValue.toFixed(1) }} px</strong>
      </div>
      <div
        class="text-center text-(--sk-ink-muted)"
        :style="{ width: `${spacePct}%` }"
      >
        space {{ (pitchNm - cdNm).toFixed(0) }} nm
      </div>
    </div>
  </div>
</template>
