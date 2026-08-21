<template>
  <div class="dashboard-surface flex flex-col overflow-hidden rounded-(--sk-r-card)">
    <!-- Headline: what this wafer says about itself, in one sentence. -->
    <div class="flex flex-wrap items-center gap-x-2.5 gap-y-1.5 border-b border-(--sk-border-soft) px-4 py-2.5">
      <span
        class="shrink-0 gap-1.5 sk-signal-badge"
        :class="verdict.tone === 'attention' ? 'bg-(--sk-warn-soft) text-(--sk-warn)' : 'bg-(--sk-ok-soft) text-(--sk-ok)'"
      >
        <span
          class="h-1.5 w-1.5 rounded-full"
          :class="verdict.tone === 'attention' ? 'bg-(--sk-warn)' : 'bg-(--sk-ok)'"
        />
        {{ verdict.badge }}
      </span>

      <p class="min-w-0 flex-1 text-base leading-snug font-semibold text-(--sk-ink)">
        <span
          v-for="(seg, i) in verdict.sentence"
          :key="i"
          :class="{
            'font-mono tabular-nums': seg.kind === 'num',
            'text-(--sk-bad)': seg.kind === 'bad'
          }"
        >{{ seg.text }}</span>
      </p>

      <!-- The thresholds are printed, not implied. A verdict nobody can audit is
           a verdict nobody should act on. -->
      <UPopover :content="{ align: 'end' }">
        <UButton
          icon="i-lucide-info"
          color="neutral"
          variant="ghost"
          size="xs"
          aria-label="판정 규칙"
        />
        <template #content>
          <div class="w-80 space-y-2 p-3">
            <p class="sk-label">
              판정 규칙
            </p>
            <ul class="list-disc space-y-1.5 pl-4 sk-meta">
              <li
                v-for="rule in RULES"
                :key="rule"
              >
                {{ rule }}
              </li>
            </ul>
          </div>
        </template>
      </UPopover>

      <EbeamSkewvoirDashboardConditions
        class="shrink-0"
        :analysis="analysis"
      />
    </div>

    <!-- Three questions, one column each: how much landed, how far it spread,
         where it went wrong. -->
    <div class="grid grid-cols-1 sm:grid-cols-3">
      <!-- 커버리지 -->
      <section class="flex flex-col gap-1 px-4 py-2.5">
        <div class="flex items-baseline gap-2">
          <span class="sk-eyebrow">커버리지</span>
          <button
            type="button"
            class="ml-auto shrink-0 rounded-(--sk-r-sidebar) sk-label transition-colors duration-200 hover:text-(--sk-ink)"
            :aria-expanded="detail === 'coverage'"
            @click="toggle('coverage')"
          >
            자세히
          </button>
        </div>
        <div class="flex flex-wrap items-baseline gap-x-2.5 gap-y-1">
          <span class="font-mono text-xl font-bold tabular-nums text-(--sk-ink)">
            {{ cov.measured }}<span class="text-sm text-(--sk-ink-muted)">/{{ cov.total }}</span>
          </span>
          <span
            v-if="cov.failed > 0"
            class="font-mono text-xs font-bold tabular-nums text-(--sk-bad)"
          >실패 {{ cov.failed }}</span>
          <span class="flex items-baseline gap-1">
            <span class="sk-label">Align</span>
            <span class="sk-value-num font-bold">{{ align.total }}</span>
            <span
              v-if="align.methods.length"
              class="sk-label"
            >{{ align.methods.join(' · ') }}</span>
          </span>
          <EbeamSkewvoirDashboardAlignImages
            class="shrink-0"
            :analysis="analysis"
          />
        </div>
        <p class="flex flex-wrap items-baseline gap-x-1.5 gap-y-0.5">
          <template
            v-for="(c, i) in causeSummary"
            :key="c.label"
          >
            <span
              v-if="i > 0"
              class="sk-label"
            >·</span>
            <span class="sk-label">{{ c.label }}</span>
            <span
              v-if="c.value"
              class="sk-value-num"
              :class="c.bad ? 'text-(--sk-bad)' : ''"
            >{{ c.value }}</span>
          </template>
        </p>
      </section>

      <!-- 산포 -->
      <section class="flex flex-col gap-1 border-(--sk-border-soft) px-4 py-2.5 sm:border-l">
        <div class="flex items-baseline gap-2">
          <span class="sk-eyebrow">산포</span>
          <button
            type="button"
            class="ml-auto shrink-0 rounded-(--sk-r-sidebar) sk-label transition-colors duration-200 hover:text-(--sk-ink)"
            :aria-expanded="detail === 'spread'"
            @click="toggle('spread')"
          >
            자세히
          </button>
        </div>
        <div
          v-if="spread"
          class="flex flex-wrap items-baseline gap-x-2.5 gap-y-1"
        >
          <span class="font-mono text-xl font-bold tabular-nums text-(--sk-ink)">{{ formatFixed(spread.threeSigma, 3) }}</span>
          <span class="sk-label">3σ<template v-if="unit"> · {{ unit }}</template></span>
          <span class="flex items-baseline gap-1">
            <span class="sk-label">σ</span>
            <span class="sk-value-num">{{ formatFixed(spread.std, 3) }}</span>
            <span class="sk-label">→</span>
            <span class="sk-value-num">{{ formatFixed(spread.madSigma, 3) }}</span>
          </span>
        </div>
        <span
          v-else
          class="text-xs font-semibold text-(--sk-ink-subtle)"
        >평가 불가 — 산포를 정의하려면 측정 site 가 2개 이상 필요합니다.</span>
        <p class="flex flex-wrap items-baseline gap-x-1.5 sk-label">
          <template v-if="verdict.outlierShare !== null">
            <span>이상치 제외 시</span>
            <span class="sk-value-num">{{ Math.round(verdict.outlierShare * 100) }}%</span>
            <span>축소 ·</span>
          </template>
          <span>넓다/좁다는 기준선이 없어 판정하지 않습니다.</span>
        </p>
      </section>

      <!-- 이상 site -->
      <section class="flex flex-col gap-1 border-(--sk-border-soft) px-4 py-2.5 sm:border-l">
        <div class="flex items-baseline gap-2">
          <span class="sk-eyebrow">이상 site</span>
          <button
            type="button"
            class="ml-auto shrink-0 rounded-(--sk-r-sidebar) sk-label transition-colors duration-200 hover:text-(--sk-ink)"
            :aria-expanded="detail === 'anomaly'"
            @click="toggle('anomaly')"
          >
            자세히
          </button>
        </div>
        <div class="flex flex-wrap items-baseline gap-x-2.5 gap-y-1">
          <span
            v-if="ov.status === 'evaluated'"
            class="font-mono text-xl font-bold tabular-nums"
            :class="ov.outlierCount > 0 ? 'text-(--sk-bad)' : 'text-(--sk-ink)'"
          >{{ ov.outlierCount }}</span>
          <span
            v-else
            class="text-xs font-semibold text-(--sk-ink-subtle)"
          >평가 불가</span>
          <span
            v-if="clustering.verdict"
            class="font-mono text-xs font-bold"
            :class="clustering.verdict === 'clustered' ? 'text-(--sk-bad)' : 'text-(--sk-ink)'"
          >{{ clustering.verdict === 'clustered' ? '군집' : '분산' }}</span>
          <span class="flex flex-wrap items-baseline gap-x-1">
            <template
              v-for="(s, i) in clustering.sectors"
              :key="s.key"
            >
              <span
                v-if="i > 0"
                class="sk-label"
              >·</span>
              <span class="sk-label">{{ s.label }}</span>
              <span class="sk-value-num">{{ s.count }}</span>
            </template>
          </span>
        </div>
        <button
          v-if="firstOutlier"
          type="button"
          class="self-start text-xs font-semibold text-(--sk-accent) transition-colors duration-200 hover:text-(--sk-brand-ink)"
          @click="showOnWafer"
        >
          웨이퍼에서 보기 →
        </button>
        <span
          v-else
          class="sk-label"
        >{{ clustering.reason ?? '표시할 이상 site 가 없습니다.' }}</span>
      </section>
    </div>

    <!-- 자세히 — everything the four cards this block replaced used to print. It
         is folded, not deleted: the top block answers "can I trust this wafer",
         and the evidence behind each answer is one click away. -->
    <div
      v-if="detail"
      class="flex flex-col gap-2 border-t border-(--sk-border-soft) bg-(--sk-muted-surface) px-4 py-3"
    >
      <!-- 커버리지: the four causes, never summed into one health score -->
      <template v-if="detail === 'coverage'">
        <div class="flex flex-wrap items-baseline gap-x-3 gap-y-1">
          <span class="sk-label">해당 원인</span>
          <span
            class="sk-value-num"
            :class="breakdown.failedCount > 0 ? 'font-bold text-(--sk-bad)' : ''"
          >{{ breakdown.failedCount }}</span>
          <span class="sk-label">/ 4</span>
          <template v-if="breakdown.unknownCount > 0">
            <span class="sk-label">· 미상</span>
            <span class="sk-value-num">{{ breakdown.unknownCount }}</span>
          </template>
        </div>
        <div class="flex flex-wrap gap-x-5 gap-y-1.5">
          <div
            v-for="r in breakdown.reasons"
            :key="r.key"
            class="flex min-w-0 flex-col gap-0.5"
            :title="r.detail"
          >
            <span class="sk-label">{{ r.label }}</span>
            <span
              class="font-mono text-sm font-bold tabular-nums"
              :class="r.status === 'fail' ? 'text-(--sk-bad)' : r.status === 'unknown' ? 'text-(--sk-ink-subtle)' : 'text-(--sk-ink)'"
            >{{ statusText(r) }}</span>
          </div>
        </div>
      </template>

      <!-- 산포: level / spread / shape, the three CDU questions -->
      <template v-else-if="detail === 'spread'">
        <div class="flex flex-wrap items-baseline gap-x-3 gap-y-1">
          <span class="sk-label">유효 N</span>
          <span class="sk-value-num font-bold">{{ metrics.n }}</span>
          <template v-if="metrics.missing > 0">
            <span class="sk-label">· 결측</span>
            <span class="sk-value-num text-(--sk-bad)">{{ metrics.missing }}</span>
          </template>
        </div>
        <div
          v-for="line in cduLines"
          :key="line.key"
          class="flex flex-wrap items-baseline gap-x-4 gap-y-1"
        >
          <span class="w-16 shrink-0 sk-label">{{ line.label }}</span>
          <template v-if="line.cells.length">
            <div
              v-for="cell in line.cells"
              :key="cell.label"
              class="flex items-baseline gap-1"
            >
              <span class="font-mono text-[11px] text-(--sk-ink-muted)">{{ cell.label }}</span>
              <span class="font-mono text-sm font-bold tabular-nums text-(--sk-ink)">{{ cell.value }}</span>
            </div>
          </template>
          <span
            v-else
            class="text-xs font-semibold text-(--sk-ink-subtle)"
          >평가 불가 — {{ line.reason }}</span>
        </div>
        <p class="sk-meta">
          σ와 σ(이상치 제외) 가 비슷하면 웨이퍼 전체가 넓은 것이고, σ(이상치 제외) 가 훨씬 작으면 몇 개 site 가 σ 를 부풀린 것입니다.
        </p>
      </template>

      <!-- 이상 site: what the 군집 verdict was computed from -->
      <template v-else>
        <div class="flex flex-wrap items-baseline gap-x-3 gap-y-1">
          <span class="sk-label">좌표 확인</span>
          <span class="sk-value-num font-bold">{{ clustering.placed }}</span>
          <template v-if="clustering.unplaced > 0">
            <span class="sk-label">· 좌표 없음</span>
            <span class="sk-value-num">{{ clustering.unplaced }}</span>
          </template>
        </div>
        <p
          v-if="clustering.reason"
          class="text-xs font-semibold text-(--sk-ink-subtle)"
        >
          평가 불가 — {{ clustering.reason }}
        </p>
        <p class="sk-meta">
          군집 판정은 이상 site 와 실패 site 를 함께 놓고 봅니다 — 웨이퍼의 어디가 잘못됐는지는 하나의 질문이고, 실패만 세면 이상이 한쪽에 몰린 웨이퍼를 분산으로 부르게 됩니다. 이상 site 수({{ ov.outlierCount }})는 그 합산과 무관하게 그대로입니다.
        </p>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { SkewvoirAnalysis } from '~/composables/useSkewvoirAnalysis'
import { analyzeSpatial } from '~/utils/skewvoirAnalysis/spatial'
import { cduMetrics, failureBreakdown, sectorClustering, type FailureReason } from '~/utils/skewvoirAnalysis/cdu'
import { measurementVerdict } from '~/utils/skewvoirAnalysis/verdict'

// The 측정 개요 top block. It replaced four cards — 측정 성공률 · 실패 원인 ·
// CDU 지표 · 측정 조건 — that between them answered "can I trust this wafer"
// twice and left the reader to join the halves. One verdict sentence answers it
// once; three columns carry the evidence; 자세히 carries everything the cards
// printed that the verdict does not need.
//
// Every number here comes from a module that already owned it. This component
// derives nothing: verdict.ts composes the sentence, cdu.ts the metrics and the
// clustering, overview.ts the outlier count.
const props = defineProps<{ analysis: SkewvoirAnalysis }>()
const emit = defineEmits<{ (e: 'show-on-wafer'): void }>()

const RULES = [
  '실패·결측이 있거나 이상 site 가 있으면 확인 필요, 그 외에는 정상입니다.',
  'σ(이상치 제외)/σ 가 0.8 이하일 때만 “σ 의 n% 가 이상 site 에서” 라고 적습니다.',
  '좌표가 있는 이상·실패 site 가 3개 이상이고 한 섹터가 60% 이상을 차지하면 군집입니다.',
  'spec·target 계약이 없어 “산포가 넓다/좁다”, In Spec, Cp/Cpk 는 판정하지 않습니다.'
]

const unit = computed(() => props.analysis.activeUnit.value)
const ov = computed(() => props.analysis.activeOverview.value)
const cov = computed(() => ov.value.coverage)

// Level + spread come from the FULL row set, not from MsrParamSummary — that
// summary carries no median and no MAD, so the robust half cannot come from it.
const metrics = computed(() =>
  cduMetrics(props.analysis.siteRows.value, props.analysis.activeParam.value, unit.value)
)
const spread = computed(() => metrics.value.spread)

const breakdown = computed(() =>
  failureBreakdown(
    props.analysis.siteRows.value,
    props.analysis.activeParam.value,
    props.analysis.focusRow.value
  )
)

const spatial = computed(() =>
  analyzeSpatial(
    props.analysis.siteRows.value,
    props.analysis.activeParam.value,
    props.analysis.waferGeo.value,
    { unit: unit.value }
  )
)

// Sites flagged abnormal/watch — overview.ts's own list, so the count here, the
// ◎ rings on the wafer and the 이상·실패 table can never disagree.
const outlierRows = computed(() => ov.value.tableRows.filter(r => r.kind !== 'failed'))
const firstOutlier = computed(() => outlierRows.value[0] ?? null)

// Where the wafer went wrong, spatially: outliers AND failures. They are pooled
// for THIS question only — `outlierCount` above never absorbs a failure, which
// is the separation utils/overview.ts owns.
const clustering = computed(() => {
  const flagged = new Set(outlierRows.value.map(r => r.sequence))
  const placedOutliers = spatial.value.sites
    .filter(s => flagged.has(s.sequence))
    .map(s => ({ sector: s.sector }))
  return sectorClustering([...spatial.value.failures, ...placedOutliers])
})

const align = computed(() => {
  const a = props.analysis.focusFile.value?.alignment
  const methods = a ? Object.values(a.offset).map(o => o[0]) : []
  return { total: methods.length, methods }
})

const verdict = computed(() => measurementVerdict({
  paramLabel: props.analysis.activeParamLabel.value,
  unit: unit.value,
  metrics: metrics.value,
  outlierCount: ov.value.status === 'evaluated' ? ov.value.outlierCount : 0,
  failedCauses: breakdown.value.failedCount,
  missing: cov.value.failed,
  measured: cov.value.measured,
  total: cov.value.total,
  clustering: clustering.value
}))

// The caption under 커버리지 names the causes that actually failed. A line that
// listed all four would restate the 자세히 panel; a line that named none would
// let a failed Align hide behind a healthy site count.
const causeSummary = computed<{ label: string, value: string, bad: boolean }[]>(() => {
  // A cause with no count behind it (msr_check, align) is named as failing in
  // words, or "실패" would disappear behind a blank number.
  const out = breakdown.value.reasons
    .filter(r => r.status === 'fail')
    .map(r => r.count == null
      ? { label: `${r.label} 실패`, value: '', bad: true }
      : { label: r.label, value: `${r.count}`, bad: true })
  if (!out.length) out.push({ label: '실패 원인 없음', value: '', bad: false })
  if (breakdown.value.unknownCount > 0) {
    out.push({ label: '평가 불가', value: `${breakdown.value.unknownCount}`, bad: false })
  }
  return out
})

const signed = (value: number, digits: number) => `${value >= 0 ? '+' : ''}${formatFixed(value, digits)}`

// Shape reuses the feature table's ALREADY-COMPUTED centre→edge delta (OLS fit
// of cd_value against site radius). Recomputing it here would be a second
// formula for the same question.
const shape = computed(() => {
  const msr = props.analysis.focusMsr.value
  return props.analysis.featureRows.value.find(r => r.msr === msr)?.spatial ?? null
})

interface Cell { label: string, value: string }

const cduLines = computed<{ key: string, label: string, cells: Cell[], reason: string }[]>(() => {
  const level = metrics.value.level
  const s = spread.value
  return [
    {
      key: 'level',
      label: 'Wafer level',
      // No target offset: this repo has no spec/target contract to subtract
      // against, and an offset against an invented target is a fiction.
      cells: level
        ? [
            { label: 'mean', value: formatFixed(level.mean, 2) },
            { label: 'median', value: formatFixed(level.median, 2) }
          ]
        : [],
      reason: '측정된 site 가 없습니다.'
    },
    {
      key: 'spread',
      label: 'Spread',
      cells: s
        ? [
            { label: 'σ', value: formatFixed(s.std, 3) },
            { label: '3σ', value: formatFixed(s.threeSigma, 3) },
            // MAD scaled to a sigma so the two stand on one axis. The label says
            // what the number MEANS, not how it was computed.
            { label: 'σ(이상치 제외)', value: formatFixed(s.madSigma, 3) },
            { label: 'range', value: formatFixed(s.range, 3) }
          ]
        : [],
      reason: '산포를 정의하려면 측정 site 가 2개 이상 필요합니다.'
    },
    {
      key: 'shape',
      label: 'Shape',
      cells: shape.value ? [{ label: '중심→외곽', value: signed(shape.value.value, 3) }] : [],
      reason: '좌표를 확인할 수 있는 site 가 부족해 반경 추세를 적합할 수 없습니다.'
    }
  ]
})

// '평가 불가' is printed, not hidden: a cause nobody could judge must not read
// as a cause that passed.
const statusText = (r: FailureReason): string => {
  if (r.status === 'unknown') return '평가 불가'
  if (r.count == null) return r.status === 'fail' ? '실패' : '정상'
  // fail_ratio arrives as a percent already — nothing is scaled here.
  return r.percent == null
    ? `${r.count}`
    : `${r.count}/${r.total} · ${formatFixed(r.percent, 2)}%`
}

type DetailKey = 'coverage' | 'spread' | 'anomaly'
const detail = ref<DetailKey | null>(null)
const toggle = (key: DetailKey) => {
  detail.value = detail.value === key ? null : key
}

// Focus the worst outlier, then let the view that owns the layout bring the
// wafer into sight. tableRows is already sorted worst-first.
const showOnWafer = () => {
  const first = firstOutlier.value
  if (!first) return
  props.analysis.setFocusedSequence(first.sequence)
  emit('show-on-wafer')
}
</script>
