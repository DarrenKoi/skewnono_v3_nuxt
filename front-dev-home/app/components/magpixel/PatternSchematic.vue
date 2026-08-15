<script setup lang="ts">
// 두 제약을 각각 담당하는 2단 구성이다.
//   ① 전체 FOV      — 패턴 N개 + 마진이 들어오는가 (FOV 제약)
//   ② Pitch 1개 확대 — CD에 픽셀이 몇 개 얹히는가 (픽셀 제약)
import { actualMarginNm } from '~/utils/magPixel'

const props = defineProps<{
  cdNm: number
  pitchNm: number
  patternCount: number
  fovNm: number
  nmPerPx: number
}>()

/** 마진은 요청 비율이 아니라 실제 span에서 역산해야 그림이 헤더의 FOV와 항상
 *  일치한다 — 근거는 actualMarginNm()에 있고, 추천 패널·시뮬레이션도 같은
 *  함수를 쓴다. */
const spanNm = computed(() => props.patternCount * props.pitchNm)
const marginNm = computed(() => actualMarginNm(props.fovNm, spanNm.value))
const marginPct = computed(() => (props.fovNm > 0 ? (marginNm.value / props.fovNm) * 100 : 0))
const bandPct = computed(() => Math.max(0, 100 - 2 * marginPct.value))

const barPct = computed(() => (props.cdNm / props.pitchNm) * 100)
const spacePct = computed(() => 100 - barPct.value)

/** 확대 뷰에서 pitch 하나에 걸치는 픽셀 수. */
const pxPerPitch = computed(() => props.pitchNm / props.nmPerPx)
const pxStepPct = computed(() => 100 / pxPerPitch.value)
const pxPerCdValue = computed(() => props.cdNm / props.nmPerPx)

const patterns = computed(() => Array.from({ length: props.patternCount }, (_, i) => i))
const unitPct = computed(() => 100 / props.patternCount)
/** 마진 빗금은 테라코타다 — 마진은 여유 마진 필터가 만들어내는 값이므로 그 필터와
 *  같은 계열로 묶는다. 크림슨(--sk-accent)은 트림 전용이라 쓰지 않는다. */
const hatch = 'repeating-linear-gradient(45deg,color-mix(in srgb,var(--sk-brand) 32%,transparent) 0 4px,transparent 4px 8px)'
/** 어두운 필드 위의 라인은 크림 잉크로 그린다 — 실제 SEM이 dark-field라 필드는
 *  유지하되, slate 원색 대신 시스템의 --sk-field* 계열을 쓴다. */
const barFill = 'linear-gradient(90deg,var(--sk-field-ink),var(--sk-field-core) 55%,var(--sk-field-ink))'
const pxGridColor = 'color-mix(in srgb,var(--sk-field-ink) 55%,transparent)'
</script>

<template>
  <div>
    <div class="mb-1.5 sk-eyebrow">
      ① 전체 FOV {{ Math.round(fovNm).toLocaleString() }} nm — 패턴 {{ patternCount }}개 · 마진 {{ Math.round(marginNm) }} nm
    </div>
    <div class="flex h-14 overflow-hidden rounded-[var(--sk-r-nav)] bg-(--sk-field)">
      <div
        :style="{ width: `${marginPct}%`, background: hatch }"
        class="border-r border-dashed border-(--sk-brand)"
      />
      <div
        class="flex"
        :style="{ width: `${bandPct}%` }"
      >
        <div
          v-for="i in patterns"
          :key="i"
          class="flex"
          :style="{ width: `${unitPct}%` }"
        >
          <div :style="{ width: `${barPct}%`, background: barFill }" />
          <div :style="{ width: `${spacePct}%` }" />
        </div>
      </div>
      <div
        :style="{ width: `${marginPct}%`, background: hatch }"
        class="border-l border-dashed border-(--sk-brand)"
      />
    </div>
    <div class="mt-1.5 flex font-mono text-[10px]">
      <div
        class="text-center text-(--sk-brand-ink)"
        :style="{ width: `${marginPct}%` }"
      >
        {{ Math.round(marginNm) }}
      </div>
      <div
        class="text-center text-(--sk-ink-muted)"
        :style="{ width: `${bandPct}%` }"
      >
        패턴 {{ spanNm.toLocaleString() }} nm
      </div>
      <div
        class="text-center text-(--sk-brand-ink)"
        :style="{ width: `${marginPct}%` }"
      >
        {{ Math.round(marginNm) }}
      </div>
    </div>

    <div class="mb-1.5 mt-4 sk-eyebrow">
      ② Pitch {{ pitchNm }} nm 확대 — 픽셀 경계 {{ pxPerPitch.toFixed(1) }} px
    </div>
    <div class="relative h-16 overflow-hidden rounded-[var(--sk-r-nav)] bg-(--sk-field)">
      <div class="absolute inset-0 flex">
        <div :style="{ width: `${barPct}%`, background: barFill }" />
        <div :style="{ width: `${spacePct}%` }" />
      </div>
      <div
        class="absolute inset-0"
        :style="{ background: `repeating-linear-gradient(90deg,${pxGridColor} 0 1px,transparent 1px ${pxStepPct}%)` }"
      />
      <div
        class="absolute inset-y-0 left-0 border-r border-dashed border-(--sk-brand)"
        :style="{ width: `${barPct}%` }"
      />
    </div>
    <div class="mt-1.5 flex font-mono text-[11px]">
      <div
        class="text-center text-(--sk-brand-ink)"
        :style="{ width: `${barPct}%` }"
      >
        CD {{ cdNm }} · <strong>{{ pxPerCdValue.toFixed(1) }} px</strong>
      </div>
      <div
        class="text-center text-(--sk-ink-muted)"
        :style="{ width: `${spacePct}%` }"
      >
        space {{ (pitchNm - cdNm).toFixed(0) }} nm
      </div>
    </div>
  </div>
</template>
