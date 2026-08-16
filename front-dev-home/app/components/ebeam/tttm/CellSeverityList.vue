<template>
  <div class="dashboard-surface rounded-[var(--sk-r-card)] px-5 py-4">
    <div class="flex items-baseline justify-between gap-2">
      <p class="sk-title">
        셀별 최악 장비쌍
      </p>
      <span class="sk-meta">CD 대비 지수 순</span>
    </div>

    <div class="mt-4 flex flex-col gap-3">
      <div
        v-for="row in cells"
        :key="row.cell.cell_id"
        class="flex items-center gap-2.5"
      >
        <span class="w-[130px] shrink-0 text-[13px] text-(--sk-ink)">
          {{ cellLabel(row.cell) }} ·
          <template v-if="row.cd.assumed">CD 가정</template>
          <template v-else>{{ row.cd.nm.toFixed(1) }} nm</template>
        </span>

        <!-- The track spans 3x this cell's own tolerance, so the mark lands at
             the same place on every row and a longer bar always means "further
             past its own limit" — see barFraction in utils/tttmCells. -->
        <div class="relative h-2.5 flex-1 rounded-[var(--sk-r-sidebar)] bg-(--sk-muted-surface)">
          <div
            v-if="row.worstPair"
            class="absolute inset-y-0 left-0 rounded-[var(--sk-r-sidebar)]"
            :style="{
              width: `${barFraction(row.worstPair.skewNm, row.thresholdNm) * 100}%`,
              background: row.worstExceeds ? 'var(--sk-bad)' : 'var(--sk-ok)'
            }"
          />
          <div
            class="absolute -top-1 -bottom-1 w-0.5 bg-(--sk-brand)"
            :style="{ left: `${TOLERANCE_MARK * 100}%` }"
          />
        </div>

        <span
          class="w-[104px] shrink-0 text-right font-mono text-xs tabular-nums"
          :class="row.worstExceeds ? 'text-(--sk-bad)' : 'text-(--sk-ink)'"
          :title="row.worstPair
            ? `${labelFor(row.worstPair.a)} · ${labelFor(row.worstPair.b)}`
            : '측정된 장비쌍 없음'"
        >
          <template v-if="row.worstPair">
            {{ row.worstPair.skewNm.toFixed(3) }} / {{ row.thresholdNm.toFixed(3) }}
          </template>
          <template v-else>— / {{ row.thresholdNm.toFixed(3) }}</template>
        </span>
      </div>
    </div>

    <p class="mt-3.5 sk-field-label leading-relaxed">
      막대 = 그 셀의 최악 장비쌍, 세로선 = tolerance.
      <template v-if="overCount">
        {{ verdict }}
      </template>
      <EbeamTttmCaptionMore>
        지수는 최악 장비쌍 스큐를 그 셀 CD의 {{ percent }}%로 나눈 값이라 패턴 크기가
        다른 셀끼리 비교할 수 있습니다. 순위를 매길 뿐 판정하지 않습니다 — 합격선은
        tolerance 입니다. (CD의 {{ percent }}% 규칙은 장비 1대를 consensus 와 비교하는
        공장 기준이고, 장비쌍에 적용하는 것은 아직 확인되지 않은 확장입니다.)
      </EbeamTttmCaptionMore>
    </p>
  </div>
</template>

<script setup lang="ts">
import { barFraction, cellLabel, TOLERANCE_MARK, type RankedCell } from '~/utils/tttmCells'
import { ACTION_LIMIT_PERCENT } from '~/utils/tttmLimits'
import { toolLabels } from '~/utils/toolLabels'
import type { ToolRef } from '~/composables/useTttmApi'

const props = defineProps<{ cells: RankedCell[], tools: ToolRef[] }>()

const percent = ACTION_LIMIT_PERCENT

const labels = computed(() => toolLabels(props.tools))
const labelFor = (eqp: string) => labels.value.labelFor(eqp)

const over = computed(() => props.cells.filter(c => c.worstExceeds))
const overCount = computed(() => over.value.length)

// Name the tool only when it is in EVERY failing cell's worst pair. Otherwise
// the sentence would blame one tool for cells it had nothing to do with, which
// is worse than saying nothing — this line is the one a reader acts on.
const culprit = computed(() => {
  if (over.value.length < 2) return null
  const first = over.value[0]!.worstPair!
  for (const eqp of [first.a, first.b]) {
    if (over.value.every(c => c.worstPair!.a === eqp || c.worstPair!.b === eqp)) return eqp
  }
  return null
})

const verdict = computed(() =>
  culprit.value
    ? `${overCount.value}개 셀이 tolerance를 넘고, 모두 ${labelFor(culprit.value)} 가 낀 장비쌍입니다.`
    : `${overCount.value}개 셀이 tolerance를 넘습니다.`
)
</script>
