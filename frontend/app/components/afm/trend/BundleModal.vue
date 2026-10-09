<template>
  <!-- 이상 측정 조사 묶음. The memo is session-only: it rides into the file and is
       stored nowhere. -->
  <UModal
    v-model:open="open"
    title="이상 측정 조사 묶음"
    description="기준 범위 밖이거나 FAILED·STOPPED 포인트가 있는 측정과 그 근거를 Excel 파일로 남깁니다."
  >
    <template #body>
      <div class="flex flex-col gap-3">
        <UFormField label="메모">
          <UTextarea
            v-model="memo"
            placeholder="조사하면서 본 것을 적어 두세요 (선택 · 저장되지 않고 파일에만 들어갑니다)"
            :rows="4"
            class="w-full"
          />
        </UFormField>
        <p class="sk-meta">
          {{ BUNDLE_CAUTION }}
        </p>
        <div class="flex justify-end">
          <UButton
            color="primary"
            icon="i-lucide-download"
            label="내려받기"
            :loading="busy"
            :disabled="!ready"
            @click="download"
          />
        </div>
      </div>
    </template>
  </UModal>
</template>

<script setup lang="ts">
import type { AfmSummaryItem } from '~/composables/useAfmDetailApi'
import type { RecipeCentre, TrendRow } from '~/utils/afmTrend'
import { downloadWorkbook } from '~/utils/xlsx'

// afmBundle.ts owns what goes in the file; this only hands over the page's
// state and reports a failed write.
const props = defineProps<{
  tool: string
  block: string
  column: string
  stat: AfmSummaryItem
  rows: TrendRow[]
  centres: Map<string, RecipeCentre>
  showLimits: boolean
  notLoaded: number
  // 02 포인트별 비교's 제외 choice, so the file's per-point reference is the screen's.
  pointsValidOnly: boolean
  // Details loaded and at least one suspect — the group can change while open.
  ready: boolean
}>()
const open = defineModel<boolean>('open', { required: true })

const toast = useToast()
const memo = ref('')
const busy = ref(false)

const download = async () => {
  if (busy.value || !props.ready) return
  const bundle = buildBundle({
    generatedAt: new Date(),
    tool: props.tool,
    block: props.block,
    column: props.column,
    stat: props.stat,
    rows: props.rows,
    centres: props.centres,
    showLimits: props.showLimits,
    notLoaded: props.notLoaded,
    pointsValidOnly: props.pointsValidOnly,
    memo: memo.value
  })
  busy.value = true
  try {
    await downloadWorkbook(
      `${props.tool.toLowerCase()}-suspects-${safeFilePart(props.block)}-${safeFilePart(props.column)}.xlsx`,
      bundleSheets(bundle)
    )
    open.value = false
  } catch {
    // exceljs is a dynamic import: a redeploy under an open tab 404s the chunk.
    toast.add({ ...EXCEL_DOWNLOAD_FAILED })
  } finally {
    busy.value = false
  }
}
</script>
