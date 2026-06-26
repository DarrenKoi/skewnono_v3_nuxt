<template>
  <EbeamSkewvoirPanelFrame
    title="SEM Image"
    :meta="meta"
    :toggles="['Single', '4-up']"
    icon="i-lucide-image"
  >
    <div class="flex h-56 flex-col items-center justify-center gap-2 rounded-(--sk-r-chip) border border-dashed border-(--sk-border) text-(--sk-ink-subtle)">
      <UIcon
        name="i-lucide-image"
        class="h-7 w-7"
      />
      <p
        v-if="firstImage"
        class="font-mono text-[11px]"
      >
        {{ firstImage }}
      </p>
      <p class="text-[10.5px]">
        이미지 뷰어는 다음 단계에서 연결됩니다.
      </p>
    </div>
  </EbeamSkewvoirPanelFrame>
</template>

<script setup lang="ts">
import type { SkewvoirAnalysis } from '~/composables/useSkewvoirAnalysis'

const props = defineProps<{ analysis: SkewvoirAnalysis }>()

const firstImage = computed(() => {
  const row = props.analysis.siteRows.value.find(
    r => r.parameter === props.analysis.activeParam.value && r.mp_image_name_01
  )
  return row?.mp_image_name_01 ?? ''
})

const meta = computed(() => firstImage.value || `${props.analysis.focusRow.value?.total_images ?? 0} images`)
</script>
