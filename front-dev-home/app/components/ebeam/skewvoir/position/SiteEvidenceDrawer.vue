<template>
  <USlideover
    :open="open"
    :title="site ? `Site ${site.chip}` : '측정점 상세'"
    description="선택한 측정점의 값 · 잔차 · 순서 · SEM"
    :ui="{ content: 'w-[92vw] sm:max-w-[420px]' }"
    @update:open="emit('update:open', $event)"
  >
    <template #body>
      <div
        v-if="site"
        class="space-y-4"
      >
        <dl class="grid grid-cols-2 gap-2">
          <div class="rounded-(--sk-r-nav) border border-(--sk-border-soft) px-2.5 py-2">
            <dt class="sk-eyebrow">
              chip · seq
            </dt>
            <dd class="mt-0.5 font-mono text-[13px] font-semibold text-(--sk-ink)">
              {{ site.chip }} · {{ site.sequence }}
            </dd>
          </div>
          <div class="rounded-(--sk-r-nav) border border-(--sk-border-soft) px-2.5 py-2">
            <dt class="sk-eyebrow">
              sector · R
            </dt>
            <dd class="mt-0.5 font-mono text-[13px] font-semibold text-(--sk-ink)">
              {{ site.sector ?? '—' }} · {{ site.radiusMm != null ? `${site.radiusMm.toFixed(1)} mm` : '—' }}
            </dd>
          </div>
          <div class="rounded-(--sk-r-nav) border border-(--sk-border-soft) px-2.5 py-2">
            <dt class="sk-eyebrow">
              raw ({{ unit }})
            </dt>
            <dd class="mt-0.5 font-mono text-[13px] font-semibold text-(--sk-ink)">
              {{ site.raw.toFixed(3) }}
            </dd>
          </div>
          <div class="rounded-(--sk-r-nav) border border-(--sk-border-soft) px-2.5 py-2">
            <dt class="sk-eyebrow">
              중앙값 대비
            </dt>
            <dd
              class="mt-0.5 font-mono text-[13px] font-semibold"
              :class="site.centered >= 0 ? 'text-(--sk-bad)' : 'text-(--sk-ok)'"
            >
              {{ site.centered >= 0 ? '+' : '' }}{{ site.centered.toFixed(3) }}
            </dd>
          </div>
          <div class="col-span-2 rounded-(--sk-r-nav) border border-(--sk-border-soft) px-2.5 py-2">
            <dt class="sk-eyebrow">
              추세 잔차 (residual)
            </dt>
            <dd class="mt-0.5 font-mono text-[13px] font-semibold text-(--sk-ink)">
              <span v-if="site.residual != null">{{ site.residual >= 0 ? '+' : '' }}{{ site.residual.toFixed(3) }} {{ unit }}</span>
              <span
                v-else
                class="text-(--sk-ink-subtle)"
              >추세 없음 — 평가 불가</span>
            </dd>
          </div>
        </dl>

        <section>
          <p class="mb-1.5 sk-eyebrow">
            SEM 미리보기
          </p>
          <div
            v-if="imageName"
            class="relative aspect-square w-full overflow-hidden rounded-(--sk-r-chip) border border-(--sk-border)"
          >
            <EbeamSkewvoirZoomableImage
              :key="imageName"
              :src="msrImageUrl(imageName)"
              :alt="imageName"
              class="h-full w-full"
            />
          </div>
          <div
            v-else
            class="flex h-40 items-center justify-center rounded-(--sk-r-chip) border border-dashed border-(--sk-border) sk-body"
          >
            측정 이미지가 없습니다.
          </div>
        </section>
      </div>
      <div
        v-else
        class="flex h-40 items-center justify-center px-4 text-center sk-body"
      >
        지도나 표에서 측정점을 선택하세요.
      </div>
    </template>
  </USlideover>
</template>

<script setup lang="ts">
import type { SkewvoirAnalysis } from '~/composables/useSkewvoirAnalysis'
import type { SpatialResult } from '~/utils/skewvoirAnalysis/spatial'
import { isMeasuredRow } from '~/utils/msrRows'

const props = defineProps<{
  open: boolean
  spatial: SpatialResult
  analysis: SkewvoirAnalysis
  unit: string
}>()
const emit = defineEmits<{ 'update:open': [value: boolean] }>()

const { msrImageUrl } = useMsrFileApi()

// The focused site (by chip_number) — first measured site on that die.
const site = computed(() => {
  const key = props.analysis.focusedSite.value
  if (!key) return null
  return props.spatial.sites.find(s => s.chip === key) ?? null
})

// SEM micrograph for the focused site's sequence, from the raw row.
const imageName = computed(() => {
  const s = site.value
  if (!s) return null
  const row = props.analysis.siteRows.value.find(
    r => r.parameter === props.analysis.activeParam.value && isMeasuredRow(r) && r.sequence === s.sequence
  )
  return row?.mp_image_name_01 || null
})
</script>
