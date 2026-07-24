<script setup lang="ts">
import { fovNm, marginSensitivity, pixelGuidance, type CalcInput, type Recommendation } from '~/utils/magPixel'

const props = defineProps<{
  rec: Recommendation
  calc: CalcInput
}>()

const guidance = computed(() => pixelGuidance(props.rec, props.calc.minPxPerCd))
const sensitivity = computed(() => marginSensitivity(props.calc))
/** FOV는 fovNm()으로만 구한다 — 135000 상수를 컴포넌트에 복제하지 않는다. */
const recFovNm = computed(() => props.rec.mag === null ? null : fovNm(props.rec.mag))

const toneClass = computed(() => ({
  ok: 'bg-emerald-500/10 border-emerald-500',
  warn: 'bg-amber-500/10 border-amber-500',
  error: 'bg-red-500/10 border-red-500'
}[guidance.value.tone]))

const magLabel = (mag: number | null) => mag === null ? '—' : `${mag / 1000}K`
</script>

<template>
  <div class="flex flex-wrap gap-4">
    <div
      class="min-w-52 flex-1 rounded-(--sk-r-sidebar) border-2 p-4"
      :class="toneClass"
    >
      <div class="mb-2 font-mono text-[10px] tracking-wide">
        ★ 추천 조합
      </div>
      <div class="font-mono text-2xl font-bold">
        {{ magLabel(rec.mag) }}
      </div>
      <div class="mb-3 font-mono text-[15px] font-bold opacity-80">
        {{ rec.pixels ?? '—' }} px
      </div>
      <dl class="font-mono text-[11.5px] leading-relaxed">
        <div class="flex justify-between">
          <dt>FOV</dt>
          <dd>{{ recFovNm !== null ? Math.round(recFovNm).toLocaleString() : '—' }} nm</dd>
        </div>
        <div class="flex justify-between opacity-60">
          <dt>필요</dt>
          <dd>{{ Math.round(rec.requiredFovNm).toLocaleString() }} nm</dd>
        </div>
        <div class="flex justify-between">
          <dt>nm/px</dt>
          <dd>{{ rec.nmPerPx?.toFixed(3) ?? '—' }}</dd>
        </div>
        <div class="flex justify-between font-semibold">
          <dt>px/CD</dt>
          <dd>{{ rec.pxPerCd?.toFixed(1) ?? '—' }}</dd>
        </div>
        <div class="mt-1 flex justify-between border-t border-(--sk-border) pt-1.5 font-semibold">
          <dt>스캔 시간</dt>
          <dd>×{{ rec.scanFactor ?? '—' }}</dd>
        </div>
      </dl>
      <div
        class="mt-3 rounded p-2 text-[11px] leading-relaxed"
        :class="toneClass"
      >
        <strong>{{ guidance.headline }}</strong><br>
        {{ guidance.detail }}
      </div>
    </div>

    <div class="min-w-52 flex-1 rounded-(--sk-r-sidebar) border border-(--sk-border) p-4">
      <div class="mb-2 font-mono text-[10px] tracking-wide text-(--sk-ink-muted)">
        마진 민감도
      </div>
      <p class="mb-2 text-[11px] leading-relaxed text-(--sk-ink-muted)">
        배율이 이산값이라 마진이 연속적으로 반응하지 않습니다. 지금 마진에 여유가 얼마나 남았는지 보세요.
      </p>
      <table class="w-full font-mono text-[11.5px]">
        <tbody>
          <tr
            v-for="row in sensitivity"
            :key="row.marginRatio"
            :class="row.marginRatio === calc.marginRatio ? 'font-bold text-emerald-600 dark:text-emerald-400' : 'text-(--sk-ink-muted)'"
          >
            <td class="py-0.5">
              {{ Math.round(row.marginRatio * 100) }}%
            </td>
            <td class="py-0.5 text-right">
              {{ row.requiredFovNm ? Math.round(row.requiredFovNm).toLocaleString() : '—' }} nm
            </td>
            <td class="py-0.5 text-right">
              {{ magLabel(row.mag) }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
