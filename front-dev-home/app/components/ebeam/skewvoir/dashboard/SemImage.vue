<template>
  <EbeamSkewvoirPanelFrame
    v-model="mode"
    title="SEM Image"
    :meta="meta"
    :toggles="['Single', '4-up']"
    icon="i-lucide-image"
  >
    <div
      v-if="!images.length"
      class="flex h-56 items-center justify-center text-[12px] text-(--sk-ink-subtle)"
    >
      이미지가 없습니다.
    </div>
    <div
      v-else-if="mode === 'Single'"
      class="flex h-56 items-center justify-center"
    >
      <img
        :src="msrImageUrl(images[0]!)"
        :alt="images[0]"
        class="max-h-56 rounded-(--sk-r-chip) border border-(--sk-border)"
      >
    </div>
    <div
      v-else
      class="grid grid-cols-2 gap-1.5"
    >
      <img
        v-for="img in images.slice(0, 4)"
        :key="img"
        :src="msrImageUrl(img)"
        :alt="img"
        class="w-full rounded-(--sk-r-chip) border border-(--sk-border)"
      >
    </div>
  </EbeamSkewvoirPanelFrame>
</template>

<script setup lang="ts">
import type { SkewvoirAnalysis } from '~/composables/useSkewvoirAnalysis'
import { measuredRows } from '~/utils/msrRows'

const props = defineProps<{ analysis: SkewvoirAnalysis }>()

const { msrImageUrl } = useMsrFileApi()

const mode = ref('Single')

const images = computed(() => {
  const rows = measuredRows(props.analysis.siteRows.value).filter(r => r.parameter === props.analysis.activeParam.value)
  const focused = props.analysis.focusedSequence.value
  const ordered = focused != null
    ? [...rows].sort((a, b) => (a.sequence === focused ? -1 : 0) - (b.sequence === focused ? -1 : 0))
    : rows
  const seen = new Set<string>()
  const out: string[] = []
  for (const r of ordered) {
    const name = r.mp_image_name_01
    if (name && !seen.has(name)) {
      seen.add(name)
      out.push(name)
    }
  }
  return out
})

const meta = computed(() => {
  const seq = props.analysis.focusedSequence.value
  return seq != null ? `seq ${seq}` : (images.value[0] ?? `${images.value.length} images`)
})
</script>
