<script setup lang="ts">
import {
  buildMagPixelTable, fovNm, recommend, magRange, magLabel, MARGIN_PRESETS, DEFAULT_MARGIN,
  DEFAULT_MIN_PX_PER_CD, DEFAULT_PATTERN_COUNT, SERIES_MODEL,
  type CalcInput, type MagSeries
} from '~/utils/magPixel'
import type { MetaBarStat } from '~/components/ebeam/MetaBar.vue'

useHead({ title: 'Mag/Pixel 가이드 | SKEWNONO' })

/** 빈 화면으로 시작하면 이 페이지가 무엇에 답하는지가 보이지 않는다. CG 계열의
 *  대표 조합을 미리 채워 첫 화면부터 답이 서 있게 하고, 그것이 예시라는 사실은
 *  메타바의 배지가 밝힌다 — ×로 비우면 순수 참조표로 돌아간다. */
const EXAMPLE = {
  series: 'CG' as MagSeries,
  cdNm: 20,
  pitchNm: 45,
  patternCount: DEFAULT_PATTERN_COUNT,
  marginRatio: DEFAULT_MARGIN
} as const

const series = ref<MagSeries>(EXAMPLE.series)
const cdNm = ref<number | null>(EXAMPLE.cdNm)
const pitchNm = ref<number | null>(EXAMPLE.pitchNm)
const patternCount = ref<number>(EXAMPLE.patternCount)
const marginRatio = ref<number>(EXAMPLE.marginRatio)
const minPxPerCd = ref<number>(DEFAULT_MIN_PX_PER_CD)
const showWide = ref(false)

/** UInput type="number" keeps a raw '' when the field is cleared, so `!= null`
 *  is not enough — normalise to a real number or null before any comparison. */
const numOrNull = (v: unknown): number | null =>
  typeof v === 'number' && Number.isFinite(v) ? v : null

const cdValue = computed(() => numOrNull(cdNm.value))
const pitchValue = computed(() => numOrNull(pitchNm.value))
const patternValue = computed(() => numOrNull(patternCount.value) ?? DEFAULT_PATTERN_COUNT)
const thresholdValue = computed(() => numOrNull(minPxPerCd.value) ?? DEFAULT_MIN_PX_PER_CD)

const rows = computed(() => buildMagPixelTable(series.value))

/** 계열마다 배율 구간이 다르다 — GT는 500K 위로 5단을 더 갖는다. 캡션을
 *  고정 문자열로 두면 GT를 고른 순간 거짓말이 되므로 실제 표에서 읽는다.
 *  라벨은 참조표와 같은 magLabel()을 쓴다 — 이 캡션만 1M으로 접었던 탓에
 *  한 화면에서 같은 배율이 "1M"과 "1000K"로 동시에 불렸다. */
const seriesRangeLabel = computed(() => {
  const range = magRange(series.value)
  const first = range[0]
  const last = range[range.length - 1]
  if (first == null || last == null) return ''
  return `${magLabel(first)}–${magLabel(last)} · ${range.length}단`
})

/** CD가 없으면 판정하지 않고 순수 참조표로 둔다. */
const pitchError = computed(() =>
  cdValue.value != null && pitchValue.value != null && pitchValue.value <= cdValue.value
    ? 'Pitch는 CD보다 커야 합니다.'
    : null
)

/** 패턴 수가 0·음수·소수면 requiredFovNm()이 null을 내고 화면 절반이 이유 없이
 *  사라진다. pitchError와 같은 자리에서 이유를 말해준다 — 빈 칸은 기본값
 *  8로 대체되므로 오류가 아니다. 소수를 막는 이유는 계산은 2.5주기로 하면서
 *  모식도는 Array.from({length: 2.5})라 2개만 그려 그림과 숫자가 어긋나서다. */
const patternError = computed(() => {
  const n = numOrNull(patternCount.value)
  if (n === null) return null
  return n > 0 && Number.isInteger(n) ? null : '패턴 수는 1 이상의 정수여야 합니다.'
})

const result = computed(() => {
  if (cdValue.value == null || cdValue.value <= 0 || pitchError.value || patternError.value) return null
  return recommend({
    series: series.value,
    cdNm: cdValue.value,
    pitchNm: pitchValue.value,
    patternCount: patternValue.value,
    marginRatio: marginRatio.value,
    minPxPerCd: thresholdValue.value
  })
})

const marginLabel = (r: number) => `${Math.round(r * 100)}%`

/** 입력이 예시 그대로인 동안에만 배지를 띄운다 — 한 글자라도 바꾼 순간부터는
 *  사용자의 입력이므로 "예시"라고 부르면 거짓말이 된다. 기준 px/CD도 포함한다:
 *  마진과 같은 성격의 필터인데 이것만 빠져 있어, 슬라이더로 합격선을 옮겨
 *  표의 ●/✗를 다시 가른 뒤에도 배지가 "예시"라고 남아 있었다. */
const isExample = computed(() =>
  series.value === EXAMPLE.series
  && cdValue.value === EXAMPLE.cdNm
  && pitchValue.value === EXAMPLE.pitchNm
  && patternValue.value === EXAMPLE.patternCount
  && marginRatio.value === EXAMPLE.marginRatio
  && thresholdValue.value === DEFAULT_MIN_PX_PER_CD
)

/** 배지의 ×는 "예시를 지운다"는 뜻이므로 CD·Pitch만 비운다. 계열·패턴 수·마진은
 *  값이 아니라 조건이라 비울 대상이 없다 — 기본값으로 남는다. */
const clearExample = () => {
  cdNm.value = null
  pitchNm.value = null
}

const resetInputs = () => {
  series.value = EXAMPLE.series
  cdNm.value = EXAMPLE.cdNm
  pitchNm.value = EXAMPLE.pitchNm
  patternCount.value = EXAMPLE.patternCount
  marginRatio.value = EXAMPLE.marginRatio
  minPxPerCd.value = DEFAULT_MIN_PX_PER_CD
}

/** 메타바가 페이지의 답을 한 줄로 든다 — 필요 FOV → 추천 배율 → 픽셀 → 합격 여부
 *  순서로, 사용자가 실제로 읽는 순서 그대로다. */
const metaStats = computed<MetaBarStat[]>(() => {
  const r = result.value
  const passes = r?.pxPerCd != null && r.pxPerCd >= thresholdValue.value
  return [
    {
      key: 'required-fov',
      value: r ? Math.round(r.requiredFovNm).toLocaleString() : '—',
      label: '필요 FOV nm'
    },
    { key: 'mag', value: r ? magLabel(r.mag) : '—', label: '추천 MAG' },
    { key: 'pixels', value: r?.pixels ?? '—', label: '픽셀' },
    {
      key: 'px-per-cd',
      value: r?.pxPerCd?.toFixed(1) ?? '—',
      label: `PX/CD · 기준 ${thresholdValue.value}`,
      tone: r == null ? 'neutral' : passes ? 'ok' : 'bad'
    }
  ]
})

/** 모식도/시뮬레이션/추천 패널이 공유하는 계산 입력. 정규화된 computed만 담는다 —
 *  raw ref(cdNm 등)는 UInput type="number"가 지운 값일 때 ''를 들고 있을 수 있다. */
const calcInput = computed<CalcInput>(() => ({
  series: series.value,
  cdNm: cdValue.value ?? 0,
  pitchNm: pitchValue.value,
  patternCount: patternValue.value,
  marginRatio: marginRatio.value,
  minPxPerCd: thresholdValue.value
}))
</script>

<template>
  <!-- 1440px 밀집 예외: 좌측 고정 입력·답 레일 + 우측 상세라는 리스트-플러스-상세
       성격이라 H/W 관리와 같은 폭을 쓴다 (DESIGN.md §Layout). -->
  <div class="mx-auto w-full max-w-[1440px] space-y-6">
    <div>
      <EbeamMetaBar
        eyebrow="CD-SEM · MAG/PIXEL"
        title="Mag / Pixel 가이드"
        subtitle="FOV = 135,000 µm ÷ Mag · 패턴이 화면에 들어오는 한도에서 가장 높은 배율을 고릅니다"
        :stats="metaStats"
      >
        <template #actions>
          <button
            v-if="isExample"
            type="button"
            class="inline-flex items-center gap-1.5 rounded-[var(--sk-r-chip)] border border-(--sk-brand-soft) bg-(--sk-brand-soft) px-2.5 py-1 text-xs font-semibold text-(--sk-brand-ink) transition-colors duration-200 hover:bg-transparent"
            aria-label="예시 입력 비우기"
            @click="clearExample"
          >
            예시 입력
            <UIcon
              name="i-lucide-x"
              class="h-3 w-3"
            />
          </button>
        </template>
      </EbeamMetaBar>

      <!-- 앞 문장은 예시가 살아 있을 때만 참이다. v-if 없이 두었더니 ×로 예시를
           지운 뒤에도 "채워져 있습니다"라고 남았다. 뒷 문장(잠정 기준)은 입력과
           무관한 사실이라 언제나 선다. -->
      <p class="mt-2 pl-0.5 sk-meta">
        <template v-if="isExample">
          예시 입력이 채워져 있습니다 — 값을 바꾸면 즉시 다시 계산됩니다.
        </template>
        기준 px/CD {{ DEFAULT_MIN_PX_PER_CD }}은 표준안 확정 전까지 잠정값입니다.
      </p>
    </div>

    <div class="grid items-start gap-6 xl:grid-cols-[392px_minmax(0,1fr)]">
      <!-- 좌측 레일 — 입력과 답. 스크롤해도 따라온다. -->
      <div class="flex flex-col gap-4 xl:sticky xl:top-6">
        <section class="dashboard-surface rounded-[var(--sk-r-card)] p-4">
          <div class="mb-3.5 flex items-center justify-between">
            <div class="sk-eyebrow">
              입력 · 스크롤 고정
            </div>
            <UButton
              size="xs"
              color="neutral"
              variant="ghost"
              icon="i-lucide-rotate-ccw"
              label="초기화"
              @click="resetInputs"
            />
          </div>

          <div class="flex flex-col gap-3.5">
            <div class="flex items-center gap-3">
              <span class="w-[92px] flex-none sk-label">Series</span>
              <div class="flex gap-1.5">
                <SkChip
                  v-for="s in (['CG', 'GT'] as MagSeries[])"
                  :key="s"
                  size="sm"
                  :label="SERIES_MODEL[s]"
                  :active="series === s"
                  @click="series = s"
                />
              </div>
              <span class="ml-auto whitespace-nowrap sk-meta">{{ seriesRangeLabel }}</span>
            </div>

            <div class="flex items-center gap-3">
              <span class="w-[92px] flex-none sk-label">CD · Pitch</span>
              <div class="flex items-center gap-1.5">
                <UInput
                  v-model.number="cdNm"
                  type="number"
                  size="xs"
                  placeholder="20"
                  aria-label="CD (nm)"
                  class="w-[104px]"
                  :ui="{ trailing: 'pointer-events-none' }"
                >
                  <template #trailing>
                    <span class="font-mono text-[11px] text-(--sk-ink-subtle)">nm</span>
                  </template>
                </UInput>
                <span class="sk-meta">/</span>
                <UInput
                  v-model.number="pitchNm"
                  type="number"
                  size="xs"
                  placeholder="45"
                  aria-label="Pitch (nm)"
                  class="w-[104px]"
                  :ui="{ trailing: 'pointer-events-none' }"
                >
                  <template #trailing>
                    <span class="font-mono text-[11px] text-(--sk-ink-subtle)">nm</span>
                  </template>
                </UInput>
              </div>
            </div>

            <div class="flex items-center gap-3">
              <span class="w-[92px] flex-none sk-label">패턴 수</span>
              <UInput
                v-model.number="patternCount"
                type="number"
                size="xs"
                aria-label="패턴 수"
                class="w-[104px]"
              />
              <span class="sk-meta">
                pitch 주기 수<template v-if="result">
                  · span {{ (patternValue * result.effectivePitchNm).toLocaleString() }} nm
                </template>
              </span>
            </div>

            <div class="flex items-start gap-3">
              <span class="w-[92px] flex-none pt-1 sk-label">
                여유 마진 <span class="font-normal text-(--sk-ink-subtle)">각 변</span>
              </span>
              <div class="flex flex-wrap gap-1.5">
                <SkChip
                  v-for="m in MARGIN_PRESETS"
                  :key="m"
                  size="sm"
                  :label="marginLabel(m)"
                  :active="marginRatio === m"
                  @click="marginRatio = m"
                />
              </div>
            </div>

            <!-- px/CD는 이 화면의 합격선이자 가장 낯선 입력이다. 다른 입력과 성격이
                 달라 구분선 아래로 내리고, 통상 구간(6–10)을 슬라이더 위에 띠로
                 그려 지금 고른 값이 어디쯤인지 눈으로 잡히게 한다. -->
            <div class="border-t border-(--sk-border-soft) pt-3.5">
              <div class="mb-2.5 flex items-center gap-1.5">
                <span class="sk-label">기준 px/CD</span>
                <span class="inline-flex items-center rounded-[var(--sk-r-chip)] bg-(--sk-warn-soft) px-1.5 py-px text-[10px] font-semibold text-(--sk-warn)">잠정</span>
                <UTooltip text="CD 하나 폭에 픽셀이 최소 몇 개는 얹혀야 하는지 — 측정을 신뢰할 수 있다고 볼 합격선입니다.">
                  <UIcon
                    name="i-lucide-circle-help"
                    class="h-3.5 w-3.5 cursor-help text-(--sk-ink-muted)"
                  />
                </UTooltip>
                <span class="ml-auto font-mono text-base font-bold tabular-nums text-(--sk-ink)">
                  {{ thresholdValue }}
                </span>
              </div>
              <!-- 테라코타인 이유: 이 슬라이더는 합격선을 움직여 아래 표의 ●/✗를
                   다시 가른다 — 화면을 바꾸는 게 아니라 데이터를 좁히므로, 바로
                   위의 계열·마진 칩과 같은 필터 계열이다 (DESIGN.md 리트머스). -->
              <USlider
                v-model="minPxPerCd"
                :min="4"
                :max="20"
                :step="1"
                size="sm"
                aria-label="기준 px/CD"
                :ui="{ range: 'bg-(--sk-brand)', thumb: 'ring-(--sk-brand)' }"
              />
              <div class="mt-1 flex justify-between font-mono text-[10px] text-(--sk-ink-subtle)">
                <span>4</span>
                <span class="font-semibold text-(--sk-ok)">통상 6–10</span>
                <span>20</span>
              </div>
              <p class="mt-2 sk-meta leading-relaxed">
                CD 하나 폭에 픽셀이 최소 몇 개는 얹혀야 측정을 신뢰할 수 있다고 볼지,
                그 합격선입니다. 아래 표에서 이 값을 넘긴 조합만
                <span class="font-semibold text-(--sk-ok)">●</span>,
                미달은 <span class="font-semibold text-(--sk-bad)">✗</span>입니다.
              </p>
            </div>
          </div>

          <p
            v-if="patternError"
            class="mt-3 rounded-[var(--sk-r-sidebar)] border border-(--sk-bad-border) bg-(--sk-bad-soft) px-3 py-2 text-xs text-(--sk-bad)"
          >
            {{ patternError }}
          </p>

          <p
            v-else-if="pitchError"
            class="mt-3 rounded-[var(--sk-r-sidebar)] border border-(--sk-bad-border) bg-(--sk-bad-soft) px-3 py-2 text-xs text-(--sk-bad)"
          >
            {{ pitchError }}
          </p>

          <p
            v-else-if="result?.pitchAssumed"
            class="mt-3 sk-meta"
          >
            Pitch가 비어 있어 CD × 2 = {{ result.effectivePitchNm }} nm로 가정했습니다.
          </p>
        </section>

        <MagpixelRecommendationPanel
          v-if="result"
          :rec="result"
          :calc="calcInput"
        />
      </div>

      <!-- 우측 — 그림과 표 -->
      <div class="flex min-w-0 flex-col gap-6">
        <section
          v-if="result"
          class="dashboard-surface rounded-[var(--sk-r-card)] p-4"
        >
          <div class="mb-3.5 flex flex-wrap items-baseline gap-x-2.5 gap-y-1">
            <h2 class="sk-heading">
              셋업 미리보기
            </h2>
            <span class="sk-meta">
              두 제약을 각각 그립니다 — ① 패턴이 화면에 들어오는가 ② CD에 픽셀이 몇 개 얹히는가
            </span>
          </div>

          <div class="flex flex-wrap items-start gap-5">
            <div class="min-w-[260px] flex-1">
              <MagpixelPatternSchematic
                v-if="result.mag && result.nmPerPx"
                :cd-nm="calcInput.cdNm"
                :pitch-nm="result.effectivePitchNm"
                :pattern-count="patternValue"
                :fov-nm="fovNm(result.mag) ?? 0"
                :nm-per-px="result.nmPerPx"
              />
            </div>

            <!-- 시뮬레이션은 접지 않는다 — "512로 되나?"에 답하는 그림이라
                 펼쳐야만 보이면 질문에 답하지 않은 화면이 된다. 클래스를 주지
                 않는 이유는 이 컴포넌트가 display:contents라서, 폭은 그 안의
                 각 블록이 스스로 정하기 때문이다. -->
            <MagpixelSemSimulation
              v-if="result.pixels && result.nmPerPx"
              :cd-nm="calcInput.cdNm"
              :pitch-nm="result.effectivePitchNm"
              :pattern-count="patternValue"
              :pixels="result.pixels"
              :nm-per-px="result.nmPerPx"
            />
          </div>
        </section>

        <section class="dashboard-surface rounded-[var(--sk-r-card)] p-4">
          <div class="mb-3.5 flex flex-wrap items-center justify-between gap-3">
            <div class="flex flex-wrap items-baseline gap-x-2.5 gap-y-1">
              <h2 class="sk-heading">
                {{ SERIES_MODEL[series] }} 참조표
              </h2>
              <span class="sk-meta">FOV에 담기는 배율과, 각 픽셀 설정의 px 크기입니다</span>
            </div>
            <div class="flex gap-1">
              <SkChip
                size="sm"
                label="512 · 1024"
                :active="!showWide"
                @click="showWide = false"
              />
              <SkChip
                size="sm"
                label="전체 4열"
                :active="showWide"
                @click="showWide = true"
              />
            </div>
          </div>
          <MagpixelResultTable
            :rows="rows"
            :show-wide="showWide"
            :required-fov-nm="result?.requiredFovNm ?? null"
            :cd-nm="cdValue ?? 0"
            :min-px-per-cd="thresholdValue"
            :recommended-mag="result?.reason === 'ok' ? result.mag : null"
            :recommended-pixels="result?.pixels ?? null"
          />
        </section>
      </div>
    </div>
  </div>
</template>
