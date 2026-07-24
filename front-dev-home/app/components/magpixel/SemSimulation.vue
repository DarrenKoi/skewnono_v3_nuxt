<script setup lang="ts">
import { scanTimeFactor } from '~/utils/magPixel'

const props = defineProps<{
  cdNm: number
  pitchNm: number
  patternCount: number
  pixels: number
  nmPerPx: number
}>()

/** The chosen magnification's FOV is the smallest available one that is at
 *  least the required FOV, and magnifications are discrete — so the real
 *  margin is usually WIDER than the ratio the user asked for. Derive it from
 *  the actual span (pixels × nmPerPx recovers the FOV this preview draws)
 *  so the drawing always matches the numbers printed next to it. */
const fovNm = computed(() => props.pixels * props.nmPerPx)
const spanNm = computed(() => props.patternCount * props.pitchNm)
const marginNm = computed(() => Math.max(0, (fovNm.value - spanNm.value) / 2))
const insetPct = computed(() => (fovNm.value > 0 ? (marginNm.value / fovNm.value) * 100 : 0))
const bandPct = computed(() => Math.max(0, 100 - 2 * insetPct.value))
const unitPct = computed(() => 100 / props.patternCount)
const barPct = computed(() => (props.cdNm / props.pitchNm) * 100)
const spacePct = computed(() => 100 - barPct.value)
const patterns = computed(() => Array.from({ length: props.patternCount }, (_, i) => i))
const pxPerCdValue = computed(() => props.cdNm / props.nmPerPx)
/** 스캔 시간은 magPixel.ts의 scanTimeFactor()로만 구한다 — 512 상수를 컴포넌트에 복제하지 않는다. */
const scanFactor = computed(() => scanTimeFactor(props.pixels))
const hatch = 'repeating-linear-gradient(45deg,rgba(99,102,241,.14) 0 4px,transparent 4px 8px)'
const barFill = 'linear-gradient(90deg,#f2f6fc,#93a3ba 55%,#f2f6fc)'
</script>

<template>
  <div class="flex flex-wrap items-start gap-4">
    <div>
      <div class="mb-1.5 font-mono text-[10px] tracking-wide text-(--sk-ink-muted)">
        {{ pixels }} px · {{ nmPerPx.toFixed(3) }} nm/px
      </div>
      <div class="relative h-52 w-52 overflow-hidden rounded bg-slate-950">
        <div
          class="absolute flex"
          :style="{ left: `${insetPct}%`, top: `${insetPct}%`, width: `${bandPct}%`, height: `${bandPct}%` }"
        >
          <div
            v-for="i in patterns"
            :key="i"
            class="flex h-full"
            :style="{ width: `${unitPct}%` }"
          >
            <div :style="{ width: `${barPct}%`, background: barFill }" />
            <div :style="{ width: `${spacePct}%` }" />
          </div>
        </div>
        <div
          class="absolute border border-dashed border-indigo-400/70"
          :style="{ left: `${insetPct}%`, top: `${insetPct}%`, width: `${bandPct}%`, height: `${bandPct}%` }"
        />
        <div
          class="absolute inset-x-0 top-0"
          :style="{ height: `${insetPct}%`, background: hatch }"
        />
        <div
          class="absolute inset-x-0 bottom-0"
          :style="{ height: `${insetPct}%`, background: hatch }"
        />
        <div
          class="absolute left-0"
          :style="{ top: `${insetPct}%`, height: `${bandPct}%`, width: `${insetPct}%`, background: hatch }"
        />
        <div
          class="absolute right-0"
          :style="{ top: `${insetPct}%`, height: `${bandPct}%`, width: `${insetPct}%`, background: hatch }"
        />
      </div>
      <div class="mt-1.5 font-mono text-[10px] text-indigo-400">
        빗금 = 여유 마진 (상하좌우 각 {{ Math.round(insetPct) }}%)
      </div>
    </div>

    <dl class="min-w-40 flex-1 font-mono text-[11.5px] leading-relaxed">
      <div class="flex justify-between">
        <dt class="text-(--sk-ink-muted)">
          픽셀 크기
        </dt>
        <dd>{{ nmPerPx.toFixed(3) }} nm</dd>
      </div>
      <div class="flex justify-between">
        <dt class="text-(--sk-ink-muted)">
          CD당 픽셀
        </dt>
        <dd>{{ pxPerCdValue.toFixed(1) }}</dd>
      </div>
      <div class="flex justify-between">
        <dt class="text-(--sk-ink-muted)">
          스캔 시간
        </dt>
        <dd>×{{ scanFactor ?? '—' }}</dd>
      </div>
    </dl>
  </div>
</template>
