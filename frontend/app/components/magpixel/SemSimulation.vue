<script setup lang="ts">
import {
  scanTimeFactor, edgeComparePair, edgeWindowHalfNm, edgeStrip, actualMarginNm,
  SEM_EDGE_WIDTH_NM, SEM_LEVELS
} from '~/utils/magPixel'

const props = defineProps<{
  cdNm: number
  pitchNm: number
  patternCount: number
  pixels: number
  nmPerPx: number
}>()

/** pixels × nmPerPx recovers the FOV this preview draws; the margin is derived
 *  from the actual span via actualMarginNm() — same helper as the schematic and
 *  the recommendation panel, so all three agree with the printed numbers. */
const fovNm = computed(() => props.pixels * props.nmPerPx)
const spanNm = computed(() => props.patternCount * props.pitchNm)
const marginNm = computed(() => actualMarginNm(fovNm.value, spanNm.value))
const insetPct = computed(() => (fovNm.value > 0 ? (marginNm.value / fovNm.value) * 100 : 0))
const bandPct = computed(() => Math.max(0, 100 - 2 * insetPct.value))
const unitPct = computed(() => 100 / props.patternCount)
const barPct = computed(() => (props.cdNm / props.pitchNm) * 100)
const spacePct = computed(() => 100 - barPct.value)
const patterns = computed(() => Array.from({ length: props.patternCount }, (_, i) => i))
const pxPerCdValue = computed(() => props.cdNm / props.nmPerPx)
/** 스캔 시간은 magPixel.ts의 scanTimeFactor()로만 구한다 — 512 상수를 컴포넌트에 복제하지 않는다. */
const scanFactor = computed(() => scanTimeFactor(props.pixels))
/** 마진 빗금은 테라코타 — 여유 마진 필터가 만들어내는 값이라 같은 계열로 묶는다. */
const hatch = 'repeating-linear-gradient(45deg,color-mix(in srgb,var(--sk-brand) 26%,transparent) 0 4px,transparent 4px 8px)'

// SEM line-scan brightness, dark field with a bright rim where the beam
// catches the sidewall and a duller top/interior. Hard stops rather than a
// soft gradient so the rim reads as an edge, not a shading trick.
// Kept as RGB triples, not hex, because the zoom strip below interpolates
// between them — one palette, two renderers. The triples are the sRGB
// resolution of --sk-field / --sk-field-core / --sk-field-ink: the same warm
// dark field the CSS uses, spelled numerically because these get mixed in JS.
const RGB = { bg: [27, 24, 20], core: [78, 70, 64], rim: [238, 235, 229] } as const
const css = (c: readonly number[]) => `rgb(${c[0]} ${c[1]} ${c[2]})`
const RIM = css(RGB.rim)
const CORE = css(RGB.core)
const RIM_PCT = 14
const barFill = `linear-gradient(90deg, ${RIM} 0%, ${RIM} ${RIM_PCT}%, ${CORE} ${RIM_PCT}%, ${CORE} ${100 - RIM_PCT}%, ${RIM} ${100 - RIM_PCT}%, ${RIM} 100%)`

// ── Edge zoom: the one place pixels are actually drawn ─────────────────────
//
// The full-FOV panel above cannot honestly show individual pixels — 512 to
// 4096 samples across a ~200px box is always sub-pixel, so drawing a "pixel
// grid" there would be pretending. (Its geometry is pixel-count-invariant
// anyway: fovNm = pixels × nmPerPx cancels `pixels` out of every percentage
// it uses.) So this crops to a narrow window around ONE bar edge and renders
// each real pixel as a countable cell.
//
// Two rules make it honest, and both were broken before:
//   ① the window is fixed in **nm**, so both rows show the same physical
//      region and only the sampling differs — the actual comparison;
//   ② the edge profile comes from magPixel.ts and never sees nmPerPx, so a
//      finer pixel setting cannot make the physical edge look thinner. What
//      it does is land more samples on the same fixed edge.
const comparePair = computed(() => edgeComparePair(props.pixels))
/** FOV is fixed by the magnification, so the other pixel setting's pixel size
 *  follows from it — no extra prop needed, and the two rows cannot drift apart. */
const nmPerPxFor = (pixels: number) => fovNm.value / pixels
const halfWindowNm = computed(() =>
  edgeWindowHalfNm(props.cdNm, props.pitchNm, nmPerPxFor(comparePair.value[0])))
const strips = computed(() => {
  const half = halfWindowNm.value
  if (half === null) return []
  return comparePair.value
    .map(pixels => edgeStrip(pixels, nmPerPxFor(pixels), half))
    .filter((s): s is NonNullable<typeof s> => s !== null)
})
/** Cells are drawn at their true nm width against the shared window scale —
 *  never stretched to make an integer count fill the box. A grid that does not
 *  divide the window evenly overflows and gets clipped, exactly as a real one
 *  would; stretching would quietly redefine what a pixel is. */
const cellPct = (nmPerPx: number) =>
  halfWindowNm.value ? (nmPerPx / (2 * halfWindowNm.value)) * 100 : 0

const lerp = (a: number, b: number, t: number) => Math.round(a + (b - a) * t)
const clamp01 = (v: number) => Math.min(1, Math.max(0, v))
const mix = (a: readonly number[], b: readonly number[], t: number) => {
  const k = clamp01(t)
  return css([lerp(a[0]!, b[0]!, k), lerp(a[1]!, b[1]!, k), lerp(a[2]!, b[2]!, k)])
}
/** Intensity 0..1 → the same three-stop palette the panel above uses. */
const rampColor = (v: number) =>
  v <= SEM_LEVELS.core
    ? mix(RGB.bg, RGB.core, (v - SEM_LEVELS.space) / (SEM_LEVELS.core - SEM_LEVELS.space))
    : mix(RGB.core, RGB.rim, (v - SEM_LEVELS.core) / (SEM_LEVELS.rim - SEM_LEVELS.core))
</script>

<template>
  <!-- display:contents — 아래 네 블록은 부모 카드의 flex 행에 **직접** 참여해야
       한다. 감싸는 상자를 두면 이 컴포넌트가 카드의 오른쪽 절반에 갇히고, 그
       안에서 설명 문단이 세로로 길어지면서 왼쪽 모식도 아래에 큰 빈 공간이
       남는다. 블록을 풀어 두면 모식도와 한 줄로 늘어서고, 설명만 basis-full로
       아래 줄 전체를 차지한다. -->
  <div class="contents">
    <div class="contents">
      <div class="w-52">
        <div class="sk-title">
          전체 FOV · {{ pixels }} px · {{ nmPerPx.toFixed(3) }} nm/px
        </div>
        <div class="relative mt-1.5 h-52 w-52 overflow-hidden rounded-[var(--sk-r-nav)] bg-(--sk-field)">
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
            class="absolute border border-dashed border-(--sk-brand)"
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
        <div class="mt-1.5 sk-meta text-(--sk-brand-ink)">
          빗금 = 여유 마진 (상하좌우 각 {{ Math.round(insetPct) }}%)
        </div>
      </div>

      <div
        v-if="strips.length && halfWindowNm"
        class="w-72"
      >
        <div class="sk-title">
          경계 확대(zoom) · 가로 {{ (2 * halfWindowNm).toFixed(1) }} nm
        </div>

        <div
          v-for="strip in strips"
          :key="strip.pixels"
          class="mt-2"
        >
          <div class="flex items-baseline justify-between font-mono text-xs">
            <span :class="strip.pixels === pixels ? 'font-semibold text-(--sk-brand-ink)' : 'sk-meta'">
              {{ strip.pixels }} px<template v-if="strip.pixels === pixels"> · 추천</template>
            </span>
            <span class="sk-meta">
              {{ strip.nmPerPx.toFixed(3) }} nm/px · 경계에 {{ strip.pxOnEdge.toFixed(1) }} px
            </span>
          </div>
          <div class="relative mt-1 h-14 w-full overflow-hidden rounded-[var(--sk-r-nav)] bg-(--sk-field)">
            <div class="flex h-full">
              <!-- shrink-0 is load-bearing: flex children default to
                   flex-shrink:1, so a grid that overshoots the window would be
                   squeezed to fit — silently making cells narrower than the
                   pixel they stand for. Clipping is the honest overflow. -->
              <div
                v-for="(value, i) in strip.samples"
                :key="i"
                class="h-full shrink-0"
                :style="{
                  width: `${cellPct(strip.nmPerPx)}%`,
                  background: rampColor(value),
                  boxShadow: 'inset -1px 0 rgba(255,255,255,.16)'
                }"
              />
            </div>
            <!-- 경계 중심은 창의 정중앙이다. 밝은 rim만으로는 "어디가 경계인지"가
                 픽셀이 커질수록 흐려지므로 기준선을 따로 긋는다. -->
            <div class="absolute inset-y-0 left-1/2 w-px bg-(--sk-warn)" />
          </div>
        </div>

        <div class="mt-1 flex justify-between font-mono text-xs text-(--sk-ink-muted)">
          <span>← bar 안쪽</span>
          <span>space →</span>
        </div>
      </div>

      <dl class="w-36 font-mono text-xs leading-relaxed">
        <div class="flex justify-between">
          <dt class="sk-meta">
            px 크기
          </dt>
          <dd class="sk-value-num">
            {{ nmPerPx.toFixed(3) }} nm
          </dd>
        </div>
        <div class="flex justify-between">
          <dt class="sk-meta">
            CD당 px 수
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

      <!-- basis-full: 설명은 카드 아래 줄 전체를 쓴다. 좁은 칸에 두면 그 칸만
           세로로 길어져 옆 칸들 아래가 통째로 비므로, 문단은 행을 바꾼다. -->
      <p class="basis-full sk-meta leading-relaxed">
        <span class="italic">시뮬레이션 — 실제로 촬영된 이미지가 아니라, 설정값으로 예상한 이미지입니다.</span>
        <template v-if="strips.length">
          경계 확대의 두 줄은 <span class="font-semibold text-(--sk-ink)">같은 물리 구간</span>을 그린 것이고, 칸 하나가 픽셀 하나입니다.
          경계 번짐 폭 {{ SEM_EDGE_WIDTH_NM }} nm는 픽셀 설정과 무관하게 고정입니다 —
          픽셀이 작아질수록 그 고정된 경계 위에 샘플이 더 많이 얹혀
          ({{ strips[0]!.pxOnEdge.toFixed(1) }} px → {{ strips[1]?.pxOnEdge.toFixed(1) ?? '—' }} px)
          경계 위치를 더 정밀하게 잡습니다.
          <span class="text-(--sk-warn)">{{ SEM_EDGE_WIDTH_NM }} nm는 설명용 대표값이며, 표준안 확정 전까지는 잠정값입니다.</span>
        </template>
      </p>
    </div>
  </div>
</template>
