<script setup lang="ts">
import type { ChatAttachment } from '~/composables/useChatApi'
import { buildAttachmentOption } from '~/utils/chatAttachmentChart'
import { copyTableToClipboard } from '~/utils/tableExport'

// One data attachment under an assistant turn: a chart when the answer says
// so and the spec is drawable, a table otherwise. Numbers come straight from
// the tool's dataframe dict — nothing here is retyped by a model.
const props = defineProps<{ attachment: ChatAttachment }>()

const isChart = computed(() => props.attachment.kind === 'chart' && !!props.attachment.chart)

// The table is always available behind a chart: the reader who wants the
// number, not the shape, flips to it without asking the assistant again.
const showTable = ref(!isChart.value)
watch(isChart, (chart) => {
  showTable.value = !chart
})

const chartEl = ref<HTMLDivElement | null>(null)
const { palette } = useEchartsTheme()
const option = computed(() => buildAttachmentOption(props.attachment, palette.value))
useEchart(chartEl, option, { exportName: props.attachment.title })

const meta = computed(() => {
  const { data } = props.attachment
  const shown = data.rows.length
  return data.truncated ? `${shown}행 표시 (전체 ${data.row_count}행)` : `${shown}행`
})

const format = (cell: string | number | boolean | null): string => {
  if (cell == null) return ''
  if (typeof cell === 'number') return Number.isInteger(cell) ? cell.toLocaleString() : cell.toFixed(3)
  return String(cell)
}

const copied = ref(false)
const copy = async () => {
  const { data } = props.attachment
  if (!(await copyTableToClipboard(data.columns, data.rows))) return
  copied.value = true
  setTimeout(() => (copied.value = false), 1400)
}
</script>

<template>
  <figure class="sk-chat-attachment">
    <figcaption class="sk-chat-attachment-head">
      <span class="sk-chat-attachment-title">{{ attachment.title }}</span>
      <span class="sk-chat-attachment-meta">{{ meta }}</span>
      <span class="ml-auto flex items-center gap-1">
        <UButton
          v-if="isChart"
          :icon="showTable ? 'i-lucide-chart-line' : 'i-lucide-table'"
          :label="showTable ? '차트' : '표'"
          color="neutral"
          variant="ghost"
          size="xs"
          @click="showTable = !showTable"
        />
        <UButton
          :icon="copied ? 'i-lucide-check' : 'i-lucide-copy'"
          :label="copied ? '복사됨' : '표 복사'"
          color="neutral"
          variant="ghost"
          size="xs"
          @click="copy"
        />
      </span>
    </figcaption>

    <!-- v-show, not v-if: the chart instance survives a flip to the table and
         back, so ECharts does not re-initialise on every toggle. -->
    <div
      v-if="isChart"
      v-show="!showTable"
      ref="chartEl"
      class="sk-chat-attachment-chart"
    />
    <div
      v-if="showTable"
      class="sk-chat-table-wrap"
    >
      <table class="sk-chat-table">
        <thead>
          <tr>
            <th
              v-for="column in attachment.data.columns"
              :key="column"
            >
              {{ column }}
            </th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="(row, index) in attachment.data.rows"
            :key="index"
          >
            <td
              v-for="(cell, cellIndex) in row"
              :key="cellIndex"
              :class="{ 'sk-chat-cell-num': typeof cell === 'number' }"
            >
              {{ format(cell) }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </figure>
</template>

<style scoped>
.sk-chat-attachment {
  margin: 0.625rem 0 0;
  border: 1px solid var(--sk-border-soft);
  border-radius: var(--sk-r-card, 0.625rem);
  background: var(--sk-surface);
  overflow: hidden;
}

.sk-chat-attachment-head {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 0.625rem 0.375rem;
  border-bottom: 1px solid var(--sk-border-soft);
}

.sk-chat-attachment-title {
  font-size: 0.8125rem;
  font-weight: 600;
  color: var(--sk-ink);
}

.sk-chat-attachment-meta {
  font-size: 0.6875rem;
  color: var(--sk-ink-subtle);
}

.sk-chat-attachment-chart {
  height: 240px;
  padding: 0.25rem;
}

.sk-chat-table-wrap {
  max-height: 320px;
  overflow: auto;
}

.sk-chat-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.8125rem;
}

.sk-chat-table th,
.sk-chat-table td {
  padding: 0.3rem 0.625rem;
  border-bottom: 1px solid var(--sk-border-soft);
  text-align: left;
  white-space: nowrap;
}

.sk-chat-table th {
  position: sticky;
  top: 0;
  background: var(--sk-muted-surface);
  font-weight: 600;
  color: var(--sk-ink-muted);
}

.sk-chat-cell-num {
  text-align: right;
  font-variant-numeric: tabular-nums;
}
</style>
