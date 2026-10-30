<template>
  <EbeamRecipeOpenParamPanel
    caption="이 파라미터를 무엇으로, 어떻게 측정하는지에 대한 설정입니다."
    :pending="pending"
    :error="error"
  >
    <div class="flex flex-col gap-3">
      <EbeamRecipeOpenSettingTable
        v-if="formulaBlock"
        title="Formula (계산식)"
        :block="formulaBlock"
      />
      <EbeamRecipeOpenSettingTable
        title="AMP (측정 알고리즘)"
        :block="ampBlock"
      />
    </div>
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
 *
 * A computed parameter gets its formula above the AMP table — read from the
 * ENMP file's `formula` group, its `$N` references named by block number
 * (office 확인 2026-10-22).
 */
import type { ParamDetail, SettingBlock } from '~/composables/useRecipeParamDetail'
import { resolveFormula } from '~/utils/recipeView'

const props = defineProps<{
  detail: ParamDetail | null
  pending: boolean
  error: boolean
  /** P_No → Parameter from wafer_mp_info, what a formula's `$N` names (`formulaRefNames`). */
  refNames: ReadonlyMap<number, string>
}>()

// Cursor coordinate lists run to hundreds of entries and mean nothing read as
// text — the server already turns them into measurement marks on the image.
const HIDDEN_AMP_KEYS = new Set(['Cursor_Positions', 'MP_Cursor_Positions'])

const ampBlock = computed<SettingBlock | null>(() => {
  const amp = props.detail?.amp
  if (!amp) return null
  return { ...amp, rows: amp.rows.filter(row => !HIDDEN_AMP_KEYS.has(row.key)) }
})

// The formula GROUP is the flag (office 확인 2026-10-22), so it alone decides:
// gating on AMP Measurement too would hide a real formula whenever the PRMS
// file is missing or unreadable.
const formulaBlock = computed<SettingBlock | null>(() => {
  const afPr = props.detail?.af_pr
  if (!afPr) return null
  const formula = resolveFormula(afPr.rows, props.refNames)
  if (!formula) return null
  return {
    source: afPr.source,
    rows: [
      { key: '원본', value: formula.raw },
      { key: '해석', value: formula.resolved }
    ]
  }
})
</script>
