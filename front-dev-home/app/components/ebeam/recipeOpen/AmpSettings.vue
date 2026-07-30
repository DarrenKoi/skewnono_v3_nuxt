<template>
  <EbeamRecipeOpenParamPanel
    caption="이 파라미터를 무엇으로, 어떻게 측정하는지에 대한 설정입니다."
    :pending="pending"
    :error="error"
  >
    <EbeamRecipeOpenSettingTable
      title="AMP (측정 알고리즘)"
      :block="detail?.amp ?? null"
    />
  </EbeamRecipeOpenParamPanel>
</template>

<script setup lang="ts">
/**
 * One parameter's measurement algorithm — the AMP file (`img_meas2` →
 * `PRMS0000`), which names no image and is why the settings panel shows three
 * thumbnails but more than three tables.
 *
 * Its own tab rather than a table beside AF/PR: Measurement · Object · Kind ·
 * Design_Value are the settings an engineer opens this screen to read, and they
 * were previously the smaller half of a two-column grid.
 */
import type { ParamDetail } from '~/composables/useRecipeParamDetail'

defineProps<{
  detail: ParamDetail | null
  pending: boolean
  error: boolean
}>()
</script>
