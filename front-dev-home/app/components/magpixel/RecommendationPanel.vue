<script setup lang="ts">
import {
  fovNm, marginSensitivity, pixelGuidance, magLabel, actualMarginNm,
  type CalcInput, type Recommendation
} from '~/utils/magPixel'

const props = defineProps<{
  rec: Recommendation
  calc: CalcInput
}>()

const guidance = computed(() => pixelGuidance(props.rec, props.calc.minPxPerCd))
const sensitivity = computed(() => marginSensitivity(props.calc))
/** FOV는 fovNm()으로만 구한다 — 135000 상수를 컴포넌트에 복제하지 않는다. */
const recFovNm = computed(() => props.rec.mag === null ? null : fovNm(props.rec.mag))

/** 판정 색은 세 계열(--sk-ok/warn/bad)에서만 나온다 — emerald/amber/red 원색은
 *  따뜻한 캔버스에서 튀고 다크 모드에서 대비가 무너진다 (DESIGN.md §Semantic). */
const TONE = {
  ok: { soft: 'bg-(--sk-ok-soft)', text: 'text-(--sk-ok)', border: 'border-(--sk-ok-border)' },
  warn: { soft: 'bg-(--sk-warn-soft)', text: 'text-(--sk-warn)', border: 'border-(--sk-warn-border)' },
  error: { soft: 'bg-(--sk-bad-soft)', text: 'text-(--sk-bad)', border: 'border-(--sk-bad-border)' }
} as const

const tone = computed(() => TONE[guidance.value.tone])

const verdictLabel = computed(() => ({
  ok: '기준 통과 · 최소 스캔',
  warn: '기준 통과 · 스캔 증가',
  error: '성립하지 않음'
}[guidance.value.tone]))

/** 실제 마진은 요청 비율이 아니라 실제 span에서 역산한다 — 근거는
 *  actualMarginNm()에 있고, 모식도·시뮬레이션도 같은 함수를 쓴다. */
const marginNm = computed(() =>
  recFovNm.value === null
    ? null
    : actualMarginNm(recFovNm.value, props.calc.patternCount * props.rec.effectivePitchNm)
)

const marginPctLabel = computed(() =>
  recFovNm.value && marginNm.value !== null
    ? `${Math.round((marginNm.value / recFovNm.value) * 100)}%`
    : '—'
)
</script>

<template>
  <div class="flex flex-col gap-4">
    <!-- 답 카드 — 배율 × 픽셀이 이 페이지의 결론이라 가장 큰 활자를 가져간다. -->
    <section class="dashboard-surface overflow-hidden rounded-[var(--sk-r-card)]">
      <div
        class="flex items-center gap-2 px-4 py-2.5"
        :class="tone.soft"
      >
        <span
          class="sk-eyebrow"
          :class="tone.text"
        >★ 추천 조합</span>
        <span
          class="ml-auto sk-label"
          :class="tone.text"
        >{{ verdictLabel }}</span>
      </div>

      <div class="p-4">
        <div class="flex flex-wrap items-baseline gap-x-2.5 gap-y-1">
          <span class="font-mono text-[38px] font-bold leading-none tracking-tight tabular-nums text-(--sk-ink)">
            {{ magLabel(rec.mag) }}
          </span>
          <span class="font-mono text-base font-semibold text-(--sk-ink-muted)">×</span>
          <span class="font-mono text-[26px] font-bold leading-none tracking-tight tabular-nums text-(--sk-ink)">
            {{ rec.pixels ?? '—' }} px
          </span>
        </div>

        <dl class="mt-3.5 grid grid-cols-2 gap-x-4 gap-y-2">
          <div class="flex justify-between border-b border-(--sk-border-soft) pb-1.5">
            <dt class="sk-meta">
              FOV
            </dt>
            <dd class="sk-value-num">
              {{ recFovNm !== null ? Math.round(recFovNm).toLocaleString() : '—' }} nm
            </dd>
          </div>
          <div class="flex justify-between border-b border-(--sk-border-soft) pb-1.5">
            <dt class="sk-meta">
              필요 FOV
            </dt>
            <dd class="sk-value-num">
              {{ Math.round(rec.requiredFovNm).toLocaleString() }} nm
            </dd>
          </div>
          <div class="flex justify-between border-b border-(--sk-border-soft) pb-1.5">
            <dt class="sk-meta">
              px 크기
            </dt>
            <dd class="sk-value-num">
              {{ rec.nmPerPx?.toFixed(3) ?? '—' }} nm
            </dd>
          </div>
          <div class="flex justify-between border-b border-(--sk-border-soft) pb-1.5">
            <dt class="sk-meta font-semibold">
              CD당 px
            </dt>
            <dd class="sk-value-num font-semibold">
              {{ rec.pxPerCd?.toFixed(1) ?? '—' }}
            </dd>
          </div>
          <div class="flex justify-between">
            <dt class="sk-meta font-semibold">
              스캔 시간
            </dt>
            <dd class="sk-value-num font-semibold">
              ×{{ rec.scanFactor ?? '—' }}
            </dd>
          </div>
          <div class="flex justify-between">
            <dt class="sk-meta">
              여유 마진
            </dt>
            <dd class="sk-value-num">
              {{ marginNm !== null ? Math.round(marginNm) : '—' }} nm · {{ marginPctLabel }}
            </dd>
          </div>
        </dl>

        <div
          class="mt-3.5 rounded-[var(--sk-r-nav)] border p-3"
          :class="[tone.border, tone.soft]"
        >
          <p class="text-[13px] font-semibold leading-snug text-(--sk-ink)">
            {{ guidance.headline }}
          </p>
          <p class="mt-1 sk-meta leading-relaxed">
            {{ guidance.detail }}
          </p>
        </div>
      </div>
    </section>

    <!-- 마진 민감도 — 배율이 이산값이라 마진이 연속으로 반응하지 않는다. -->
    <section class="dashboard-surface rounded-[var(--sk-r-card)] p-4">
      <div class="mb-2 flex items-baseline justify-between gap-2">
        <span class="sk-eyebrow">마진 민감도</span>
        <span class="sk-meta">배율은 계단으로 움직입니다</span>
      </div>
      <table class="w-full border-collapse">
        <thead>
          <tr>
            <th class="pb-1 text-left sk-label">
              마진
            </th>
            <th class="pb-1 text-right sk-label">
              필요 FOV
            </th>
            <th class="pb-1 text-right sk-label">
              추천 MAG
            </th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="row in sensitivity"
            :key="row.marginRatio"
            :class="row.marginRatio === calc.marginRatio ? 'bg-(--sk-brand-soft)' : undefined"
          >
            <td class="border-t border-(--sk-border-soft) py-1 pr-1.5 sk-value-num">
              {{ Math.round(row.marginRatio * 100) }}%
            </td>
            <td class="border-t border-(--sk-border-soft) px-1.5 py-1 text-right sk-value-num">
              {{ row.requiredFovNm ? Math.round(row.requiredFovNm).toLocaleString() : '—' }} nm
            </td>
            <td class="border-t border-(--sk-border-soft) py-1 pl-1.5 text-right sk-value-num">
              {{ magLabel(row.mag) }}
            </td>
          </tr>
        </tbody>
      </table>
    </section>
  </div>
</template>
