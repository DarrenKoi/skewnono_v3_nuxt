<template>
  <section
    class="dashboard-surface flex flex-wrap items-center gap-x-8 gap-y-4 rounded-(--sk-r-card) px-5 py-4"
    aria-label="측정 개요"
  >
    <div class="min-w-0 max-w-full flex-1 basis-80">
      <p class="sk-label">
        Recipe
      </p>
      <p
        class="truncate sk-card-id"
        :title="recipe"
      >
        {{ recipe }}
      </p>
      <p class="mt-1 flex min-w-0 items-center gap-1">
        <span
          class="truncate sk-field-name"
          :title="filename"
        >{{ filename }}</span>
        <UButton
          size="xs"
          color="neutral"
          variant="ghost"
          icon="i-lucide-copy"
          aria-label="파일 이름 복사"
          @click="copyFilename"
        />
      </p>
    </div>

    <dl class="flex flex-wrap items-stretch gap-y-3 divide-x divide-(--sk-border-soft)">
      <div
        v-for="cell in cells"
        :key="cell.label"
        class="flex flex-col justify-center gap-1 px-5 first:pl-0 last:pr-0"
      >
        <dt class="text-xs font-medium whitespace-nowrap text-(--sk-ink-muted)">
          {{ cell.label }}
        </dt>
        <dd
          class="text-base font-semibold whitespace-nowrap text-(--sk-ink)"
          :class="cell.sans ? null : 'font-mono tabular-nums'"
        >
          {{ cell.value }}
        </dd>
      </div>
      <div
        v-if="measurement"
        class="flex flex-col justify-center gap-1 px-5 last:pr-0"
      >
        <dt class="text-xs font-medium text-(--sk-ink-muted)">
          데이터
        </dt>
        <dd class="flex h-6 items-center">
          <AfmDataAvailability :measurement="measurement" />
        </dd>
      </div>
    </dl>
  </section>
</template>

<script setup lang="ts">
// The measurement this page is about, read before anything else: the recipe as
// the headline, the file name under it (copyable — it is what people paste into
// a ticket), and the identifiers and counts the cards below are computed from.
// The list row (`measurement`) is the source where it is known; a deep link with
// no list loaded falls back to the information block.
import type { AfmMeasurement } from '~/composables/useAfmCart'
import type { AfmInformation } from '~/composables/useAfmDetailApi'
import { copyTextToClipboard } from '~/utils/tableExport'

const props = defineProps<{
  filename: string
  measurement?: AfmMeasurement
  information: AfmInformation
  pointCount: number
  siteCount: number
  validCount: number
  rowCount: number
}>()

const info = (key: string) => {
  const value = props.information[key]
  return value === null || value === undefined || value === '' ? undefined : String(value)
}

const recipe = computed(() => props.measurement?.recipeName ?? info('Recipe ID') ?? '–')

const cells = computed(() => [
  { label: '측정 일시', value: props.measurement?.formattedDate ?? info('Start Time') ?? '–' },
  { label: 'Lot', value: props.measurement?.lotId ?? info('Lot ID') ?? '–' },
  { label: 'Slot', value: String(props.measurement?.slotNumber ?? '–') },
  { label: '측정', value: props.measurement?.measuredInfo ?? info('Measurement') ?? '–', sans: true },
  { label: '포인트', value: String(props.pointCount) },
  { label: '사이트', value: String(props.siteCount) },
  { label: '유효 행', value: props.rowCount ? `${props.validCount} / ${props.rowCount}` : '–' }
])

const toast = useToast()
const copyFilename = async () => {
  const ok = await copyTextToClipboard(props.filename)
  toast.add(ok
    ? { title: '파일 이름을 복사했습니다.', icon: 'i-lucide-check', color: 'success' }
    : { title: '파일 이름을 복사하지 못했습니다.', icon: 'i-lucide-triangle-alert', color: 'error' })
}
</script>
