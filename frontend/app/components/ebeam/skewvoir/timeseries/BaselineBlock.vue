<template>
  <!-- S7 기준 대비. Neutral on purpose: this states how far the target group
       moved against the hand-picked baseline and how many points say so. It
       carries no verdict colour because nothing here is a judgement. -->
  <EbeamSkewvoirPanelFrame
    title="기준 대비"
    :meta="`${analysis.activeParamLabel.value} · 이 세트 안에서 손으로 나눈 기준이며 공식 기준선이 아닙니다`"
    icon="i-lucide-git-compare"
    title-size="md"
    body-class="flex flex-col gap-2"
  >
    <AppLoadingState
      v-if="analysis.setPending.value"
      variant="inline"
      class="h-24"
      title="세트를 불러오는 중입니다."
    />
    <template v-else>
      <p
        class="text-base leading-snug font-semibold"
        :class="result.comparison ? 'text-(--sk-ink)' : 'text-(--sk-ink-subtle)'"
      >
        {{ sentence }}
      </p>

      <table class="w-full max-w-3xl border-collapse text-xs">
        <thead>
          <tr class="border-b border-(--sk-border) sk-label">
            <th
              v-for="(h, i) in HEADERS"
              :key="h"
              scope="col"
              class="px-1.5 py-1.5 font-semibold"
              :class="i === 0 ? 'text-left' : 'text-right'"
            >
              {{ h }}<template v-if="i > 2 && unit">
                ({{ unit }})
              </template>
            </th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="row in rows"
            :key="row.label"
            class="border-b border-(--sk-border-soft) last:border-0"
          >
            <th
              scope="row"
              class="px-1.5 py-1.5 text-left font-semibold text-(--sk-ink)"
            >
              {{ row.label }}
            </th>
            <td
              v-for="(cell, i) in row.cells"
              :key="i"
              class="px-1.5 py-1.5 text-right font-mono tabular-nums text-(--sk-ink)"
            >
              {{ cell }}
            </td>
          </tr>
        </tbody>
      </table>

      <p
        v-for="note in notes"
        :key="note"
        class="sk-meta"
      >
        {{ note }}
      </p>
    </template>
  </EbeamSkewvoirPanelFrame>
</template>

<script setup lang="ts">
import type { SkewvoirAnalysis } from '~/composables/useSkewvoirAnalysis'
import { baselineComparison, baselineSentence, type BaselineSide } from '~/utils/skewvoirAnalysis/baselineCompare'

// Draws only: baselineCompare.ts owns the split, the pooling and the sentence.
const props = defineProps<{ analysis: SkewvoirAnalysis }>()

const HEADERS = ['', '측정', 'site', 'mean', 'median', '3σ', 'range']

const unit = computed(() => props.analysis.activeUnit.value)

const result = computed(() => {
  const { base, target } = props.analysis.baselineGroups.value
  return baselineComparison(props.analysis.setFiles.value, base, target, props.analysis.activeParam.value, unit.value)
})

const sentence = computed(() => baselineSentence(result.value))

const signed = (v: number, digits: number) => `${v >= 0 ? '+' : ''}${formatFixed(v, digits)}`

const sideCells = (s: BaselineSide) => [
  `${s.msrs.length}`,
  `${s.pooled.n}`,
  formatFixed(s.pooled.level?.mean, 3),
  formatFixed(s.pooled.level?.median, 3),
  formatFixed(s.pooled.spread?.threeSigma, 3),
  formatFixed(s.pooled.spread?.range, 3)
]

const rows = computed(() => {
  const r = result.value
  const c = r.comparison
  return [
    { label: '기준', cells: sideCells(r.base) },
    { label: '대상', cells: sideCells(r.target) },
    ...(c
      ? [{
          label: '대상 − 기준',
          cells: ['', '', signed(c.shift, 3), '', c.threeSigmaRatio == null ? '—' : `×${formatFixed(c.threeSigmaRatio, 2)}`, signed(c.rangeDelta, 3)]
        }]
      : [])
  ]
})

// What qualifies the numbers above: who was left out, and whether one
// measurement is doing the talking for its side.
const notes = computed(() => {
  const r = result.value
  const out: string[] = []
  const sides: [string, BaselineSide][] = [['기준', r.base], ['대상', r.target]]
  for (const [label, s] of sides) {
    if (s.dominated) out.push(`${label} site 의 ${Math.round(s.dominance * 100)}% 가 한 측정에서 나왔습니다. site 를 같은 가중치로 합쳤으므로 그 측정이 ${label} 값을 좌우합니다.`)
    if (s.msrs.length < s.requested) out.push(`${label} ${s.requested}건 중 ${s.requested - s.msrs.length}건은 이 파라미터의 측정값이 없어 빠졌습니다.`)
  }
  const excluded = props.analysis.manifest.value.counts.excluded
  if (excluded > 0) out.push(`호환되지 않아 제외된 측정 ${excluded}건은 어느 쪽에도 들어가지 않았습니다.`)
  return out
})
</script>
