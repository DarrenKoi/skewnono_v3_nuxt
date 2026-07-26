<script setup lang="ts">
import { cellVerdict, scanTimeFactor, type MagPixelRow } from '~/utils/magPixel'

const props = defineProps<{
  rows: MagPixelRow[]
  /** 2048·4096까지 보여줄지. 실사용은 512·1024가 대부분이다. */
  showWide: boolean
  /** null이면 판정 없이 순수 참조표로 렌더한다. */
  requiredFovNm: number | null
  cdNm: number
  minPxPerCd: number
  recommendedMag: number | null
  recommendedPixels: number | null
}>()

const visiblePixels = computed(() => props.showWide ? [512, 1024, 2048, 4096] : [512, 1024])

/** CD가 들어와야 px/CD 열을 붙인다 — CD 없이는 판정할 값이 없다. */
const hasVerdict = computed(() => props.requiredFovNm !== null)

const scanFactorLabel = (pixels: number) => {
  const factor = scanTimeFactor(pixels)
  return factor === null ? '' : `×${factor}`
}

/**
 * nm/px는 배율에 따라 263 nm(1K×)부터 0.03 nm(1M×, 4096 px)까지 4자리 넘게
 * 움직인다. 고정 소수점은 큰 값에서 과잉 정밀(263.672)이고 작은 값에서 정보를
 * 잃으므로(0.033), 유효숫자 4자리 정도로 자리수를 맞춘다 — 열 폭도 같이 줄어든다.
 */
const fmtNmPerPx = (nm: number) =>
  nm >= 100 ? nm.toFixed(1) : nm >= 10 ? nm.toFixed(2) : nm.toFixed(3)

/**
 * FOV 미수용은 **배율(행)의 성질**이다 — 픽셀 수를 바꿔도 패턴은 화면에 들어오지
 * 않는다. 그래서 픽셀 열마다 '✗ FOV'를 반복하지 않고 FOV 열에서 한 번 판정하고
 * 행 전체를 흐린다. 픽셀 열의 nm/px는 그래도 물리적으로 유효한 값이라 남긴다.
 */
const fovFits = (row: MagPixelRow) =>
  props.requiredFovNm === null || row.fovNm >= props.requiredFovNm

const verdictOf = (mag: number, pixels: number) =>
  props.requiredFovNm === null
    ? null
    : cellVerdict(mag, pixels, props.cdNm, props.requiredFovNm, props.minPxPerCd)

const isRecommended = (mag: number, pixels: number) =>
  props.recommendedMag === mag && props.recommendedPixels === pixels

const cellOf = (row: MagPixelRow, pixels: number) => row.cells.find(c => c.pixels === pixels)

const nmPerPxText = (row: MagPixelRow, pixels: number) => {
  const cell = cellOf(row, pixels)
  return cell ? fmtNmPerPx(cell.nmPerPx) : '—'
}

/** CD 한 개 폭에 얹히는 픽셀 개수 = CD ÷ (1 px가 덮는 길이). */
const pxPerCdText = (row: MagPixelRow, pixels: number) => {
  const cell = cellOf(row, pixels)
  return cell ? (props.cdNm / cell.nmPerPx).toFixed(1) : '—'
}

const pxPerCdMark = (row: MagPixelRow, pixels: number) => {
  if (!fovFits(row)) return ''
  if (isRecommended(row.mag, pixels)) return '★'
  return verdictOf(row.mag, pixels) === 'under-pixel' ? '✗' : '●'
}

const pxPerCdClass = (row: MagPixelRow, pixels: number) => {
  if (!fovFits(row)) return 'text-(--sk-ink-muted) opacity-50'
  if (verdictOf(row.mag, pixels) === 'under-pixel') return 'text-(--sk-bad)'
  return isRecommended(row.mag, pixels)
    ? 'text-(--sk-ok) font-bold'
    : 'text-(--sk-ok)'
}

const magLabel = (mag: number) => mag >= 1000 ? `${mag / 1000}K` : String(mag)
</script>

<template>
  <div class="overflow-x-auto">
    <!-- w-max: 참조표는 밀도가 가독성이다. w-full은 남는 폭을 컬럼에 분배해
         값 사이를 벌리므로, 내용만큼만 넓히고 좁은 화면에서만 스크롤한다. -->
    <table class="w-max border-collapse font-mono text-[12px]">
      <thead>
        <tr class="sk-eyebrow">
          <th
            rowspan="2"
            class="border-b border-(--sk-border) px-2 py-1.5 text-left align-bottom"
          >
            MAG
          </th>
          <th
            rowspan="2"
            class="border-b border-(--sk-border) px-2 py-1.5 text-right align-bottom"
          >
            FOV<span class="opacity-60">(nm)</span>
          </th>
          <th
            v-for="p in visiblePixels"
            :key="p"
            :colspan="hasVerdict ? 2 : 1"
            class="border-l border-(--sk-border) px-2 pb-1 pt-1.5 text-center"
          >
            {{ p }} px <span class="opacity-60">· 스캔 {{ scanFactorLabel(p) }}</span>
          </th>
        </tr>
        <tr class="sk-eyebrow">
          <template
            v-for="p in visiblePixels"
            :key="p"
          >
            <th
              class="whitespace-nowrap border-b border-l border-(--sk-border) px-2 pb-1.5 text-right font-normal normal-case tracking-normal"
            >
              px 크기(nm)
            </th>
            <th
              v-if="hasVerdict"
              class="whitespace-nowrap border-b border-(--sk-border) px-2 pb-1.5 text-right font-normal normal-case tracking-normal"
            >
              CD당 px 수
            </th>
          </template>
        </tr>
      </thead>
      <tbody>
        <tr
          v-for="row in rows"
          :key="row.mag"
          :class="recommendedMag === row.mag ? 'bg-(--sk-ok-soft)' : undefined"
        >
          <td class="whitespace-nowrap px-2 py-1">
            {{ magLabel(row.mag) }}
            <span
              v-if="row.assumed"
              class="ml-1 rounded-[var(--sk-r-chip)] bg-(--sk-warn-soft) px-1 text-[10px] font-semibold text-(--sk-warn)"
            >가정</span>
          </td>
          <td
            class="whitespace-nowrap px-2 py-1 text-right"
            :class="fovFits(row) ? 'text-(--sk-ink)' : 'text-(--sk-bad)'"
          >
            {{ Math.round(row.fovNm).toLocaleString() }}
            <span
              v-if="!fovFits(row)"
              title="패턴이 화면에 들어오지 않습니다"
            >✗</span>
          </td>
          <template
            v-for="p in visiblePixels"
            :key="p"
          >
            <td
              class="border-l border-(--sk-border) px-2 py-1 text-right"
              :class="fovFits(row) ? 'text-(--sk-ink)' : 'text-(--sk-ink-muted) opacity-50'"
            >
              {{ nmPerPxText(row, p) }}
            </td>
            <td
              v-if="hasVerdict"
              class="px-2 py-1 text-right"
              :class="pxPerCdClass(row, p)"
            >
              <span class="mr-0.5 inline-block w-[1em] text-center">{{ pxPerCdMark(row, p) }}</span>{{ pxPerCdText(row, p) }}
            </td>
          </template>
        </tr>
      </tbody>
    </table>

    <p class="mt-3 max-w-2xl font-mono sk-meta leading-relaxed">
      <span class="text-(--sk-ink)">px 크기(nm)</span> = 1 px가 덮는 실제 길이 (FOV ÷ 픽셀 수) ·
      헤더 스캔 ×N = 512 px 대비 상대 스캔 시간 (픽셀 총량 X×Y에 비례)
      <template v-if="hasVerdict">
        <br>
        <span class="text-(--sk-ink)">CD당 px 수</span> = CD 한 개 폭에 얹히는 픽셀 개수 (CD ÷ px 크기) ·
        ● 기준 {{ minPxPerCd }} px 통과 · ✗ 픽셀 부족 · ★ 추천
        <br>
        FOV에 ✗ 표시된 행은 패턴이 화면에 들어오지 않아 배율 자체가 성립하지 않습니다 (픽셀 수를 바꿔도 해결되지 않습니다).
      </template>
    </p>
  </div>
</template>
