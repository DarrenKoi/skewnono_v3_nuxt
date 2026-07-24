<script setup lang="ts">
import { cellVerdict, type MagPixelRow } from '~/utils/magPixel'

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

const scanFactorLabel = (pixels: number) => `×${(pixels / 512) ** 2}`

const verdictOf = (mag: number, pixels: number) =>
  props.requiredFovNm === null
    ? null
    : cellVerdict(mag, pixels, props.cdNm, props.requiredFovNm, props.minPxPerCd)

const isRecommended = (mag: number, pixels: number) =>
  props.recommendedMag === mag && props.recommendedPixels === pixels

const cellClass = (mag: number, pixels: number) => {
  const v = verdictOf(mag, pixels)
  if (v === null) return 'text-(--sk-ink)'
  if (v === 'over-fov' || v === 'under-pixel') return 'text-red-600 dark:text-red-400'
  return isRecommended(mag, pixels)
    ? 'text-emerald-600 dark:text-emerald-400 font-bold'
    : 'text-emerald-600 dark:text-emerald-400'
}

/** 참조 모드는 nm/px, 판정 모드는 px/CD를 보여준다. */
const cellText = (row: MagPixelRow, pixels: number) => {
  const cell = row.cells.find(c => c.pixels === pixels)
  if (!cell) return '—'
  if (props.requiredFovNm === null) return cell.nmPerPx.toFixed(3)
  const v = verdictOf(row.mag, pixels)
  if (v === 'over-fov') return '✗ FOV'
  const ratio = props.cdNm / cell.nmPerPx
  return `${v === 'under-pixel' ? '✗' : isRecommended(row.mag, pixels) ? '★' : '●'} ${ratio.toFixed(1)}`
}

const magLabel = (mag: number) => mag >= 1000 ? `${mag / 1000}K` : String(mag)
</script>

<template>
  <div class="overflow-x-auto">
    <table class="w-full border-collapse font-mono text-[12px]">
      <thead>
        <tr class="text-[10px] tracking-wide text-(--sk-ink-muted)">
          <th class="border-b border-(--sk-border) px-2 py-1.5 text-left">
            MAG
          </th>
          <th class="border-b border-(--sk-border) px-2 py-1.5 text-right">
            FOV(nm)
          </th>
          <th
            v-for="p in visiblePixels"
            :key="p"
            class="border-b border-(--sk-border) px-2 py-1.5 text-center"
          >
            {{ p }} <span class="opacity-60">{{ scanFactorLabel(p) }}</span>
          </th>
        </tr>
      </thead>
      <tbody>
        <tr
          v-for="row in rows"
          :key="row.mag"
          :class="recommendedMag === row.mag ? 'bg-emerald-500/10' : undefined"
        >
          <td class="px-2 py-1">
            {{ magLabel(row.mag) }}
            <span
              v-if="row.assumed"
              class="ml-1 rounded px-1 text-[9px] text-amber-600 ring-1 ring-amber-500/40 dark:text-amber-400"
            >가정</span>
          </td>
          <td class="px-2 py-1 text-right">
            {{ Math.round(row.fovNm).toLocaleString() }}
          </td>
          <td
            v-for="p in visiblePixels"
            :key="p"
            class="px-2 py-1 text-center"
            :class="cellClass(row.mag, p)"
          >
            {{ cellText(row, p) }}
          </td>
        </tr>
      </tbody>
    </table>

    <p class="mt-3 font-mono text-[10.5px] leading-relaxed text-(--sk-ink-muted)">
      <template v-if="requiredFovNm === null">
        셀 값 = 픽셀당 길이(nm/px) · 헤더 ×N = 512 대비 상대 스캔 시간
      </template>
      <template v-else>
        셀 값 = px/CD · ● 기준 통과 · ✗ 픽셀 부족 · ✗ FOV 패턴 미수용 · ★ 추천<br>
        헤더 ×N = 512 대비 상대 스캔 시간 (픽셀 총량 X×Y 비례)
      </template>
    </p>
  </div>
</template>
