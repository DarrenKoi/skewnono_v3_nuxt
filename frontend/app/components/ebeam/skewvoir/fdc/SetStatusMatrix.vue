<template>
  <div class="space-y-2">
    <!-- Legend. The matrix encodes status as a fill, so the fills have to be
         named somewhere — including the absent one, which is otherwise
         indistinguishable from a rendering fault. -->
    <div class="flex flex-wrap items-center gap-x-3 gap-y-1.5 sk-label">
      <span
        v-for="key in LEGEND"
        :key="key"
        class="inline-flex items-center gap-1.5"
      >
        <span
          class="inline-block h-2.5 w-2.5 rounded-[3px] border border-(--sk-border)"
          :class="LEGEND_FILL[key]"
        />
        {{ LEGEND_LABEL[key] }}
      </span>
    </div>

    <div class="overflow-x-auto">
      <table class="w-full border-collapse">
        <caption class="sr-only">
          측정(run)별 FDC 채널 비교. 셀 값은 채널 원시 평균과 같은 채널의 선택 세트 대비 편차이며, 셀 색은 상대 상태입니다.
        </caption>

        <thead>
          <tr class="border-b border-(--sk-border)">
            <th
              scope="col"
              class="sticky left-0 z-10 bg-(--sk-surface) px-2 py-1.5 text-left sk-label"
            >
              채널
            </th>
            <th
              v-for="run in matrix.runs"
              :key="run.msr"
              scope="col"
              class="min-w-28 px-2 py-1.5 text-left align-bottom"
            >
              <span class="block truncate sk-label">{{ run.label }}</span>
              <!-- These counts are DATA VALUES, so they sit at the 12px floor
                   (DESIGN.md, the sub-12px rule). 10px is the eyebrow tier and
                   is for chrome that names things, never for a number the user
                   came to read. The "이상 없음" placeholder rides the same size
                   so the three states read as one row. -->
              <span class="mt-0.5 flex flex-wrap items-center gap-1">
                <span
                  v-if="run.bad"
                  class="rounded-(--sk-r-chip) bg-(--sk-bad-soft) px-1.5 font-mono text-xs tabular-nums text-(--sk-bad)"
                >이상 {{ run.bad }}</span>
                <span
                  v-if="run.warning"
                  class="rounded-(--sk-r-chip) bg-(--sk-warn-soft) px-1.5 font-mono text-xs tabular-nums text-(--sk-warn)"
                >주의 {{ run.warning }}</span>
                <span
                  v-if="run.insufficient"
                  class="rounded-(--sk-r-chip) bg-(--sk-muted-surface) px-1.5 font-mono text-xs tabular-nums text-(--sk-ink)"
                >평가 불가 {{ run.insufficient }}</span>
                <span
                  v-if="!run.bad && !run.warning && !run.insufficient && run.ok"
                  class="font-mono text-xs text-(--sk-ink-subtle)"
                >정상</span>
                <span
                  v-else-if="!run.bad && !run.warning && !run.insufficient"
                  class="font-mono text-xs text-(--sk-ink-subtle)"
                >평가 없음</span>
              </span>
            </th>
          </tr>
        </thead>

        <tbody
          v-for="group in matrix.groups"
          :key="group.category"
        >
          <tr class="bg-(--sk-muted-surface)">
            <th
              scope="colgroup"
              :colspan="matrix.runs.length + 1"
              class="sticky left-0 px-2 py-1 text-left sk-label"
            >
              {{ group.label }}
              <span class="ml-1 font-normal text-(--sk-ink-subtle)">{{ group.channels.length }}</span>
            </th>
          </tr>
          <tr
            v-for="ch in group.channels"
            :key="ch.name"
            class="border-b border-(--sk-border-soft) last:border-0"
          >
            <th
              scope="row"
              class="sticky left-0 z-10 max-w-44 truncate bg-(--sk-surface) px-2 py-1 text-left font-normal sk-value"
            >
              {{ ch.name }}
              <span
                v-if="ch.unit"
                class="text-(--sk-ink-subtle)"
              >({{ ch.unit }})</span>
            </th>
            <td
              v-for="(cell, i) in ch.cells"
              :key="matrix.runs[i]?.msr ?? i"
              class="px-2 py-1 text-right sk-value-num"
              :class="cell.present ? TONE[cell.status] : 'text-(--sk-ink-subtle)'"
              :title="cell.present ? cell.reason : '이 측정에 없는 채널'"
            >
              <template v-if="cell.present">
                <span class="block">{{ formatRawValue(cell.rawValue) }}</span>
                <span
                  v-if="cell.peerSigma != null"
                  class="block text-xs font-normal"
                >{{ formatSigned(cell.peerSigma) }}σ</span>
                <span
                  v-else-if="cell.status === 'insufficient'"
                  class="block text-xs font-normal text-(--sk-ink-subtle)"
                >미평가</span>
                <span class="sr-only">{{ STATUS_LABEL[cell.status] }}</span>
              </template>
              <template v-else>
                –<span class="sr-only">이 측정에 없는 채널</span>
              </template>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { FdcSetMatrix, FdcSetStatus } from '~/utils/skewvoirAnalysis/fdcSet'

// Presentational only. Row composition, category grouping, channel ranking, the
// per-run roll-ups and the absent-cell rule are all decided in
// utils/skewvoirAnalysis/fdcSet.ts — this turns that model into markup.
//
// A DOM table rather than an ECharts heatmap on purpose: DESIGN.md's colour
// contract is the --sk-* custom properties, and ECharts draws to canvas where it
// cannot read them (see the note in main.css). Painting status here keeps the
// fills on the same tokens as every other status surface in the app, and the
// theme switch comes for free.
defineProps<{ matrix: FdcSetMatrix }>()

// Status lives in the `-soft` CELL BACKGROUND. Every raw mean and peer σ keeps
// full ink: DESIGN.md reserves semantic text colour for status labels, never
// for the data value itself. `ok` stays unfilled — a green wash on the majority
// of cells would drown out the few that need reading.
//
// `ok` keeps FULL ink all the same. Not filling the cell is a background
// decision; the raw mean and peer σ inside it are the values the user came to read, and
// DESIGN.md is explicit that muted ink is for labels only (`--sk-ink-muted`:
// "never data values"). Quieting the majority of the numbers would hand the
// table's own content the treatment reserved for its chrome.
const TONE: Record<FdcSetStatus, string> = {
  ok: 'text-(--sk-ink)',
  warning: 'bg-(--sk-warn-soft) text-(--sk-ink)',
  bad: 'bg-(--sk-bad-soft) text-(--sk-ink)',
  insufficient: 'bg-(--sk-muted-surface) text-(--sk-ink)'
}

const STATUS_LABEL: Record<FdcSetStatus, string> = {
  ok: '정상',
  warning: '주의',
  bad: '이상',
  insufficient: '평가 불가'
}

const LEGEND = ['bad', 'warning', 'ok', 'insufficient', 'absent'] as const

const LEGEND_FILL: Record<(typeof LEGEND)[number], string> = {
  bad: 'bg-(--sk-bad-soft)',
  warning: 'bg-(--sk-warn-soft)',
  ok: 'bg-(--sk-surface)',
  insufficient: 'bg-(--sk-muted-surface)',
  absent: 'border-dashed bg-(--sk-surface)'
}

const LEGEND_LABEL: Record<(typeof LEGEND)[number], string> = {
  bad: '이상',
  warning: '주의',
  ok: '정상',
  insufficient: '평가 불가',
  absent: '이 측정에 없는 채널'
}

const rawValueFormatter = new Intl.NumberFormat('ko-KR', {
  maximumFractionDigits: 2
})

const formatRawValue = (value: number): string => rawValueFormatter.format(value)

const formatSigned = (value: number): string =>
  `${value >= 0 ? '+' : ''}${value.toFixed(2)}`
</script>
