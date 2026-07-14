<template>
  <EbeamSkewvoirPanelFrame
    title="SEM Gallery"
    :meta="`${images.length} sites · MP: ${analysis.activeParam.value}`"
    icon="i-lucide-images"
  >
    <div
      v-if="analysis.focusPending.value"
      class="flex h-96 items-center justify-center gap-2 text-[12px] text-(--sk-ink-muted)"
    >
      <UIcon
        name="i-lucide-loader-circle"
        class="h-4 w-4 animate-spin"
      />
      불러오는 중…
    </div>
    <div
      v-else-if="images.length"
      class="grid max-h-[34rem] grid-cols-3 gap-2 overflow-auto sm:grid-cols-4 xl:grid-cols-6"
    >
      <figure
        v-for="img in images"
        :key="img.name"
        class="overflow-hidden rounded-(--sk-r-chip) border border-(--sk-border)"
      >
        <img
          :src="msrImageUrl(img.name)"
          :alt="img.name"
          class="aspect-square w-full object-cover"
          loading="lazy"
        >
        <figcaption class="truncate px-1.5 py-1 font-mono text-[9.5px] text-(--sk-ink-subtle)">
          {{ img.chip }} · {{ img.cd.toFixed(2) }}
        </figcaption>
      </figure>
    </div>
    <div
      v-else
      class="flex h-96 items-center justify-center text-[12px] text-(--sk-ink-subtle)"
    >
      {{ analysis.activeParam.value }} 이미지가 없습니다.
    </div>
  </EbeamSkewvoirPanelFrame>
</template>

<script setup lang="ts">
import type { SkewvoirAnalysis } from '~/composables/useSkewvoirAnalysis'
import { measuredRows } from '~/utils/msrRows'

const props = defineProps<{ analysis: SkewvoirAnalysis }>()

const { msrImageUrl } = useMsrFileApi()

const images = computed(() => {
  const seen = new Set<string>()
  const out: { name: string, chip: string, cd: number }[] = []
  for (const r of measuredRows(props.analysis.siteRows.value)) {
    if (r.parameter !== props.analysis.activeParam.value) continue
    const name = r.mp_image_name_01
    if (name && !seen.has(name)) {
      seen.add(name)
      out.push({ name, chip: r.chip_number, cd: r.cd_value })
    }
  }
  return out
})
</script>
