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

// SEM line-scan brightness, dark field with a bright rim where the beam
// catches the sidewall and a duller top/interior. Hard stops rather than a
// soft gradient so the rim reads as an edge, not a shading trick.
const RIM = '#f4f7ff'
const CORE = '#4c5666'
const BG = '#0a0e16'
const RIM_PCT = 14
const barFill = `linear-gradient(90deg, ${RIM} 0%, ${RIM} ${RIM_PCT}%, ${CORE} ${RIM_PCT}%, ${CORE} ${100 - RIM_PCT}%, ${RIM} ${100 - RIM_PCT}%, ${RIM} 100%)`

// ── Zoom inset: the one place pixels are actually drawn ────────────────────
//
// The full-FOV panel above cannot honestly show individual pixels — 512 to
// 4096 samples across a ~200px box is always sub-pixel, so drawing a "pixel
// grid" there would be pretending. Instead this crops to exactly ONE pitch
// period and renders every real pixel that lands on it. Pixel count here is
// pitchNm / nmPerPx, which DOES move with the pixel setting — unlike the
// panel above, whose geometry is pixel-count-invariant (fovNm = pixels ×
// nmPerPx cancels pixels out of every percentage used there). This is the one
// place stepping 512 → 1024 is actually visible.
const MAX_INSET_CELLS = 240
const rawInsetCells = computed(() => props.nmPerPx > 0 ? props.pitchNm / props.nmPerPx : 0)
const insetCellCount = computed(() => Math.min(MAX_INSET_CELLS, Math.max(1, Math.round(rawInsetCells.value))))
const insetClamped = computed(() => rawInsetCells.value > MAX_INSET_CELLS)
const insetCellWidthNm = computed(() => props.pitchNm / insetCellCount.value)
const insetCellPct = computed(() => 100 / insetCellCount.value)

/** One cell's brightness: bright rim near a bar/space boundary, mid-tone bar
 *  interior, dark background — same three-colour palette as the panel above,
 *  but assigned per pixel instead of per bar, so the grid is what's visible. */
const insetCellColor = (index: number) => {
  const x = (index + 0.5) * insetCellWidthNm.value
  const spaceNm = props.pitchNm - props.cdNm
  const bloomNm = Math.min(insetCellWidthNm.value * 1.5, props.cdNm / 2, spaceNm / 2)
  const edgeDist = Math.min(x, Math.abs(x - props.cdNm), Math.abs(props.pitchNm - x))
  if (bloomNm > 0 && edgeDist <= bloomNm) return RIM
  return x < props.cdNm ? CORE : BG
}
const insetCells = computed(() => Array.from({ length: insetCellCount.value }, (_, i) => insetCellColor(i)))
</script>

<template>
  <div class="space-y-3">
    <p class="sk-meta italic">
      시뮬레이션 — 실제로 촬영된 이미지가 아니라, 설정값으로 예상한 이미지입니다.
    </p>

    <div class="flex flex-wrap items-start gap-5">
      <div>
        <div class="sk-eyebrow">
          전체 FOV · {{ pixels }} px · {{ nmPerPx.toFixed(3) }} nm/px
        </div>
        <div class="relative mt-1.5 h-52 w-52 overflow-hidden rounded-lg bg-slate-950">
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
        <div class="mt-1.5 sk-meta text-indigo-500 dark:text-indigo-400">
          빗금 = 여유 마진 (상하좌우 각 {{ Math.round(insetPct) }}%)
        </div>
      </div>

      <div>
        <div class="sk-eyebrow">
          1 Pitch 확대(zoom) · 픽셀 {{ insetCellCount }}개{{ insetClamped ? ` · 최대 ${MAX_INSET_CELLS}개만 표시` : '' }}
        </div>
        <div class="mt-1.5 flex h-24 w-52 overflow-hidden rounded-lg bg-slate-950">
          <div
            v-for="(color, i) in insetCells"
            :key="i"
            :style="{ width: `${insetCellPct}%`, background: color }"
          />
        </div>
        <div class="mt-1.5 max-w-52 sk-meta">
          실제 픽셀 하나하나를 그린 확대 뷰입니다. 512와 1024를 비교하면 경계가 몇 칸에 걸쳐 퍼지는지가 달라집니다 — 칸이 많을수록(픽셀이 클수록) 경계가 더 촘촘하게, 즉 더 또렷하게 잡힙니다.
        </div>
      </div>

      <dl class="min-w-40 flex-1 font-mono text-[11.5px] leading-relaxed">
        <div class="flex justify-between">
          <dt class="sk-meta">
            픽셀 크기
          </dt>
          <dd class="sk-value-num">
            {{ nmPerPx.toFixed(3) }} nm
          </dd>
        </div>
        <div class="flex justify-between">
          <dt class="sk-meta">
            CD당 픽셀
          </dt>
          <dd class="sk-value-num">
            {{ pxPerCdValue.toFixed(1) }}
          </dd>
        </div>
        <div class="flex justify-between">
          <dt class="sk-meta">
            스캔 시간
          </dt>
          <dd class="sk-value-num">
            ×{{ scanFactor ?? '—' }}
          </dd>
        </div>
      </dl>
    </div>
  </div>
</template>
