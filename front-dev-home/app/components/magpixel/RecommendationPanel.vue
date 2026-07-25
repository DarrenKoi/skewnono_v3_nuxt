<script setup lang="ts">
import { fovNm, isAssumedMag, marginSensitivity, pixelGuidance, type CalcInput, type Recommendation } from '~/utils/magPixel'

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

/** 원본 문서에서 확인되지 않아 가정한 GT 600K+ 구간인지. ResultTable.vue의 `가정`
 *  배지와 같은 판정을 헤드라인·민감도 표에도 적용해, 표와 추천 카드가 서로
 *  다른 신뢰도를 말하지 않게 한다. */
const isMagAssumed = (mag: number | null) => mag !== null && isAssumedMag(props.calc.series, mag)
</script>

<template>
  <div class="flex flex-wrap gap-4">
    <div
      class="min-w-52 flex-1 rounded-lg border-2 p-4"
      :class="toneClass"
    >
      <div class="sk-eyebrow mb-2">
        ★ 추천 조합
      </div>
      <div class="font-mono text-2xl font-bold">
        {{ magLabel(rec.mag) }}
        <span
          v-if="isMagAssumed(rec.mag)"
          class="ml-1 rounded px-1 align-middle text-[9px] text-amber-600 ring-1 ring-amber-500/40 dark:text-amber-400"
        >가정</span>
      </div>
      <div class="mb-3 font-mono text-[15px] font-bold opacity-80">
        {{ rec.pixels ?? '—' }} px
      </div>
      <dl class="font-mono text-[11.5px] leading-relaxed">
        <div class="flex justify-between">
          <dt class="sk-meta">
            FOV
          </dt>
          <dd class="sk-value-num">
            {{ recFovNm !== null ? Math.round(recFovNm).toLocaleString() : '—' }} nm
          </dd>
        </div>
        <div class="flex justify-between opacity-60">
          <dt class="sk-meta">
            필요
          </dt>
          <dd class="sk-value-num">
            {{ Math.round(rec.requiredFovNm).toLocaleString() }} nm
          </dd>
        </div>
        <div class="flex justify-between">
          <dt class="sk-meta">
            nm/px
          </dt>
          <dd class="sk-value-num">
            {{ rec.nmPerPx?.toFixed(3) ?? '—' }}
          </dd>
        </div>
        <div class="flex justify-between">
          <dt class="sk-meta font-semibold">
            px/CD
          </dt>
          <dd class="sk-value-num font-semibold">
            {{ rec.pxPerCd?.toFixed(1) ?? '—' }}
          </dd>
        </div>
        <div class="mt-1 flex justify-between border-t border-(--sk-border) pt-1.5">
          <dt class="sk-meta font-semibold">
            스캔 시간
          </dt>
          <dd class="sk-value-num font-semibold">
            ×{{ rec.scanFactor ?? '—' }}
          </dd>
        </div>
      </dl>
      <div
        class="mt-3 rounded-lg p-2 text-[11px] leading-relaxed"
        :class="toneClass"
      >
        <strong>{{ guidance.headline }}</strong><br>
        {{ guidance.detail }}
      </div>
    </div>

    <div class="min-w-52 flex-1 rounded-lg border border-(--sk-border) p-4">
      <div class="sk-eyebrow mb-2">
        마진 민감도
      </div>
      <p class="mb-2 sk-meta leading-relaxed">
        배율이 정해진 단계로만 바뀌어서 마진이 연속적으로 반응하지 않습니다. 지금 여유 마진이 얼마나 남았는지 보세요.
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
              <span
                v-if="isMagAssumed(row.mag)"
                class="ml-1 rounded px-1 text-[9px] text-amber-600 ring-1 ring-amber-500/40 dark:text-amber-400"
              >가정</span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
