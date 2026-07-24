<script setup lang="ts">
import {
  buildMagPixelTable, fovNm, recommend, MARGIN_PRESETS, DEFAULT_MARGIN,
  DEFAULT_MIN_PX_PER_CD, DEFAULT_PATTERN_COUNT, type CalcInput, type MagSeries
} from '~/utils/magPixel'

useHead({ title: 'Mag/Pixel 가이드 | SKEWNONO' })

const series = ref<MagSeries>('CG')
const cdNm = ref<number | null>(null)
const pitchNm = ref<number | null>(null)
const patternCount = ref(DEFAULT_PATTERN_COUNT)
const marginRatio = ref<number>(DEFAULT_MARGIN)
const minPxPerCd = ref(DEFAULT_MIN_PX_PER_CD)
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

/** CD가 없으면 판정하지 않고 순수 참조표로 둔다. */
const pitchError = computed(() =>
  cdValue.value != null && pitchValue.value != null && pitchValue.value <= cdValue.value
    ? 'Pitch는 CD보다 커야 합니다.'
    : null
)

const result = computed(() => {
  if (cdValue.value == null || cdValue.value <= 0 || pitchError.value) return null
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

const showSim = ref(false)

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
  <div class="mx-auto flex max-w-6xl flex-col gap-5 p-5">
    <header>
      <h1 class="sk-page-title">
        CD-SEM Mag / Pixel 가이드
      </h1>
      <p class="mt-1 text-sm text-(--sk-ink-muted)">
        목표 패턴 크기에서 적정 배율과 픽셀 수를 역산합니다. FOV = 135,000 µm ÷ Mag.
      </p>
    </header>

    <!-- 입력 -->
    <section class="flex flex-wrap items-end gap-3 rounded-(--sk-r-sidebar) border border-(--sk-border) p-4">
      <div>
        <div class="mb-1.5 font-mono text-[10px] tracking-wide text-(--sk-ink-muted)">
          SERIES
        </div>
        <UFieldGroup size="xs">
          <UButton
            v-for="s in (['CG', 'GT'] as MagSeries[])"
            :key="s"
            :label="s"
            :color="series === s ? 'primary' : 'neutral'"
            :variant="series === s ? 'solid' : 'outline'"
            :aria-pressed="series === s"
            @click="series = s"
          />
        </UFieldGroup>
      </div>

      <div>
        <div class="mb-1.5 font-mono text-[10px] tracking-wide text-(--sk-ink-muted)">
          CD (nm)
        </div>
        <UInput
          v-model.number="cdNm"
          type="number"
          size="xs"
          placeholder="20"
          class="w-24"
        />
      </div>

      <div>
        <div class="mb-1.5 font-mono text-[10px] tracking-wide text-(--sk-ink-muted)">
          PITCH (nm) · 선택
        </div>
        <UInput
          v-model.number="pitchNm"
          type="number"
          size="xs"
          placeholder="35"
          class="w-28"
        />
      </div>

      <div>
        <div class="mb-1.5 font-mono text-[10px] tracking-wide text-(--sk-ink-muted)">
          패턴 수
        </div>
        <UInput
          v-model.number="patternCount"
          type="number"
          size="xs"
          class="w-20"
        />
      </div>

      <div>
        <div class="mb-1.5 font-mono text-[10px] tracking-wide text-primary">
          여유 마진 (각 변)
        </div>
        <UFieldGroup size="xs">
          <UButton
            v-for="m in MARGIN_PRESETS"
            :key="m"
            :label="marginLabel(m)"
            :color="marginRatio === m ? 'primary' : 'neutral'"
            :variant="marginRatio === m ? 'solid' : 'outline'"
            :aria-pressed="marginRatio === m"
            @click="marginRatio = m"
          />
        </UFieldGroup>
      </div>

      <div>
        <div class="mb-1.5 font-mono text-[10px] tracking-wide text-(--sk-ink-muted)">
          기준 px/CD <span class="text-amber-500">·잠정</span>
        </div>
        <UInput
          v-model.number="minPxPerCd"
          type="number"
          size="xs"
          class="w-20"
        />
      </div>
    </section>

    <p
      v-if="pitchError"
      class="rounded-(--sk-r-sidebar) bg-red-500/10 px-3 py-2 text-sm text-red-600 dark:text-red-400"
    >
      {{ pitchError }}
    </p>

    <p
      v-else-if="result?.pitchAssumed"
      class="font-mono text-[11px] text-(--sk-ink-muted)"
    >
      Pitch를 비워서 CD × 2 = {{ result.effectivePitchNm }} nm로 가정했습니다 ·
      기준 px/CD는 사내 기준 확정 전까지 잠정값입니다
    </p>

    <!-- 모식도 + 추천 -->
    <section
      v-if="result"
      class="flex flex-wrap items-start gap-4 rounded-(--sk-r-sidebar) border border-(--sk-border) p-4"
    >
      <div class="min-w-80 flex-1">
        <MagpixelPatternSchematic
          v-if="result.mag && result.nmPerPx"
          :cd-nm="calcInput.cdNm"
          :pitch-nm="result.effectivePitchNm"
          :pattern-count="patternValue"
          :fov-nm="fovNm(result.mag) ?? 0"
          :nm-per-px="result.nmPerPx"
        />

        <UButton
          v-if="result.pixels && result.nmPerPx"
          class="mt-3"
          size="xs"
          color="neutral"
          variant="outline"
          :icon="showSim ? 'i-lucide-chevron-down' : 'i-lucide-chevron-right'"
          label="SEM 이미지 미리보기"
          @click="showSim = !showSim"
        />
        <div
          v-if="showSim && result.pixels && result.nmPerPx"
          class="mt-3"
        >
          <MagpixelSemSimulation
            :cd-nm="calcInput.cdNm"
            :pitch-nm="result.effectivePitchNm"
            :pattern-count="patternValue"
            :pixels="result.pixels"
            :nm-per-px="result.nmPerPx"
          />
        </div>
      </div>

      <MagpixelRecommendationPanel
        class="min-w-80 flex-1"
        :rec="result"
        :calc="calcInput"
      />
    </section>

    <!-- 테이블 -->
    <section class="rounded-(--sk-r-sidebar) border border-(--sk-border) p-4">
      <div class="mb-3 flex items-center justify-between">
        <h2 class="font-mono text-[10px] tracking-wide text-(--sk-ink-muted)">
          {{ series }} SERIES · MAG × PIXEL
        </h2>
        <USwitch
          v-model="showWide"
          size="xs"
          label="2048 · 4096 표시"
        />
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
</template>
