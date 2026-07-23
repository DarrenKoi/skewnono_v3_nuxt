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
            v-if="imageName && blobUrl"
            class="relative aspect-square w-full overflow-hidden rounded-(--sk-r-chip) border border-(--sk-border)"
          >
            <EbeamSkewvoirZoomableImage
              :key="imageName"
              :src="blobUrl"
              :alt="imageName"
              class="h-full w-full"
            />
          </div>
          <div
            v-else-if="imageName && imageLoading"
            class="flex h-40 items-center justify-center rounded-(--sk-r-chip) border border-dashed border-(--sk-border) sk-body"
          >
            <UIcon
              name="i-lucide-loader-circle"
              class="h-5 w-5 animate-spin"
            />
          </div>
          <div
            v-else
            class="flex h-40 items-center justify-center rounded-(--sk-r-chip) border border-dashed border-(--sk-border) sk-body"
          >
            {{ imageFailed ? '이미지 로드 실패' : '측정 이미지가 없습니다.' }}
          </div>

          <div v-if="imageCond">
            <p class="mt-2 mb-1 sk-eyebrow">
              취득 조건
            </p>
            <pre class="max-h-32 overflow-auto rounded-(--sk-r-chip) border border-(--sk-border) bg-(--sk-chip-bg) p-2 font-mono text-[10px] whitespace-pre-wrap text-(--sk-ink-muted)">{{ imageCond }}</pre>
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

const { fetchImageWithCond } = useMsrImageApi()

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

// Every image in this drawer belongs to the FOCUS MSR — same context as the
// gallery (focusRow's eqp_ip/class_name + focusMsr).
const focusCtx = computed(() => {
  const row = props.analysis.focusRow.value
  return {
    eqp_ip: row?.eqp_ip ?? '',
    class_name: row?.class_name ?? '',
    msr: props.analysis.focusMsr.value ?? ''
  }
})

const blobUrl = ref<string | null>(null)
const imageCond = ref<string | null>(null)
const imageLoading = ref(false)
const imageFailed = ref(false)

const revokeBlob = () => {
  if (blobUrl.value) {
    URL.revokeObjectURL(blobUrl.value)
    blobUrl.value = null
  }
}

let loadToken = 0

watch(
  () => `${focusCtx.value.eqp_ip}|${focusCtx.value.class_name}|${focusCtx.value.msr}|${imageName.value ?? ''}`,
  async () => {
    const name = imageName.value
    const ctx = focusCtx.value
    revokeBlob()
    imageCond.value = null
    imageFailed.value = false
    if (!name) return
    if (!ctx.eqp_ip) {
      // Context not resolved yet (e.g. focus row still pending) — treat as a
      // load failure rather than silently rendering a broken image.
      imageFailed.value = true
      return
    }
    const token = ++loadToken
    imageLoading.value = true
    try {
      const res = await fetchImageWithCond(ctx.eqp_ip, ctx.class_name, ctx.msr, name)
      if (token !== loadToken) {
        URL.revokeObjectURL(res.blobUrl)
        return
      }
      blobUrl.value = res.blobUrl
      imageCond.value = res.cond
    } catch {
      if (token === loadToken) imageFailed.value = true
    } finally {
      if (token === loadToken) imageLoading.value = false
    }
  },
  { immediate: true }
)

onBeforeUnmount(() => {
  loadToken++
  revokeBlob()
})
</script>
