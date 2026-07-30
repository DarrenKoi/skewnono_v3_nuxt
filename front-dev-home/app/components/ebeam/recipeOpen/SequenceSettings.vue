<template>
  <EbeamRecipeOpenParamPanel
    caption="Addressing · Measurement 시퀀스가 어떤 단계로 구성되는지입니다."
    :pending="pending"
    :error="error"
  >
    <EbeamRecipeOpenSettingTable
      title="Sequence (단계 구성)"
      :block="sequence"
    />
  </EbeamRecipeOpenParamPanel>
</template>

<script setup lang="ts">
/**
 * The `sequence_addressing` and `sequence_measurement` groups of one parameter's
 * AF/PR (ENMP) file.
 *
 * Same file as the AF/PR table on the 이미지 + 설정 tab, split by section: these
 * two groups list WHICH STEPS run, the other six hold each step's settings.
 * Rendered as one table so the reader's own group order survives — the split is
 * a filter, never a regrouping.
 */
import type { ParamDetail } from '~/composables/useRecipeParamDetail'
import { splitSequenceSections } from '~/utils/recipeView'

const props = defineProps<{
  detail: ParamDetail | null
  pending: boolean
  error: boolean
}>()

const sequence = computed(() => splitSequenceSections(props.detail?.af_pr ?? null).sequence)
</script>
